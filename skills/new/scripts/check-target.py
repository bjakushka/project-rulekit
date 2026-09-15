#!/usr/bin/env python3
"""Check whether a target directory is suitable for `rulekit:new`.

Output:
    path: <absolute path>
    state: missing | empty | git-only | preview-exists | not-directory |
           not-empty | error
    ready: yes | no

Exit codes:
    0  target is suitable
    1  target is not suitable
    2  usage or operating system error
"""

import argparse
import sys
from pathlib import Path


def inspect_target(raw_path):
    path = Path(raw_path).expanduser().resolve()

    if not path.exists():
        return path, "missing", True
    if not path.is_dir():
        return path, "not-directory", False

    entries = {entry.name for entry in path.iterdir()}
    if not entries:
        return path, "empty", True
    if entries == {".git"}:
        return path, "git-only", True
    if ".kit-preview" in entries:
        return path, "preview-exists", False
    return path, "not-empty", False


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--target", required=True, help="target directory path")
    args = parser.parse_args()

    try:
        path, state, ready = inspect_target(args.target)
    except OSError as error:
        print(f"path: {Path(args.target).expanduser().absolute()}")
        print("state: error")
        print("ready: no")
        print(f"error: {error}")
        return 2

    print(f"path: {path}")
    print(f"state: {state}")
    print(f"ready: {'yes' if ready else 'no'}")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
