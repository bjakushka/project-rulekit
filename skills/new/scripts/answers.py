#!/usr/bin/env python3
"""Build and validate temporary interview answers for `rulekit:new`.

Commands:
    check   validate that the answers are complete
    init    create the target workspace and a new empty answers file
    modules replace the selected module list
    value   set one declared value

Workspace:
    <target>/.kit-preview/answers.json

Exit codes:
    0  command completed
    1  requested state change was refused
    2  usage or operating system error
"""

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
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
PREVIEW_DIRECTORY = ".kit-preview"
ANSWERS_FILENAME = "answers.json"

EMPTY_ANSWERS = {
    "modules": [],
    "values": {},
}


class CommandError(Exception):
    def __init__(self, exit_code, result, reason, next_step):
        super().__init__(reason)
        self.exit_code = exit_code
        self.result = result
        self.reason = reason
        self.next_step = next_step


def report(result, reason, next_step, stream=sys.stdout):
    print(f"result: {result}", file=stream)
    print(f"reason: {reason}", file=stream)
    print(f"next: {next_step}", file=stream)


def resolve_target(raw_target):
    return Path(raw_target).expanduser().resolve()


def answers_path(raw_target):
    return resolve_target(raw_target) / PREVIEW_DIRECTORY / ANSWERS_FILENAME


def report_existing(target, preview):
    raise CommandError(
        1,
        f"refused to initialize project workspace: {target}",
        f"the preview workspace already exists: {preview}",
        "inspect it, then explicitly remove it before starting again",
    )


def read_json(path, subject, recovery, missing_exit_code=2):
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        outcome = "refused" if missing_exit_code == 1 else "failed"
        raise CommandError(
            missing_exit_code,
            f"{outcome} to read {subject}: {path}",
            f"the {subject} does not exist",
            recovery,
        )
    except json.JSONDecodeError as error:
        raise CommandError(
            2,
            f"failed to read {subject}: {path}",
            f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}",
            recovery,
        )
    except OSError as error:
        raise CommandError(
            2,
            f"failed to read {subject}: {path}",
            str(error),
            recovery,
        )


def write_replacement(path, data):
    temporary_path = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def validate_answers(answers):
    if not isinstance(answers, dict):
        return "the answers document must be a JSON object"
    if set(answers) != {"modules", "values"}:
        return "the answers document must contain exactly `modules` and `values`"
    if not isinstance(answers["modules"], list):
        return "`modules` must be a JSON array"
    if not isinstance(answers["values"], dict):
        return "`values` must be a JSON object"
    return None


def load_answers(path, operation):
    answers = read_json(
        path,
        "answers file",
        "run init if it is missing; otherwise repair it or choose another path",
        missing_exit_code=1,
    )
    problem = validate_answers(answers)
    if problem:
        raise CommandError(
            2,
            f"failed to {operation} in answers file: {path}",
            problem,
            "repair the file or initialize a new answers file",
        )
    return answers


def load_manifest_sections(path, operation, *sections):
    manifest = read_json(
        MANIFEST,
        "kit manifest",
        "run `python3 scripts/manifest.py check` and restore or fix the manifest",
    )
    if not isinstance(manifest, dict):
        raise CommandError(
            2,
            f"failed to {operation} in answers file: {path}",
            "the kit manifest must be a JSON object",
            "run `python3 scripts/manifest.py check` and fix the manifest",
        )

    found = []
    for section in sections:
        declarations = manifest.get(section)
        if not isinstance(declarations, dict):
            raise CommandError(
                2,
                f"failed to {operation} in answers file: {path}",
                f"the kit manifest does not contain a valid `{section}` object",
                "run `python3 scripts/manifest.py check` and fix the manifest",
            )
        invalid = sorted(
            key for key, declaration in declarations.items()
            if not isinstance(declaration, dict)
        )
        if invalid:
            raise CommandError(
                2,
                f"failed to {operation} in answers file: {path}",
                f"manifest `{section}` entries must be objects: {', '.join(invalid)}",
                "run `python3 scripts/manifest.py check` and fix the manifest",
            )
        found.append(declarations)
    return found


def save_answers(path, answers, operation):
    try:
        write_replacement(path, answers)
    except OSError as error:
        raise CommandError(
            2,
            f"failed to {operation} in answers file: {path}",
            str(error),
            "check the path and permissions, then retry",
        )


def module_selection_problems(modules, selected, require_complete=False):
    if not all(isinstance(name, str) for name in selected):
        return [("module names must be strings", "replace invalid module names")]

    problems = []
    duplicates = sorted(
        name for name, count in Counter(selected).items() if count > 1
    )
    if duplicates:
        problems.append(
            (
                f"module names were repeated: {', '.join(duplicates)}",
                "pass every selected module exactly once",
            )
        )

    unknown = sorted(set(selected) - set(modules))
    if unknown:
        problems.append(
            (
                f"unknown modules: {', '.join(unknown)}",
                f"choose from: {', '.join(sorted(modules))}",
            )
        )

    selected_set = set(selected)
    if require_complete:
        required = sorted(
            name
            for name, module in modules.items()
            if module.get("required") and module.get("group") is None
        )
        missing = sorted(set(required) - selected_set)
        if missing:
            problems.append(
                (
                    f"required modules are missing: {', '.join(missing)}",
                    "add the missing modules and retry",
                )
            )

    groups = {}
    for name, module in modules.items():
        group = module.get("group")
        if group is not None:
            groups.setdefault(group, []).append(name)

    for group in sorted(groups):
        members = sorted(groups[group])
        chosen = sorted(selected_set.intersection(members))
        required_group = any(modules[name].get("required") for name in members)
        if len(chosen) > 1:
            problems.append(
                (
                    f"group `{group}` allows one module but selected: "
                    f"{', '.join(chosen)}",
                    f"choose one of: {', '.join(members)}",
                )
            )
        elif require_complete and required_group and not chosen:
            problems.append(
                (
                    f"required group `{group}` has no selected module",
                    f"choose one of: {', '.join(members)}",
                )
            )

    return problems


def stored_value_problem(key, value, declaration):
    if not isinstance(value, str):
        return f"value `{key}` must be a string"
    if declaration.get("required") and not value.strip():
        return f"required value is empty: {key}"
    return None


def value_problems(values, selected):
    problems = []
    unknown = sorted(set(selected) - set(values))
    if unknown:
        problems.append(f"unknown value keys: {', '.join(unknown)}")

    required = sorted(
        key for key, declaration in values.items()
        if declaration.get("required")
    )
    missing = sorted(set(required) - set(selected))
    if missing:
        problems.append(f"required values are missing: {', '.join(missing)}")

    for key in sorted(set(selected).intersection(values)):
        problem = stored_value_problem(key, selected[key], values[key])
        if problem:
            problems.append(problem)
    return problems


def cmd_init(raw_target):
    target = resolve_target(raw_target)
    preview = target / PREVIEW_DIRECTORY
    path = preview / ANSWERS_FILENAME

    if os.path.lexists(preview):
        report_existing(target, preview)

    if os.path.lexists(target) and not target.is_dir():
        raise CommandError(
            1,
            f"refused to initialize project workspace: {target}",
            "the target exists and is not a directory",
            "choose a missing, empty, or git-only target directory",
        )

    if target.is_dir():
        try:
            entries = {entry.name for entry in target.iterdir()}
        except OSError as error:
            raise CommandError(
                2,
                f"failed to inspect target directory: {target}",
                str(error),
                "check the target path and permissions, then retry",
            )
        if entries not in (set(), {".git"}):
            raise CommandError(
                1,
                f"refused to initialize project workspace: {target}",
                "the target contains entries other than `.git`",
                "choose a missing, empty, or git-only target directory",
            )

    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise CommandError(
            2,
            f"failed to create target directory: {target}",
            str(error),
            "check the target path and permissions, then retry",
        )

    try:
        preview.mkdir()
    except FileExistsError:
        report_existing(target, preview)
    except OSError as error:
        raise CommandError(
            2,
            f"failed to create preview workspace: {preview}",
            str(error),
            "check the target path and permissions, then retry",
        )

    temporary_path = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=preview,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                EMPTY_ANSWERS,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        try:
            os.link(temporary_path, path)
        except FileExistsError:
            report_existing(target, preview)
    except OSError as error:
        raise CommandError(
            2,
            f"failed to initialize answers file: {path}",
            str(error),
            "check the path and permissions, then retry",
        )
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass

    report(
        f"initialized answers file: {path}",
        "init created a new document with empty modules and values",
        "collect module and value answers",
    )
    return 0


def refuse_modules(path, reason, next_step):
    raise CommandError(
        1,
        f"refused to update modules in answers file: {path}",
        reason,
        next_step,
    )


def cmd_modules(raw_target, selected):
    path = answers_path(raw_target)
    answers = load_answers(path, "update modules")
    (modules,) = load_manifest_sections(path, "update modules", "modules")

    problems = module_selection_problems(modules, selected)
    if problems:
        reason, next_step = problems[0]
        return refuse_modules(path, reason, next_step)

    answers["modules"] = sorted(selected)
    save_answers(path, answers, "update modules")

    report(
        f"updated modules in answers file: {path}",
        "the draft contains only known modules and at most one from each group",
        "continue the interview and run check when the answers should be complete",
    )
    return 0


def refuse_value(path, reason, next_step):
    raise CommandError(
        1,
        f"refused to update value in answers file: {path}",
        reason,
        next_step,
    )


def cmd_value(raw_target, key, value):
    path = answers_path(raw_target)
    answers = load_answers(path, "update value")
    (values,) = load_manifest_sections(path, "update value", "values")

    if key not in values:
        return refuse_value(
            path,
            f"unknown value key: {key}",
            f"choose from: {', '.join(sorted(values))}",
        )

    problem = stored_value_problem(key, value, values[key])
    if problem:
        return refuse_value(
            path,
            problem,
            "provide a non-empty value and retry",
        )

    answers["values"][key] = value
    save_answers(path, answers, "update value")

    report(
        f"updated value `{key}` in answers file: {path}",
        "the key is declared by the kit manifest and the value is valid",
        "set remaining values or check the answers",
    )
    return 0


def cmd_check(raw_target):
    path = answers_path(raw_target)
    answers = load_answers(path, "check answers")
    modules, values = load_manifest_sections(
        path, "check answers", "modules", "values"
    )

    problems = [
        reason
        for reason, _next_step in module_selection_problems(
            modules, answers["modules"], require_complete=True
        )
    ]
    problems.extend(value_problems(values, answers["values"]))

    if problems:
        print(f"result: answers file is incomplete: {path}", file=sys.stderr)
        print("reason:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        print("next: fix every listed problem and run check again", file=sys.stderr)
        return 1

    report(
        f"answers file is complete: {path}",
        "modules and values satisfy the current kit manifest",
        "prepare the generated project",
    )
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--target", required=True, help="future project directory"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="validate that the answers are complete")
    commands.add_parser("init", help="create a new empty answers file")
    modules = commands.add_parser("modules", help="replace the selected modules")
    modules.add_argument("names", nargs="*", help="complete module selection")
    value = commands.add_parser("value", help="set one declared value")
    value.add_argument("key", help="declared value name")
    value.add_argument("value", help="value to store")

    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    args = parser.parse_args()

    try:
        if args.command == "check":
            return cmd_check(args.target)
        if args.command == "init":
            return cmd_init(args.target)
        if args.command == "modules":
            return cmd_modules(args.target, args.names)
        if args.command == "value":
            return cmd_value(args.target, args.key, args.value)
    except CommandError as error:
        report(error.result, error.reason, error.next_step, stream=sys.stderr)
        return error.exit_code

    parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
