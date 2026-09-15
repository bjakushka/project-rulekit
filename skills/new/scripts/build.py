#!/usr/bin/env python3
"""Prepare generated project files for `rulekit:new`.

Commands:
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
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

import answers


FILES_DIRECTORY = "files"
STATE_FILENAME = ".kit.json"
IMPORTS_START = "<!-- kit:imports -->"
IMPORTS_END = "<!-- /kit:imports -->"
PLACEHOLDER = re.compile(r"{{([A-Z][A-Z0-9_]*)}}")


CommandError = answers.CommandError
report = answers.report


def run_git(*arguments):
    try:
        completed = subprocess.run(
            ["git", "-C", str(answers.KIT), *arguments],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as error:
        raise CommandError(
            2,
            "failed to read the current kit version",
            str(error),
            "make Git available and retry",
        )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise CommandError(
            2,
            "failed to read the current kit version",
            detail or f"Git exited with status {completed.returncode}",
            "check that the plugin is inside its Git repository and retry",
        )
    return completed.stdout


def kit_commit():
    changed = run_git(
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        "manifest.json",
        "template",
    ).strip()
    if changed:
        paths = sorted(line[3:] for line in changed.splitlines())
        raise CommandError(
            1,
            "refused to prepare a project preview",
            f"managed kit sources differ from HEAD: {', '.join(paths)}",
            "commit or restore the manifest and templates, then retry",
        )
    return run_git("rev-parse", "--verify", "HEAD").strip()


def validated_inputs(raw_target):
    target = answers.resolve_target(raw_target)
    preview = target / answers.PREVIEW_DIRECTORY
    path = answers.answers_path(target)

    if preview.is_symlink() or not preview.is_dir():
        raise CommandError(
            1,
            f"refused to prepare project preview: {target}",
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
            f"refused to prepare project preview: {target}",
            "the target contains entries other than `.git` and `.kit-preview`",
            "use a missing, empty, or git-only target directory",
        )

    allowed = {answers.ANSWERS_FILENAME, FILES_DIRECTORY}
    unexpected = sorted(preview_entries - allowed)
    if unexpected:
        raise CommandError(
            1,
            f"refused to prepare project preview: {target}",
            "the preview workspace contains unexpected entries: "
            f"{', '.join(unexpected)}",
            "inspect the workspace and explicitly remove the unexpected entries",
        )

    draft = answers.load_answers(path, "prepare project preview")
    modules, values = answers.load_manifest_sections(
        path, "prepare project preview", "modules", "values"
    )
    problems = [
        reason
        for reason, _next_step in answers.module_selection_problems(
            modules, draft["modules"], require_complete=True
        )
    ]
    problems.extend(answers.value_problems(values, draft["values"]))
    if problems:
        raise CommandError(
            1,
            f"refused to prepare project preview: {target}",
            "; ".join(problems),
            "complete the answers and run their check command, then retry",
        )

    return target, preview, draft, modules, values


def module_rule_files(module):
    directory = answers.KIT / "template" / "rules" / module
    if directory.is_dir():
        return sorted(directory.glob("*.md"))
    return [directory.with_suffix(".md")]


def module_entry_point(module):
    directory = answers.KIT / "template" / "rules" / module
    if directory.is_dir():
        return Path("rules") / module / "INDEX.md"
    return Path("rules") / f"{module}.md"


def resolved_values(declarations, stored):
    values = {}
    for key in sorted(declarations):
        if key in stored:
            values[key] = stored[key]
        elif declarations[key].get("default") is not None:
            values[key] = declarations[key]["default"]
    return values


def render_claude(
    template, modules, values, module_declarations, value_declarations
):
    text = template.read_text(encoding="utf-8")
    rendered_values = resolved_values(value_declarations, values)

    for key, value in rendered_values.items():
        text = text.replace(f"{{{{{key}}}}}", value)

    remaining = sorted(set(PLACEHOLDER.findall(text)))
    if remaining:
        raise CommandError(
            2,
            "failed to render CLAUDE.md",
            f"template placeholders have no value: {', '.join(remaining)}",
            "declare and collect every template value, then retry",
        )

    imports = [
        f"@{module_entry_point(name).as_posix()}"
        for name in modules
        if module_declarations[name].get("load") == "always"
    ]
    block = "\n".join([IMPORTS_START, *sorted(imports), IMPORTS_END])
    pattern = re.compile(
        rf"^{re.escape(IMPORTS_START)}$.*?^{re.escape(IMPORTS_END)}$",
        flags=re.MULTILINE | re.DOTALL,
    )
    text, replacements = pattern.subn(block, text)
    if replacements != 1:
        raise CommandError(
            2,
            "failed to render CLAUDE.md",
            "the template must contain exactly one complete `kit:imports` block",
            "restore or fix template/CLAUDE.md, then retry",
        )
    return text, rendered_values


def snapshot(directory):
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise CommandError(
                2,
                f"failed to compare project preview: {directory}",
                f"the preview contains a non-regular file: {path}",
                "inspect and explicitly remove the preview, then retry",
            )
        if path.is_file():
            files[path.relative_to(directory).as_posix()] = path.read_bytes()
    return files


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


def cmd_prepare(raw_target):
    target, preview, draft, modules, values = validated_inputs(raw_target)
    commit = kit_commit()
    staging = Path(tempfile.mkdtemp(dir=preview, prefix=".files."))
    destination = preview / FILES_DIRECTORY

    try:
        claude, values = render_claude(
            answers.KIT / "template" / "CLAUDE.md",
            draft["modules"],
            draft["values"],
            modules,
            values,
        )
        (staging / "CLAUDE.md").write_text(claude, encoding="utf-8")

        copied = 0
        for module in draft["modules"]:
            for source in module_rule_files(module):
                relative = source.relative_to(answers.KIT / "template")
                output = staging / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, output)
                copied += 1

        state = {
            "kit": {"commit": commit},
            "modules": sorted(draft["modules"]),
            "values": values,
        }
        with (staging / STATE_FILENAME).open("w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")

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

    report(
        f"prepared project preview: {destination}",
        f"rendered CLAUDE.md, {copied} module rule file(s), and .kit.json",
        "inspect the exact preview before applying it",
    )
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--target", required=True, help="future project directory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare", help="render the project preview")

    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    args = parser.parse_args()

    try:
        if args.command == "prepare":
            return cmd_prepare(args.target)
    except CommandError as error:
        report(error.result, error.reason, error.next_step, stream=sys.stderr)
        return error.exit_code

    parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
