#!/usr/bin/env python3
"""Read and check the kit manifest.

Commands:
    list     show every module the kit offers
    values   show every value the kit can substitute
    check    validate the manifest against the schema and the files

`check` only looks and reports; it never writes. Bringing the manifest back
in line with the disk is a separate command, `sync`, not written yet.

The output is a report meant to be read by the caller or skill that decides
what to do about it.
"""

import argparse
import json
import re
import sys
from pathlib import Path


def find_kit_root(start):
    """Find the plugin root by its stable on-disk markers."""
    for directory in (start, *start.parents):
        if (
            (directory / ".claude-plugin" / "plugin.json").is_file()
            and (directory / "manifest.json").is_file()
        ):
            return directory
    raise RuntimeError(f"could not find the rulekit plugin root above: {start}")


KIT = find_kit_root(Path(__file__).resolve().parent)
MANIFEST = KIT / "manifest.json"
TEMPLATE = KIT / "template"

MODULE_FIELDS = {
    "group": (str, type(None)),
    "required": (bool,),
    "load": (str,),
    "scaffold": (list,),
    "skills": (list,),
}
LOAD_VALUES = {"always", "on-demand"}
VALUE_FIELDS = {
    "choices": (list, type(None)),
    "default": (str, type(None)),
    "prompt": (str,),
    "required": (bool,),
}

def load_manifest():
    with MANIFEST.open() as fh:
        return json.load(fh)


def opening(path):
    """The first line of real content: comments and blank lines skipped."""
    if not path.is_file():
        return None
    text = re.sub(r"<!--.*?-->", "", path.read_text(), flags=re.S)
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return None


def first_heading(path):
    """The heading a file opens with, as (marker, text).

    Returns None when the file does not open with a heading at all. The
    marker is whatever is there, `#` included: a rules file opening at `#`
    is wrong, and saying which level it used beats reporting nothing.
    """
    line = opening(path)
    if line is None:
        return None
    match = re.match(r"(#+)\s+(.*)", line)
    return (match.group(1), match.group(2).strip()) if match else None


def heading(path, level="##"):
    """The module description: the text of the heading, if it is at `level`."""
    found = first_heading(path)
    if found is None or found[0] != level:
        return None
    return found[1]


def entry_point(root, key):
    """Where a module's rules start.

    The key is the path, without an extension: the script looks at what is
    on disk. A directory is a composite module and starts at its `INDEX.md`;
    otherwise the module is a single file, `<key>.md`.
    """
    if (root / "rules" / key).is_dir():
        return Path("rules") / key / "INDEX.md"
    return Path("rules") / f"{key}.md"


def rule_files(root, key):
    """The rules files of one module, found on disk, not by reading them.

    A composite module is its whole directory: every `.md` in it belongs to
    the module. `@` imports are how the model pulls the parts together, and
    the scripts have no business following them - the manifest and the disk
    are their source of truth.
    """
    directory = root / "rules" / key
    if directory.is_dir():
        return sorted(p.relative_to(root) for p in directory.glob("*.md"))
    return [Path("rules") / f"{key}.md"]


def module_files(key, module, root=TEMPLATE):
    """Every file a module contributes, as (kind, relative path) pairs."""
    for rel in rule_files(root, key):
        yield "rules", rel
    for name in module["scaffold"]:
        yield "scaffold", Path(name)
    for name in module["skills"]:
        yield "skills", Path(name)


def cmd_list(manifest):
    """Print the catalogue.

    Reads the manifest defensively: `list` does not validate, and a field
    missing from a half-written entry should not stop the listing. `check`
    is where an incomplete manifest gets reported.
    """
    modules = manifest.get("modules", {})
    groups = {}
    for key, module in modules.items():
        groups.setdefault(module.get("group"), []).append(key)

    for key in sorted(modules):
        module = modules[key]
        desc = heading(TEMPLATE / entry_point(TEMPLATE, key))

        flags = []
        group = module.get("group")
        if group:
            members = groups[group]
            mandatory = any(modules[m].get("required") for m in members)
            flags.append(f"group={group}, {'pick one' if mandatory else 'optional'}")
        elif module.get("required"):
            flags.append("required")
        else:
            flags.append("optional")
        if module.get("load", "always") != "always":
            flags.append(module["load"])

        suffix = f"  [{', '.join(flags)}]" if flags else ""
        print(f"{key}{suffix}")
        source = Path("template") / entry_point(TEMPLATE, key)
        print(f"    source: {source.as_posix()}")
        if desc:
            print(f"    {desc}")
    return 0


def cmd_values(manifest):
    """Print the values available for substitution."""
    for key in sorted(manifest.get("values", {})):
        value = manifest["values"][key]
        required = "required" if value.get("required") else "optional"
        default = value.get("default")
        default_flag = "no default" if default is None else f"default={default}"
        choices = value.get("choices")
        choice_flags = [] if choices is None else [f"choices={','.join(choices)}"]

        flags = ", ".join([required, default_flag, *choice_flags])
        print(f"{key}  [{flags}]")
        if value.get("prompt"):
            print(f"    {value['prompt']}")
    return 0


def check_key_order(value, path, problems):
    """Every object in the manifest has lexicographically sorted keys."""
    if isinstance(value, dict):
        keys = list(value)
        if keys != sorted(keys):
            problems.append(f"{path}: object keys are not sorted")
        for key, child in value.items():
            check_key_order(child, f"{path}.{key}", problems)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_key_order(child, f"{path}[{index}]", problems)


def check_schema(manifest, problems):
    for section in ("core", "modules", "paths", "values"):
        if section not in manifest:
            problems.append(f"manifest: missing top-level section `{section}`")

    check_key_order(manifest, "manifest", problems)

    for key, module in manifest.get("modules", {}).items():
        for field, types in MODULE_FIELDS.items():
            if field not in module:
                problems.append(f"{key}: missing field `{field}`")
            elif not isinstance(module[field], types):
                problems.append(f"{key}: field `{field}` has the wrong type")
        for field in module:
            if field not in MODULE_FIELDS:
                problems.append(f"{key}: unknown field `{field}`")
        if module.get("load") not in LOAD_VALUES:
            problems.append(f"{key}: `load` must be one of {sorted(LOAD_VALUES)}")

    for key, value in manifest.get("values", {}).items():
        for field, types in VALUE_FIELDS.items():
            if field not in value:
                problems.append(f"{key}: missing field `{field}`")
            elif not isinstance(value[field], types):
                problems.append(f"{key}: field `{field}` has the wrong type")
        for field in value:
            if field not in VALUE_FIELDS:
                problems.append(f"{key}: unknown field `{field}`")
        choices = value.get("choices")
        if isinstance(choices, list):
            if not choices:
                problems.append(f"{key}: `choices` must not be empty")
            elif not all(isinstance(choice, str) and choice for choice in choices):
                problems.append(f"{key}: `choices` must contain non-empty strings")
            elif len(choices) != len(set(choices)):
                problems.append(f"{key}: `choices` contains duplicates")
            elif value.get("default") is not None and value["default"] not in choices:
                problems.append(f"{key}: `default` must be one of `choices`")


def check_keys(manifest, problems):
    """The key is the path to the module's rules, so it has to resolve."""
    for key in manifest.get("modules", {}):
        directory = TEMPLATE / "rules" / key
        if directory.is_dir():
            if not (directory / "INDEX.md").is_file():
                problems.append(
                    f"{key}: `rules/{key}/` is a composite module, so it must "
                    "contain an `INDEX.md` as its entry point"
                )
        elif not (TEMPLATE / "rules" / f"{key}.md").is_file():
            problems.append(
                f"{key}: resolves to neither `rules/{key}.md` nor a "
                f"directory `rules/{key}/`"
            )


def check_files(manifest, problems):
    """Every file exists, and every file in template/ belongs to something.

    A file cannot belong to two modules: the key is the path, so one module
    is one path. Only orphans are worth looking for.
    """
    owned = set()
    for key, module in manifest.get("modules", {}).items():
        for _, rel in module_files(key, module):
            if not (TEMPLATE / rel).exists():
                problems.append(f"{key}: `{rel}` does not exist")
            owned.add(rel)

    for section in ("rules", "scaffold"):
        for name in manifest.get("core", {}).get(section, []):
            if not (TEMPLATE / name).exists():
                problems.append(f"core: `{name}` does not exist")
            owned.add(Path(name))

    for path in sorted(TEMPLATE.rglob("*.md")):
        rel = path.relative_to(TEMPLATE)
        if rel not in owned:
            problems.append(f"`{rel}` is in template/ but no module owns it")


def check_modules(manifest, problems):
    """Headings, and the `.tmpl` suffix on scaffolds.

    The entry point of a module carries a `##` naming the module as a whole.
    The other files of a composite module are parts of it, so they open at
    `###` instead.
    """
    for key, module in manifest.get("modules", {}).items():
        entry = entry_point(TEMPLATE, key)
        for rel in rule_files(TEMPLATE, key):
            path = TEMPLATE / rel
            if not path.is_file():
                continue
            want = "##" if rel == entry else "###"
            found = first_heading(path)
            if found is None:
                problems.append(
                    f"{key}: `{rel}` does not open with a heading, expected `{want}`"
                )
            elif found[0] != want:
                problems.append(
                    f"{key}: `{rel}` opens at `{found[0]}`, expected `{want}`"
                )

        for name in module.get("scaffold", []):
            if not name.endswith(".tmpl.md"):
                problems.append(
                    f"{key}: scaffold `{name}` is missing the `.tmpl` suffix"
                )


def check_groups(manifest, problems):
    """Variants of one group are simply the modules sharing its name.

    A group whose members disagree about `required` is probably an oversight:
    the fallback is that one required member makes the whole group mandatory,
    but say so rather than deciding silently.
    """
    groups = {}
    for key, module in manifest.get("modules", {}).items():
        group = module.get("group")
        if group:
            groups.setdefault(group, []).append(key)

    for group, members in sorted(groups.items()):
        if len(members) < 2:
            problems.append(
                f"group `{group}` has a single member, `{members[0]}` - "
                "probably a typo in `group`"
            )
            continue
        flags = {manifest["modules"][m]["required"] for m in members}
        if len(flags) > 1:
            required = sorted(m for m in members if manifest["modules"][m]["required"])
            problems.append(
                f"group `{group}`: only {', '.join(required)} marked "
                "`required`, so the whole group is treated as mandatory. "
                "Set the same value on every member"
            )


def report(problems):
    for problem in problems:
        print(problem)
    print(f"\n{len(problems)} problem(s)")
    return 1


def cmd_check(manifest):
    """Validate, and report. Never writes: that is `sync`, not written yet."""
    problems = []

    # The schema comes first and on its own: every check below reads fields
    # directly, so there is nothing to say about a manifest whose shape is
    # already wrong.
    check_schema(manifest, problems)
    if problems:
        return report(problems)

    check_keys(manifest, problems)
    check_files(manifest, problems)
    check_modules(manifest, problems)
    check_groups(manifest, problems)

    if not problems:
        print("ok")
        return 0
    return report(problems)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="show every module the kit offers")
    sub.add_parser("values", help="show every value the kit can substitute")
    sub.add_parser("check", help="validate the manifest")
    args = parser.parse_args()

    manifest = load_manifest()
    if args.command == "list":
        return cmd_list(manifest)
    if args.command == "values":
        return cmd_values(manifest)
    return cmd_check(manifest)


if __name__ == "__main__":
    sys.exit(main())
