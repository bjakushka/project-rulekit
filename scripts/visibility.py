#!/usr/bin/env python3
"""Report which files Rulekit created in a project git does not see.

The expected files come from the kit and the project's `.kit.json`: the core
files, and every rule, scaffold and skill of each selected module. A file that
no longer exists is skipped. Only the outer repository is asked; the inner
repositories are ignored by it on purpose.

The report says which files are ignored, never why.

Exit codes:
    0  git sees every existing Rulekit file
    1  git ignores at least one of them
    2  usage or operating system error
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import answers
import render as project_render


CORE_FILES = (
    "CLAUDE.md",
    "PROJECT.md",
    project_render.STATE_FILENAME,
    ".gitignore",
)


CommandError = answers.CommandError
report = answers.report


def selected_modules(target):
    path = target / project_render.STATE_FILENAME
    try:
        with path.open(encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise CommandError(
            2,
            f"failed to read project state: {path}",
            str(error),
            "run this against a Rulekit project with a readable .kit.json",
        )
    modules = state.get("modules") if isinstance(state, dict) else None
    if not isinstance(modules, list) or not all(
        isinstance(module, str) for module in modules
    ):
        raise CommandError(
            2,
            f"failed to read project state: {path}",
            "`modules` is not a list of module names",
            "repair .kit.json, then retry",
        )
    return modules


def expected_files(kit_root, modules):
    """Every path Rulekit writes into a project, relative to its root."""
    paths = [Path(name) for name in CORE_FILES]
    for module in modules:
        for source in project_render.module_rule_files(kit_root, module):
            paths.append(project_render.module_rule_target(module, source.name))
        for name in project_render.module_scaffold_files(kit_root, module):
            paths.append(project_render.scaffold_output_path(name))
        for name in project_render.module_skill_files(kit_root, module):
            paths.append(project_render.module_skill_target(name))
    return paths


def ignored_files(target, paths):
    try:
        completed = subprocess.run(
            ["git", "-C", str(target), "check-ignore", "--", *map(str, paths)],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as error:
        raise CommandError(
            2,
            f"failed to ask git about project files: {target}",
            str(error),
            "make Git available and retry",
        )
    if completed.returncode not in (0, 1):
        raise CommandError(
            2,
            f"failed to ask git about project files: {target}",
            completed.stderr.strip() or completed.stdout.strip(),
            "run this against a project whose root is a Git repository",
        )
    return completed.stdout.splitlines()


def check(raw_target):
    target = answers.resolve_target(raw_target)
    modules = selected_modules(target)
    existing = [
        path
        for path in expected_files(answers.KIT, modules)
        if (target / path).is_file()
    ]
    ignored = ignored_files(target, existing) if existing else []

    if not ignored:
        report(
            f"git sees every Rulekit file: {target}",
            f"checked {len(existing)} existing file(s)",
            "nothing to do",
        )
        return 0

    report(
        f"git ignores {len(ignored)} Rulekit file(s): {target}",
        "ignored: " + ", ".join(ignored),
        "decide whether each of them should be tracked",
    )
    return 1


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--target", required=True, help="project directory")
    args = parser.parse_args()

    try:
        return check(args.target)
    except CommandError as error:
        report(error.result, error.reason, error.next_step, stream=sys.stderr)
        return error.exit_code


if __name__ == "__main__":
    sys.exit(main())
