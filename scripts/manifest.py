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
CORE = KIT / "core"
MODULES = KIT / "modules"

MODULE_FIELDS = {
    "description": (str,),
    "group": (str, type(None)),
    "required": (bool,),
    "load": (str, type(None)),
}
LOAD_VALUES = {"always", "on-demand"}
KIND_DIRECTORIES = ("rules", "scaffold", "skills")
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


def module_root(key):
    """Where one module's files live, relative to `modules/`."""
    return Path(key)


def has_rules(root, key):
    """Whether a module ships rules at all."""
    return (root / module_root(key) / "rules").is_dir()


def entry_point(root, key):
    """Where a module's rules start, or None when it ships none.

    Every module is composite: its rules are a directory that starts at
    `INDEX.md`.
    """
    if not has_rules(root, key):
        return None
    return module_root(key) / "rules" / "INDEX.md"


def rule_files(root, key):
    """The rules files of one module, found on disk, not by reading them.

    A module's rules are its whole `rules/` directory: every `.md` in it
    belongs to the module. `@` imports are how the model pulls the parts
    together, and the scripts have no business following them - the disk is
    their source of truth.
    """
    if not has_rules(root, key):
        return []
    directory = root / module_root(key) / "rules"
    return sorted(p.relative_to(root) for p in directory.glob("*.md"))


def kind_files(root, key, kind):
    """Every file a module contributes of one kind, found by glob."""
    directory = root / module_root(key) / kind
    if not directory.is_dir():
        return []
    return sorted(
        p.relative_to(root) for p in directory.rglob("*") if p.is_file()
    )


def module_files(key, root=MODULES):
    """Every file a module contributes, as (kind, relative path) pairs."""
    for kind in KIND_DIRECTORIES:
        for rel in kind_files(root, key, kind):
            yield kind, rel


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
        desc = module.get("description")

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
        load = module.get("load")
        if load is not None and load != "always":
            flags.append(load)

        suffix = f"  [{', '.join(flags)}]" if flags else ""
        print(f"{key}{suffix}")
        entry = entry_point(MODULES, key)
        if entry is not None:
            print(f"    source: {(Path('modules') / entry).as_posix()}")
        skills_root = MODULES / key / "skills"
        if skills_root.is_dir():
            names = sorted(p.name for p in skills_root.iterdir() if p.is_dir())
            if names:
                print(f"    skills: {', '.join(names)}")
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
    for section in ("core", "modules", "values"):
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
        if module.get("load") is not None and module["load"] not in LOAD_VALUES:
            problems.append(
                f"{key}: `load` must be `null` or one of {sorted(LOAD_VALUES)}"
            )

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
    """A module is a directory that carries something.

    Its contents live in one subdirectory per kind of file it contributes, and
    at least one of them has to be there: an empty directory is a typo, not a
    module. `load` is null exactly when the module ships no rules.
    """
    for key, module in manifest.get("modules", {}).items():
        root = MODULES / module_root(key)
        if not root.is_dir():
            problems.append(f"{key}: has no `{module_root(key)}/` directory")
            continue

        kinds = [kind for kind in KIND_DIRECTORIES if (root / kind).is_dir()]
        unknown = sorted(
            child.name
            for child in root.iterdir()
            if child.name not in KIND_DIRECTORIES
        )
        if unknown:
            problems.append(
                f"{key}: `{module_root(key)}/` holds entries that are not a "
                f"kind of file a module contributes: {', '.join(unknown)}"
            )
        if not kinds:
            problems.append(
                f"{key}: carries neither rules nor skills, so it contributes "
                "nothing"
            )

        for rel in kind_files(MODULES, key, "rules"):
            if rel.suffix != ".md":
                problems.append(
                    f"{key}: `{rel}` is under `rules/` but is not Markdown"
                )

        if not has_rules(MODULES, key):
            if module.get("load") is not None:
                problems.append(
                    f"{key}: has no rules, so `load` must be `null`"
                )
            continue
        directory = root / "rules"
        if not (directory / "INDEX.md").is_file():
            problems.append(
                f"{key}: `{module_root(key)}/rules/` must contain an `INDEX.md` "
                "as its entry point"
            )
        if module.get("load") is None:
            problems.append(f"{key}: has rules, so `load` must not be `null`")


def check_files(manifest, problems):
    """Every payload file belongs to a declared module or to core.

    Under `modules/` membership is a prefix test rather than a list of declared
    paths: a file under `<key>/` belongs to that module whatever its extension,
    so a skill's scripts and references are covered as well as its Markdown.
    `core/` holds exactly the files the manifest names.
    """
    core_files = {
        Path(name)
        for section in ("rules", "scaffold")
        for name in manifest.get("core", {}).get(section, [])
    }
    for name in sorted(core_files):
        if not (CORE / name).exists():
            problems.append(f"core: `{name}` does not exist")

    for path in sorted(CORE.rglob("*")):
        if path.is_file() and path.relative_to(CORE) not in core_files:
            problems.append(
                f"`core/{path.relative_to(CORE)}` is not named by the manifest"
            )

    declared = set(manifest.get("modules", {}))
    for path in sorted(MODULES.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(MODULES)
        parts = rel.parts
        if len(parts) < 2:
            problems.append(f"`modules/{rel}` belongs to no module")
        elif parts[0] not in declared:
            problems.append(
                f"`modules/{rel}` is under `{parts[0]}/`, which the manifest "
                "does not declare"
            )


def check_modules(manifest, problems):
    """Headings, the description, and the `.tmpl` suffix on scaffolds.

    The entry point of a module carries a `##` naming the module as a whole.
    The other files of a composite module are parts of it, so they open at
    `###` instead.

    The manifest owns the description, because a module with no rules has no
    heading to read it from. The heading stays in the rules file for the model,
    and the two are held equal here: left to drift they would not merely differ,
    they would come to mean different things.
    """
    for key, module in manifest.get("modules", {}).items():
        entry = entry_point(MODULES, key)
        for rel in rule_files(MODULES, key):
            path = MODULES / rel
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

        described = module.get("description")
        if not described:
            problems.append(f"{key}: `description` must not be empty")
        elif entry is not None:
            found = heading(MODULES / entry)
            if found is not None and found != described:
                problems.append(
                    f"{key}: `description` and the `{entry}` heading differ: "
                    f"`{described}` against `{found}`"
                )

        for rel in kind_files(MODULES, key, "scaffold"):
            if not rel.name.endswith(".tmpl.md"):
                problems.append(
                    f"{key}: scaffold `{rel}` is missing the `.tmpl` suffix"
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
