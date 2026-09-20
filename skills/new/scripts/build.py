#!/usr/bin/env python3
"""Prepare generated project files for `rulekit:new`.

Commands:
    apply    move the exact preview into the project root
    prepare  render the validated answers into the target preview

Workspace:
    <target>/.kit-preview/answers.json
    <target>/.kit-preview/files/

Exit codes:
    0  command completed
    1  requested state change was refused
    2  usage or operating system error
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

import answers
import render as project_render


FILES_DIRECTORY = "files"
STATE_FILENAME = project_render.STATE_FILENAME


CommandError = answers.CommandError
report = answers.report


def workspace_paths(raw_target, operation):
    target = answers.resolve_target(raw_target)
    preview = target / answers.PREVIEW_DIRECTORY
    path = answers.answers_path(target)
    destination = preview / FILES_DIRECTORY

    if preview.is_symlink() or not preview.is_dir():
        raise CommandError(
            1,
            f"refused to {operation} project preview: {target}",
            f"the preview workspace is not a directory: {preview}",
            "initialize a new project workspace and retry",
        )

    try:
        target_entries = {entry.name for entry in target.iterdir()}
        preview_entries = {entry.name for entry in preview.iterdir()}
    except OSError as error:
        raise CommandError(
            2,
            f"failed to inspect project workspace: {target}",
            str(error),
            "check the target path and permissions, then retry",
        )

    if not target_entries.issubset({".git", answers.PREVIEW_DIRECTORY}):
        raise CommandError(
            1,
            f"refused to {operation} project preview: {target}",
            "the target contains entries other than `.git` and `.kit-preview`",
            "use a missing, empty, or git-only target directory",
        )

    allowed = {answers.ANSWERS_FILENAME, FILES_DIRECTORY}
    unexpected = sorted(preview_entries - allowed)
    if unexpected:
        raise CommandError(
            1,
            f"refused to {operation} project preview: {target}",
            "the preview workspace contains unexpected entries: "
            f"{', '.join(unexpected)}",
            "inspect the workspace and explicitly remove the unexpected entries",
        )

    return target, preview, path, destination


def validated_inputs(raw_target):
    target, preview, path, _destination = workspace_paths(raw_target, "prepare")

    draft = answers.load_answers(path, "prepare project preview")
    modules, values = answers.load_manifest_sections(
        path, "prepare project preview", "modules", "values"
    )
    problems = project_render.specification_problems(
        draft, modules, values, require_complete=True
    )
    if problems:
        raise CommandError(
            1,
            f"refused to prepare project preview: {target}",
            "; ".join(problems),
            "complete the answers and run their check command, then retry",
        )

    return target, preview, draft, modules, values


def snapshot(directory):
    entries = {}
    try:
        for path in sorted(directory.rglob("*")):
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise CommandError(
                    2,
                    f"failed to compare project preview: {directory}",
                    f"the preview contains a non-regular file: {path}",
                    "inspect and explicitly remove the preview, then retry",
                )
            relative = path.relative_to(directory).as_posix()
            if path.is_file():
                entries[relative] = path.read_bytes()
            else:
                entries[relative] = None
    except OSError as error:
        raise CommandError(
            2,
            f"failed to compare project preview: {directory}",
            str(error),
            "check the preview path and permissions, then retry",
        )
    return entries


def install_preview(staging, destination):
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_dir():
            raise CommandError(
                1,
                f"refused to replace project preview: {destination}",
                "the preview files path is not a regular directory",
                "inspect and explicitly remove it, then retry",
            )
        if snapshot(staging) == snapshot(destination):
            shutil.rmtree(staging)
            return
        shutil.rmtree(destination)
    os.replace(staging, destination)


def validate_state(path):
    state = answers.read_json(
        path,
        "preview state",
        "run prepare again before applying the preview",
        missing_exit_code=1,
    )
    if not isinstance(state, dict) or set(state) != {"kit", "modules", "values"}:
        raise CommandError(
            2,
            f"failed to validate preview state: {path}",
            "the state must contain exactly `kit`, `modules`, and `values`",
            "run prepare again before applying the preview",
        )
    kit = state["kit"]
    if not isinstance(kit, dict) or set(kit) != {"commit"}:
        commit = None
    else:
        commit = kit["commit"]
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise CommandError(
            2,
            f"failed to validate preview state: {path}",
            "`kit.commit` must be a full lowercase Git commit hash",
            "run prepare again before applying the preview",
        )
    modules = state["modules"]
    if (
        not isinstance(modules, list)
        or not all(isinstance(name, str) for name in modules)
        or modules != sorted(set(modules))
    ):
        raise CommandError(
            2,
            f"failed to validate preview state: {path}",
            "`modules` must be a sorted list of unique strings",
            "run prepare again before applying the preview",
        )
    if not isinstance(state["values"], dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in state["values"].items()
    ):
        raise CommandError(
            2,
            f"failed to validate preview state: {path}",
            "`values` must be an object with string keys and values",
            "run prepare again before applying the preview",
        )


def rollback_moves(moved):
    failures = []
    for destination, source in reversed(moved):
        try:
            os.replace(destination, source)
        except OSError as error:
            failures.append(f"{destination}: {error}")
    return failures


def cmd_apply(raw_target):
    target, preview, path, source_root = workspace_paths(raw_target, "apply")

    if path.is_symlink() or not path.is_file():
        raise CommandError(
            1,
            f"refused to apply project preview: {target}",
            f"the answers file is not a regular file: {path}",
            "initialize and prepare a new project workspace",
        )
    if source_root.is_symlink() or not source_root.is_dir():
        raise CommandError(
            1,
            f"refused to apply project preview: {target}",
            f"the prepared files directory is missing or invalid: {source_root}",
            "run prepare before applying the preview",
        )

    generated_entries = snapshot(source_root)
    generated_file_count = sum(
        content is not None for content in generated_entries.values()
    )
    state_source = source_root / STATE_FILENAME
    validate_state(state_source)

    reserved = sorted(
        relative
        for relative in generated_entries
        if {".git", answers.PREVIEW_DIRECTORY}.intersection(
            Path(relative).parts
        )
    )
    if reserved:
        raise CommandError(
            1,
            f"refused to apply project preview: {target}",
            f"the preview contains reserved target paths: {', '.join(reserved)}",
            "fix the generator and run prepare again",
        )

    try:
        top_level = sorted(
            (item for item in source_root.iterdir() if item.name != STATE_FILENAME),
            key=lambda item: item.name,
        )
    except OSError as error:
        raise CommandError(
            2,
            f"failed to inspect project preview: {source_root}",
            str(error),
            "check the preview path and permissions, then retry",
        )

    moves = [(source, target / source.name) for source in top_level]
    moves.append((state_source, target / STATE_FILENAME))
    conflicts = sorted(
        destination.name
        for _source, destination in moves
        if os.path.lexists(destination)
    )
    if conflicts:
        raise CommandError(
            1,
            f"refused to apply project preview: {target}",
            f"target paths appeared after validation: {', '.join(conflicts)}",
            "inspect the target and retry with a missing, empty, or git-only directory",
        )

    moved = []
    try:
        for source, destination in moves:
            os.replace(source, destination)
            moved.append((destination, source))
    except OSError as error:
        rollback_failures = rollback_moves(moved)
        if rollback_failures:
            raise CommandError(
                2,
                f"failed to apply and fully roll back project preview: {target}",
                f"{error}; rollback failures: {'; '.join(rollback_failures)}",
                "inspect both the project root and preview before continuing",
            )
        raise CommandError(
            2,
            f"failed to apply project preview: {target}",
            f"{error}; moved paths were restored to the preview",
            "check the target path and permissions, then retry",
        )

    try:
        source_root.rmdir()
        path.unlink()
        preview.rmdir()
    except OSError as error:
        raise CommandError(
            2,
            f"applied project files but failed to remove preview workspace: {target}",
            str(error),
            "verify the generated project, then remove the preview explicitly",
        )

    report(
        f"applied project preview: {target}",
        f"moved {generated_file_count} generated file(s) and wrote .kit.json last",
        "continue work in the generated project",
    )
    return 0


def cmd_prepare(raw_target):
    target, preview, draft, modules, values = validated_inputs(raw_target)
    commit, changed_sources = project_render.kit_version(answers.KIT)
    staging = Path(tempfile.mkdtemp(dir=preview, prefix=".files."))
    destination = preview / FILES_DIRECTORY

    try:
        rendered = project_render.render_tree(
            answers.KIT,
            staging,
            draft,
            modules,
            values,
            commit,
        )
        install_preview(staging, destination)
        staging = None
    except OSError as error:
        raise CommandError(
            2,
            f"failed to prepare project preview: {destination}",
            str(error),
            "check the target path and permissions, then retry",
        )
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)

    reason = (
        "rendered CLAUDE.md and PROJECT.md, copied "
        f"{rendered['copied_rules']} rule file(s) and "
        f"{rendered['copied_scaffolds']} scaffold file(s), created "
        f"{rendered['repositories']} inner repository directory(s), and wrote "
        ".kit.json"
    )
    if rendered["uses_git"]:
        reason += " and .gitignore"
    next_step = "inspect the exact preview before applying it"
    if changed_sources:
        reason += (
            "; warning: .kit.json records HEAD although managed kit sources "
            f"differ from it: {', '.join(changed_sources)}"
        )
        next_step = (
            "inspect the exact preview; commit the kit sources and run prepare "
            "again before treating kit.commit as a reproducible baseline"
        )

    report(f"prepared project preview: {destination}", reason, next_step)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--target", required=True, help="future project directory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("apply", help="move the exact preview into the project root")
    commands.add_parser("prepare", help="render the project preview")

    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    args = parser.parse_args()

    try:
        if args.command == "apply":
            return cmd_apply(args.target)
        if args.command == "prepare":
            return cmd_prepare(args.target)
    except CommandError as error:
        report(error.result, error.reason, error.next_step, stream=sys.stderr)
        return error.exit_code

    parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
