#!/usr/bin/env python3
"""Build and validate temporary interview answers for `rulekit:new`.

Commands:
    brief   show or replace one project brief answer
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
import re
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
    "brief": {
        "context": None,
        "repositories": [],
    },
    "modules": [],
    "values": {},
}

BRIEF_KEYS = ("context", "repositories")
RESERVED_TARGET_PATHS = (
    ".git",
    ".gitignore",
    ".kit-preview",
    ".kit.json",
    "CLAUDE.md",
    "PROJECT.md",
    "rules",
)


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
    if set(answers) != {"brief", "modules", "values"}:
        return (
            "the answers document must contain exactly `brief`, `modules`, "
            "and `values`"
        )
    if not isinstance(answers["brief"], dict):
        return "`brief` must be a JSON object"
    if set(answers["brief"]) != set(BRIEF_KEYS):
        return "`brief` must contain exactly `context` and `repositories`"
    if answers["brief"]["context"] is not None and not isinstance(
        answers["brief"]["context"], str
    ):
        return "`brief.context` must be a string or null"
    repositories = answers["brief"]["repositories"]
    if not isinstance(repositories, list):
        return "`brief.repositories` must be a JSON array"
    for repository in repositories:
        if not isinstance(repository, dict) or set(repository) != {"path", "purpose"}:
            return (
                "every `brief.repositories` entry must contain exactly `path` "
                "and `purpose`"
            )
        if not all(isinstance(repository[key], str) for key in ("path", "purpose")):
            return "repository paths and purposes must be strings"
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
    choices = declaration.get("choices")
    if choices is not None and value not in choices:
        return (
            f"value `{key}` is not supported: {value}; "
            f"choose from: {', '.join(choices)}"
        )
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


def scaffold_output_path(name):
    path = Path(name)
    suffix = ".tmpl.md"
    if path.is_absolute() or ".." in path.parts or not path.name.endswith(suffix):
        raise CommandError(
            2,
            "failed to validate project brief",
            f"invalid scaffold template path in the manifest: {name}",
            "run `python3 scripts/manifest.py check` and fix the manifest",
        )
    return path.with_name(f"{path.name[:-len(suffix)]}.md")


def normalize_repository_path(raw_path):
    path = raw_path.strip().rstrip("/")
    if not path:
        return None, "repository path is empty"
    if path.startswith("/") or "\\" in path:
        return None, f"repository path must be relative and use `/`: {raw_path}"
    if any(ord(character) < 32 for character in path):
        return None, f"repository path contains a control character: {raw_path}"

    parts = path.split("/")
    if any(part in ("", ".", "..", "~") for part in parts):
        return None, f"repository path is not normalized or safe: {raw_path}"
    if re.match(r"^[A-Za-z]:", parts[0]):
        return None, f"repository path must not use a drive prefix: {raw_path}"
    return "/".join(parts), None


def path_parts(path):
    return tuple(part.casefold() for part in path.split("/"))


def paths_overlap(left, right):
    left_parts = path_parts(left)
    right_parts = path_parts(right)
    common = min(len(left_parts), len(right_parts))
    return left_parts[:common] == right_parts[:common]


def generated_target_paths(modules, selected_modules):
    generated = set(RESERVED_TARGET_PATHS)
    for name in selected_modules:
        module = modules.get(name)
        if module is None:
            continue
        for scaffold in module.get("scaffold", []):
            generated.add(scaffold_output_path(scaffold).as_posix())
    return sorted(generated)


def brief_problems(brief, modules, selected_modules, require_complete=False):
    problems = []
    context = brief["context"]
    if require_complete and (context is None or not context.strip()):
        problems.append("project brief context is missing or empty")
    elif isinstance(context, str) and not context.strip():
        problems.append("project brief context is empty")

    repositories = brief["repositories"]
    if require_complete and not repositories:
        problems.append("project brief has no inner repositories")

    normalized = []
    for repository in repositories:
        path, problem = normalize_repository_path(repository["path"])
        if problem:
            problems.append(problem)
            continue
        if path != repository["path"]:
            problems.append(f"repository path is not normalized: {repository['path']}")
        if not repository["purpose"].strip():
            problems.append(f"repository purpose is empty: {repository['path']}")
        normalized.append(path)

    for index, path in enumerate(normalized):
        for other in normalized[index + 1:]:
            if paths_overlap(path, other):
                problems.append(f"repository paths overlap: {path}, {other}")

    reserved = generated_target_paths(modules, selected_modules)
    for path in normalized:
        conflicts = [
            candidate for candidate in reserved if paths_overlap(path, candidate)
        ]
        if conflicts:
            problems.append(
                f"repository path `{path}` conflicts with generated or reserved "
                f"path: {conflicts[0]}"
            )
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
        "init created a new document with an empty brief, modules, and values",
        "collect project brief, module, and value answers",
    )
    return 0


def cmd_brief_list():
    print("context")
    print("    usage: brief context <text...>")
    print("    Concise English orientation for a future assistant.")
    print("repositories")
    print(
        "    usage: brief repositories --repo <relative-path> <purpose> "
        "[--repo ...]"
    )
    print("    One or more inner repositories, each with a concise purpose.")
    return 0


def refuse_brief(path, reason, next_step):
    raise CommandError(
        1,
        f"refused to update project brief in answers file: {path}",
        reason,
        next_step,
    )


def cmd_brief(raw_target, key, values, repositories):
    path = answers_path(raw_target)
    answers = load_answers(path, "update project brief")
    (modules,) = load_manifest_sections(path, "update project brief", "modules")

    if key not in BRIEF_KEYS:
        return refuse_brief(
            path,
            f"unknown project brief key: {key}",
            f"choose from: {', '.join(BRIEF_KEYS)}",
        )

    if key == "context":
        if repositories:
            return refuse_brief(
                path,
                "`context` does not accept `--repo` arguments",
                "pass the concise English context as positional text",
            )
        context = " ".join(values).strip()
        if not context:
            return refuse_brief(
                path,
                "project brief context is empty",
                "provide concise English orientation text",
            )
        answers["brief"]["context"] = context
    else:
        if values:
            return refuse_brief(
                path,
                "`repositories` accepts only repeated `--repo` arguments",
                "use `--repo <relative-path> <purpose>` for every repository",
            )
        if not repositories:
            return refuse_brief(
                path,
                "project brief has no inner repositories",
                "provide at least one `--repo <relative-path> <purpose>` argument",
            )

        updated = []
        for raw_path, raw_purpose in repositories:
            repository_path, problem = normalize_repository_path(raw_path)
            if problem:
                return refuse_brief(path, problem, "provide a safe relative path")
            purpose = raw_purpose.strip()
            if not purpose:
                return refuse_brief(
                    path,
                    f"repository purpose is empty: {raw_path}",
                    "provide a non-empty purpose for every repository",
                )
            updated.append({"path": repository_path, "purpose": purpose})
        answers["brief"]["repositories"] = sorted(
            updated, key=lambda repository: repository["path"].casefold()
        )

    problems = brief_problems(
        answers["brief"], modules, answers["modules"], require_complete=False
    )
    if problems:
        return refuse_brief(path, problems[0], "correct the project brief and retry")

    save_answers(path, answers, "update project brief")
    report(
        f"updated project brief `{key}` in answers file: {path}",
        "the answer satisfies the project brief contract",
        "set remaining answers or check the answers",
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
        choices = values[key].get("choices")
        next_step = (
            f"choose from: {', '.join(choices)}"
            if choices is not None
            else "provide a non-empty value and retry"
        )
        return refuse_value(
            path,
            problem,
            next_step,
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
    problems.extend(
        brief_problems(
            answers["brief"],
            modules,
            answers["modules"],
            require_complete=True,
        )
    )

    if problems:
        print(f"result: answers file is incomplete: {path}", file=sys.stderr)
        print("reason:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        print("next: fix every listed problem and run check again", file=sys.stderr)
        return 1

    report(
        f"answers file is complete: {path}",
        "the project brief, modules, and values satisfy the current kit contract",
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
    brief = commands.add_parser("brief", help="show or replace a project brief answer")
    brief.add_argument("--list", action="store_true", help="show the brief contract")
    brief.add_argument("key", nargs="?", help="brief answer key")
    brief.add_argument("values", nargs="*", help="brief answer text")
    brief.add_argument(
        "--repo",
        action="append",
        default=[],
        nargs=2,
        metavar=("PATH", "PURPOSE"),
        help="inner repository path and purpose",
    )
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
        if args.command == "brief":
            if args.list:
                if args.key is not None or args.values or args.repo:
                    parser.error("brief --list does not accept a key or values")
                return cmd_brief_list()
            if args.key is None:
                parser.error("brief requires a key or --list")
            return cmd_brief(args.target, args.key, args.values, args.repo)
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
