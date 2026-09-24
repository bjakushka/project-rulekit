#!/usr/bin/env python3
"""Initialize Git repositories in explicitly provided existing directories."""

import argparse
import os
import subprocess
import sys
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


CommandError = answers.CommandError
report = answers.report


def run_git(arguments, operation, exit_code=2):
    try:
        completed = subprocess.run(
            ["git", *arguments],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as error:
        raise CommandError(
            exit_code,
            f"failed to {operation}",
            str(error),
            "make Git available and retry",
        )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise CommandError(
            exit_code,
            f"failed to {operation}",
            detail or f"Git exited with status {completed.returncode}",
            "fix the reported Git problem and retry the same command",
        )
    return completed.stdout.strip()


def resolve_repositories(raw_paths):
    repositories = []
    seen = set()
    for raw_path in raw_paths:
        path = Path(raw_path).expanduser().resolve(strict=False)
        key = os.path.normcase(str(path))
        if key in seen:
            raise CommandError(
                1,
                "refused to initialize Git repositories",
                f"repository directory was provided more than once: {path}",
                "pass every repository directory exactly once",
            )
        seen.add(key)
        if path.is_symlink() or not path.exists() or not path.is_dir():
            raise CommandError(
                1,
                "refused to initialize Git repositories",
                f"repository directory is missing or invalid: {path}",
                "prepare and apply the project directories, then retry",
            )
        repositories.append(path)
    return repositories


def verify_existing_repository(path):
    marker = path / ".git"
    if not os.path.lexists(marker):
        return False
    if marker.is_symlink():
        raise CommandError(
            1,
            "refused to initialize Git repositories",
            f"the repository marker is a symbolic link: {marker}",
            "inspect the repository marker and retry",
        )
    top_level = run_git(
        ["-C", str(path), "rev-parse", "--show-toplevel"],
        f"verify existing Git repository: {path}",
        exit_code=1,
    )
    if Path(top_level).resolve() != path:
        raise CommandError(
            1,
            "refused to initialize Git repositories",
            f"the existing Git repository has a different root: {path}",
            "pass the repository root directory and retry",
        )
    return True


def repository_count(count):
    noun = "repository" if count == 1 else "repositories"
    return f"{count} {noun}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        action="append",
        required=True,
        help="existing directory to initialize as its own Git repository",
    )

    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    args = parser.parse_args()

    try:
        repositories = resolve_repositories(args.repo)
        run_git(["--version"], "check Git availability")

        existing = []
        pending = []
        for path in repositories:
            if verify_existing_repository(path):
                existing.append(path)
            else:
                pending.append(path)

        initialized = []
        for path in pending:
            run_git(["-C", str(path), "init"], f"initialize Git repository: {path}")
            verify_existing_repository(path)
            initialized.append(path)
    except CommandError as error:
        report(error.result, error.reason, error.next_step, stream=sys.stderr)
        return error.exit_code

    report(
        "Git repository setup is complete: "
        + ", ".join(str(path) for path in repositories),
        f"initialized {repository_count(len(initialized))} and preserved "
        f"{repository_count(len(existing))}",
        "continue work in the generated project",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
