#!/usr/bin/env python3
"""Prepare a clean Rulekit preview for an existing project."""

import argparse
import json
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
PREVIEW_DIRECTORY = ".kit-preview"

sys.path.insert(0, str(KIT / "scripts"))

import render as project_render


def report(result, reason, next_step, stream=sys.stdout):
    print(f"result: {result}", file=stream)
    print(f"reason: {reason}", file=stream)
    print(f"next: {next_step}", file=stream)


def load_manifest():
    path = KIT / "manifest.json"
    try:
        with path.open(encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise project_render.ProjectError(
            2,
            f"failed to read kit manifest: {path}",
            str(error),
            "run `python3 scripts/manifest.py check` and fix the manifest",
        )
    return manifest


def pairs_to_dict(pairs, subject):
    result = {}
    duplicates = []
    for key, value in pairs:
        if key in result:
            duplicates.append(key)
        result[key] = value
    if duplicates:
        raise project_render.ProjectError(
            1,
            "refused to prepare adoption preview",
            f"{subject} were repeated: {', '.join(sorted(set(duplicates)))}",
            f"pass every {subject[:-1]} exactly once",
        )
    return result


def prepare(args):
    target = Path(args.target).expanduser().resolve()
    preview = target / PREVIEW_DIRECTORY
    destination = preview / "files"

    if not target.is_dir():
        raise project_render.ProjectError(
            1,
            f"refused to prepare adoption preview: {target}",
            "the adoption target does not exist or is not a directory",
            "choose an existing project directory",
        )
    if os.path.lexists(target / project_render.STATE_FILENAME):
        raise project_render.ProjectError(
            1,
            f"refused to prepare adoption preview: {target}",
            "the project already has Rulekit state",
            "use the future sync workflow instead of adopt",
        )
    if os.path.lexists(preview):
        raise project_render.ProjectError(
            1,
            f"refused to prepare adoption preview: {target}",
            f"the preview workspace already exists: {preview}",
            "inspect it, then explicitly remove it before preparing again",
        )

    manifest = load_manifest()
    modules = manifest["modules"]
    values = manifest["values"]
    draft = {
        "brief": {
            "context": args.context.strip(),
            "repositories": sorted(
                (
                    {"path": path, "purpose": purpose.strip()}
                    for path, purpose in args.repository
                ),
                key=lambda repository: repository["path"].casefold(),
            ),
        },
        "modules": sorted(args.module),
        "values": pairs_to_dict(args.value, "values"),
    }
    problems = project_render.specification_problems(
        draft, modules, values, require_complete=True
    )
    if problems:
        raise project_render.ProjectError(
            1,
            f"refused to prepare adoption preview: {target}",
            "; ".join(problems),
            "correct the confirmed project specification and retry",
        )

    staging = None
    complete = False
    try:
        preview.mkdir()
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
        complete = True
    except OSError as error:
        raise project_render.ProjectError(
            2,
            f"failed to prepare adoption preview: {target}",
            str(error),
            "check the target path and permissions, then retry",
        )
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        if not complete:
            shutil.rmtree(preview, ignore_errors=True)

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
    parser.add_argument("--context", required=True, help="confirmed project context")
    parser.add_argument(
        "--module",
        action="append",
        default=[],
        required=True,
        help="confirmed Rulekit module; repeat for every selected module",
    )
    parser.add_argument(
        "--value",
        action="append",
        default=[],
        nargs=2,
        required=True,
        metavar=("KEY", "VALUE"),
        help="confirmed Rulekit value; repeat for every value",
    )
    parser.add_argument(
        "--repo",
        dest="repository",
        action="append",
        default=[],
        nargs=2,
        required=True,
        metavar=("PATH", "PURPOSE"),
        help="confirmed inner repository path and purpose; repeat as needed",
    )
    args = parser.parse_args()

    try:
        return prepare(args)
    except project_render.ProjectError as error:
        report(error.result, error.reason, error.next_step, stream=sys.stderr)
        return error.exit_code


if __name__ == "__main__":
    sys.exit(main())
