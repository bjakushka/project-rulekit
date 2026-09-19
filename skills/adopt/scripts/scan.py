#!/usr/bin/env python3
"""Report repository roots and files in an existing project without writing."""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path


SKIPPED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".kit-preview",
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "vendor",
    "venv",
}
DEFAULT_MAX_FILES = 2_000


class ScanError(Exception):
    """An expected scan failure suitable for concise CLI reporting."""


@dataclass(frozen=True)
class Scope:
    root: Path
    label: str
    kind: str
    parent: str | None
    files: tuple[str, ...]
    truncated: bool


@dataclass(frozen=True)
class ScanResult:
    target: Path
    scopes: tuple[Scope, ...]
    warnings: tuple[str, ...]


def display_label(path: Path, target: Path) -> str:
    relative = path.relative_to(target).as_posix()
    return "." if relative == "." else f"{relative}/"


def safe_display_path(path: str) -> bool:
    return "`" not in path and "\n" not in path and "\r" not in path


def discover_git_roots(target: Path, warnings: list[str]) -> list[Path]:
    roots = []

    def record_error(error):
        warnings.append(f"could not inspect {error.filename}: {error.strerror}")

    for current, directories, files in os.walk(
        target,
        topdown=True,
        followlinks=False,
        onerror=record_error,
    ):
        current_path = Path(current)
        if ".git" in directories or ".git" in files:
            roots.append(current_path)

        directories[:] = sorted(
            directory
            for directory in directories
            if directory not in SKIPPED_DIRECTORIES
        )

    return sorted(set(roots), key=lambda path: (len(path.parts), str(path)))


def closest_parent(root: Path, roots: list[Path], target: Path) -> str | None:
    parents = [
        candidate
        for candidate in roots
        if candidate != root and candidate in root.parents
    ]
    if not parents:
        return None
    parent = max(parents, key=lambda path: len(path.parts))
    return display_label(parent, target)


def collect_files(
    root: Path,
    excluded_roots: set[Path],
    max_files: int,
    warnings: list[str],
) -> tuple[tuple[str, ...], bool]:
    paths = []

    def record_error(error):
        warnings.append(f"could not inspect {error.filename}: {error.strerror}")

    for current, directories, files in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=record_error,
    ):
        current_path = Path(current)
        directories[:] = sorted(
            directory
            for directory in directories
            if directory not in SKIPPED_DIRECTORIES
            and current_path / directory not in excluded_roots
        )

        for filename in sorted(files):
            if filename == ".git":
                continue
            relative = (current_path / filename).relative_to(root).as_posix()
            if safe_display_path(relative):
                paths.append(relative)
            else:
                warnings.append(
                    f"skipped a path that cannot be displayed safely under {root}"
                )

    paths.sort(key=lambda path: (len(Path(path).parts), path))
    truncated = len(paths) > max_files
    return tuple(paths[:max_files]), truncated


def scan_target(raw_target: str, max_files: int) -> ScanResult:
    target = Path(raw_target).expanduser().resolve()
    if not target.exists():
        raise ScanError(f"target does not exist: {target}")
    if not target.is_dir():
        raise ScanError(f"target is not a directory: {target}")
    if max_files < 1:
        raise ScanError("max-files must be a positive integer")

    warnings = []
    git_roots = discover_git_roots(target, warnings)
    scope_roots = list(git_roots)
    if target not in git_roots:
        scope_roots.insert(0, target)

    scopes = []
    for root in scope_roots:
        excluded = {
            candidate
            for candidate in git_roots
            if candidate != root and root in candidate.parents
        }
        files, truncated = collect_files(root, excluded, max_files, warnings)
        kind = "repository" if root in git_roots else "workspace"
        parent = (
            closest_parent(root, git_roots, target)
            if kind == "repository"
            else None
        )
        scopes.append(
            Scope(
                root=root,
                label=display_label(root, target),
                kind=kind,
                parent=parent,
                files=files,
                truncated=truncated,
            )
        )

    return ScanResult(target=target, scopes=tuple(scopes), warnings=tuple(warnings))


def render(result: ScanResult) -> str:
    lines = [f"Target: `{result.target}`", "", "## Git repositories", ""]
    repositories = [scope for scope in result.scopes if scope.kind == "repository"]
    if repositories:
        for scope in repositories:
            parent = f"; parent `{scope.parent}`" if scope.parent else ""
            lines.append(f"`{scope.label}` :: Git repository{parent}")
    else:
        lines.append("None found")

    for scope in result.scopes:
        heading = "Repository" if scope.kind == "repository" else "Workspace"
        lines.extend(["", f"## {heading} `{scope.label}`", ""])
        lines.extend(f"`{path}`" for path in scope.files)
        if scope.truncated:
            lines.append(f"[truncated after {len(scope.files)} files]")

    if result.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in result.warnings)

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="existing project directory")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    args = parser.parse_args()

    try:
        result = scan_target(args.target, args.max_files)
    except (OSError, ScanError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
