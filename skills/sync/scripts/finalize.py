#!/usr/bin/env python3
"""Advance an adopted project's Rulekit baseline after a completed sync."""

import argparse
import json
import subprocess
import sys

import detect


sys.path.insert(0, str(detect.KIT / "scripts"))
sys.dont_write_bytecode = True

import answers


def require_descendant(baseline, head):
    result = subprocess.run(
        [
            "git",
            "-C",
            str(detect.KIT),
            "merge-base",
            "--is-ancestor",
            baseline,
            head,
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode == 1:
        raise detect.SyncError(
            "current Rulekit HEAD does not descend from the stored baseline"
        )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise detect.SyncError(detail or "could not compare Rulekit commits")


def finalize(raw_target):
    state = detect.load_state(raw_target)
    head = detect.run_git("rev-parse", "--verify", "HEAD", text=True).strip()
    require_descendant(state.baseline_commit, head)

    current_manifest = (detect.KIT / "manifest.json").read_bytes()
    committed_manifest = detect.run_git("show", f"{head}:manifest.json")
    if current_manifest != committed_manifest:
        raise detect.SyncError(
            "current Rulekit manifest differs from committed HEAD"
        )

    comparisons = [
        detect.compare_module(state, module) for module in state.modules
    ]
    unmatched = [
        comparison.module
        for comparison in comparisons
        if comparison.project != comparison.kit
    ]
    if unmatched:
        raise detect.SyncError(
            "project and Rulekit modules still differ: " + ", ".join(unmatched)
        )

    uncommitted = [
        comparison.module
        for comparison in comparisons
        if comparison.kit
        != detect.baseline_snapshot(head, comparison.module)
    ]
    if uncommitted:
        raise detect.SyncError(
            "current Rulekit module content is not in HEAD: "
            + ", ".join(uncommitted)
        )

    state_path = state.target / ".kit.json"
    if state.baseline_commit == head:
        return (
            f"baseline is already current: {state_path}",
            f"all {len(comparisons)} selected module(s) match Rulekit HEAD {head}",
            "no state update is needed",
        )

    document = detect.read_json(state_path, "Rulekit state")
    document["kit"]["commit"] = head
    answers.write_replacement(state_path, document)
    return (
        f"advanced Rulekit baseline: {state_path}",
        f"all {len(comparisons)} selected module(s) match committed HEAD {head}",
        "review and commit the updated .kit.json in the project repository",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="adopted project directory")
    args = parser.parse_args()

    try:
        result, reason, next_step = finalize(args.target)
    except (OSError, detect.SyncError, UnicodeError, json.JSONDecodeError) as error:
        print("result: refused to advance Rulekit baseline", file=sys.stderr)
        print(f"reason: {error}", file=sys.stderr)
        print(
            "next: commit the accepted Rulekit module content and retry",
            file=sys.stderr,
        )
        return 1

    print(f"result: {result}")
    print(f"reason: {reason}")
    print(f"next: {next_step}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
