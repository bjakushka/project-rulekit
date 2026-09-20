#!/usr/bin/env python3
"""Render validated adoption answers into a clean Rulekit preview."""

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path


def find_kit_root(start):
    for directory in (start, *start.parents):
        if (
            (directory / ".claude-plugin" / "plugin.json").is_file()
            and (directory / "manifest.json").is_file()
        ):
            return directory
    raise RuntimeError(f"could not find the rulekit plugin root above: {start}")


KIT = find_kit_root(Path(__file__).resolve().parent)
sys.path.insert(0, str(KIT / "scripts"))
sys.dont_write_bytecode = True

import answers
import render as project_render


FILES_DIRECTORY = "files"
CommandError = answers.CommandError
report = answers.report


def validated_inputs(raw_target):
    target = answers.resolve_target(raw_target)
    preview = target / answers.PREVIEW_DIRECTORY
    path = answers.answers_path(target)
    destination = preview / FILES_DIRECTORY

    if not target.is_dir():
        raise CommandError(
            1,
            f"refused to prepare adoption preview: {target}",
            "the adoption target does not exist or is not a directory",
            "choose an existing project directory",
        )
    if os.path.lexists(target / project_render.STATE_FILENAME):
        raise CommandError(
            1,
            f"refused to prepare adoption preview: {target}",
            "the project already has Rulekit state",
            "use the future sync workflow instead of adopt",
        )
    if preview.is_symlink() or not preview.is_dir():
        raise CommandError(
            1,
            f"refused to prepare adoption preview: {target}",
            f"the preview workspace is missing or invalid: {preview}",
            "initialize adoption answers and retry",
        )

    try:
        preview_entries = {entry.name for entry in preview.iterdir()}
    except OSError as error:
        raise CommandError(
            2,
            f"failed to inspect adoption workspace: {target}",
            str(error),
            "check the target path and permissions, then retry",
        )

    allowed = {answers.ANSWERS_FILENAME, FILES_DIRECTORY}
    unexpected = sorted(preview_entries - allowed)
    if unexpected:
        raise CommandError(
            1,
            f"refused to prepare adoption preview: {target}",
            "the preview workspace contains unexpected entries: "
            f"{', '.join(unexpected)}",
            "inspect the workspace and explicitly remove unexpected entries",
        )
    if os.path.lexists(destination):
        raise CommandError(
            1,
            f"refused to prepare adoption preview: {target}",
            f"the prepared files path already exists: {destination}",
            "inspect the existing preview before preparing again",
        )
    if path.is_symlink() or not path.is_file():
        raise CommandError(
            1,
            f"refused to prepare adoption preview: {target}",
            f"the answers file is missing or invalid: {path}",
            "initialize adoption answers and retry",
        )

    draft = answers.load_answers(path, "prepare adoption preview")
    modules, values = answers.load_manifest_sections(
        path, "prepare adoption preview", "modules", "values"
    )
    problems = project_render.specification_problems(
        draft, modules, values, require_complete=True
    )
    if problems:
        raise CommandError(
            1,
            f"refused to prepare adoption preview: {target}",
            "; ".join(problems),
            "complete the answers, run check, and retry",
        )

    return target, preview, destination, draft, modules, values


def prepare(raw_target):
    target, preview, destination, draft, modules, values = validated_inputs(
        raw_target
    )
    staging = None
    try:
        staging = Path(tempfile.mkdtemp(dir=preview, prefix=".files."))
        commit, changed_sources = project_render.kit_version(KIT)
        rendered = project_render.render_tree(
            KIT,
            staging,
            draft,
            modules,
            values,
            commit,
        )
        os.replace(staging, destination)
        staging = None
    except OSError as error:
        raise CommandError(
            2,
            f"failed to prepare adoption preview: {target}",
            str(error),
            "check the target path and permissions, then retry",
        )
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)

    reason = (
        "rendered a clean Rulekit base with "
        f"{rendered['copied_rules']} rule file(s), "
        f"{rendered['copied_scaffolds']} scaffold file(s), and "
        f"{rendered['repositories']} inner repository directory(s)"
    )
    next_step = "inspect the preview before reconciling existing project content"
    if changed_sources:
        reason += (
            "; warning: .kit.json records HEAD although managed kit sources "
            f"differ from it: {', '.join(changed_sources)}"
        )
        next_step = (
            "commit the kit sources and prepare again before treating "
            "kit.commit as a reproducible baseline"
        )
    report(f"prepared adoption preview: {destination}", reason, next_step)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="existing project directory")
    args = parser.parse_args()

    try:
        return prepare(args.target)
    except CommandError as error:
        report(error.result, error.reason, error.next_step, stream=sys.stderr)
        return error.exit_code


if __name__ == "__main__":
    sys.exit(main())
