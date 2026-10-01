#!/usr/bin/env python3
"""Report the Rulekit modules a project has installed, with what each is for.

Reads the project only. The kit is not consulted and must not be: a skill
deciding where a finding belongs answers from what the project actually has,
not from what the catalogue could offer.

Output is one block per module:

    <key>
        <description>

The description is the module entry point's heading, which names the module for
the model. A module that ships only skills has no rules and no heading, so it is
listed by key alone.
"""

import argparse
import json
import re
import sys
from pathlib import Path


def fail(result, reason, next_step):
    print(f"result: {result}")
    print(f"reason: {reason}")
    print(f"next: {next_step}")
    return 1


def module_description(rules_root, key):
    """The heading of a module's entry point, or None when it ships no rules."""
    entry = rules_root / key / "INDEX.md"
    if not entry.is_file():
        return None
    try:
        text = entry.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"##\s+(.*)", line)
        return match.group(1).strip() if match else None
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target", default=".", help="project directory to read (default: .)"
    )
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    state = target / ".kit.json"
    if not state.is_file():
        return fail(
            f"refused to list modules: {target}",
            "the project has no .kit.json, so it is not Rulekit-managed",
            "run this from a managed project, or pass --target",
        )

    try:
        modules = json.loads(state.read_text(encoding="utf-8"))["modules"]
    except (OSError, UnicodeError, ValueError, KeyError) as error:
        return fail(
            f"refused to list modules: {state}",
            f"the project state could not be read: {error}",
            "repair .kit.json and retry",
        )

    rules_root = target / "rules"
    for key in sorted(modules):
        print(key)
        description = module_description(rules_root, key)
        if description:
            print(f"    {description}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
