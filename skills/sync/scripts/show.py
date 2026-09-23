#!/usr/bin/env python3
"""Show three-way text differences for one selected Rulekit module."""

import argparse
import difflib
import sys

import detect


def decoded(snapshot, path):
    content = snapshot.get(path)
    if content is None:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise detect.SyncError(f"module file is not UTF-8 text: {path}") from error


def snapshot_diff(old, new, old_name, new_name):
    sections = []
    for path in sorted(set(old) | set(new)):
        before = decoded(old, path)
        after = decoded(new, path)
        if before == after:
            continue
        fromfile = "/dev/null" if before is None else f"{old_name}/{path}"
        tofile = "/dev/null" if after is None else f"{new_name}/{path}"
        lines = difflib.unified_diff(
            [] if before is None else before.splitlines(),
            [] if after is None else after.splitlines(),
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
        sections.append("\n".join(lines))
    return "\n\n".join(sections) if sections else "(no differences)"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="adopted project directory")
    parser.add_argument("--module", required=True, help="selected module name")
    args = parser.parse_args()

    try:
        state = detect.load_state(args.target)
        comparison = detect.compare_module(state, args.module)
        sections = (
            (
                "Baseline -> project",
                snapshot_diff(
                    comparison.baseline,
                    comparison.project,
                    "baseline",
                    "project",
                ),
            ),
            (
                "Baseline -> current kit",
                snapshot_diff(
                    comparison.baseline,
                    comparison.kit,
                    "baseline",
                    "kit",
                ),
            ),
            (
                "Current kit -> project",
                snapshot_diff(
                    comparison.kit,
                    comparison.project,
                    "kit",
                    "project",
                ),
            ),
        )
    except (OSError, detect.SyncError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Module: `{comparison.module}`")
    print(f"Status: `{comparison.status}`")
    for heading, content in sections:
        print(f"\n## {heading}\n")
        print(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
