#!/usr/bin/env python3
"""Compare selected project modules with their baseline and current Rulekit."""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class SyncError(Exception):
    """An expected sync inspection failure."""


def find_kit_root(start):
    for directory in (start, *start.parents):
        if (
            (directory / ".claude-plugin" / "plugin.json").is_file()
            and (directory / "manifest.json").is_file()
        ):
            return directory
    raise RuntimeError(f"could not find the rulekit plugin root above: {start}")


KIT = find_kit_root(Path(__file__).resolve().parent)


@dataclass(frozen=True)
class SyncState:
    target: Path
    baseline_commit: str
    modules: tuple[str, ...]


@dataclass(frozen=True)
class Comparison:
    module: str
    status: str
    baseline: dict[str, bytes]
    project: dict[str, bytes]
    kit: dict[str, bytes]


def read_json(path, subject):
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as error:
        raise SyncError(f"{subject} is missing: {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise SyncError(f"could not read {subject} at {path}: {error}") from error


def run_git_at(root, *arguments, text=False):
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        check=False,
        text=text,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() if text else result.stderr.decode().strip()
        raise SyncError(detail or f"git {' '.join(arguments)} failed")
    return result.stdout


def run_git(*arguments, text=False):
    return run_git_at(KIT, *arguments, text=text)


def require_clean_repository(root, subject):
    root = root.resolve()
    top_level = Path(
        run_git_at(root, "rev-parse", "--show-toplevel", text=True).strip()
    ).resolve()
    if top_level != root:
        raise SyncError(f"{subject} is not a Git repository root: {root}")

    output = run_git_at(
        root,
        "status",
        "--porcelain",
        "--untracked-files=all",
        text=True,
    ).strip()
    if output:
        changes = output.splitlines()
        summary = "; ".join(changes[:5])
        if len(changes) > 5:
            summary += f"; and {len(changes) - 5} more"
        raise SyncError(f"{subject} repository has uncommitted changes: {summary}")


def load_state(raw_target):
    target = Path(raw_target).expanduser().resolve()
    if not target.is_dir():
        raise SyncError(f"target is not a directory: {target}")

    state_path = target / ".kit.json"
    if state_path.is_symlink():
        raise SyncError(f"Rulekit state must not be a symlink: {state_path}")
    state = read_json(state_path, "Rulekit state")
    if not isinstance(state, dict):
        raise SyncError("Rulekit state must be a JSON object")

    kit = state.get("kit")
    commit = kit.get("commit") if isinstance(kit, dict) else None
    modules = state.get("modules")
    if not isinstance(commit, str) or not commit.strip():
        raise SyncError("Rulekit state has no valid `kit.commit`")
    if (
        not isinstance(modules, list)
        or not modules
        or not all(isinstance(module, str) and module for module in modules)
        or len(modules) != len(set(modules))
    ):
        raise SyncError("Rulekit state has no valid selected module list")

    run_git("cat-file", "-e", f"{commit}^{{commit}}")
    current_manifest = read_json(KIT / "manifest.json", "current manifest")
    baseline_manifest = json.loads(
        run_git("show", f"{commit}:manifest.json", text=True)
    )
    current_modules = current_manifest.get("modules", {})
    baseline_modules = baseline_manifest.get("modules", {})
    unavailable = sorted(
        module
        for module in modules
        if module not in current_modules or module not in baseline_modules
    )
    if unavailable:
        raise SyncError(
            "selected modules are not available in both manifests: "
            + ", ".join(unavailable)
        )

    return SyncState(target, commit, tuple(sorted(modules)))


def module_paths_from_git(commit, module):
    output = run_git(
        "ls-tree",
        "-r",
        "--name-only",
        commit,
        "--",
        "template/rules",
        text=True,
    )
    single = f"template/rules/{module}.md"
    directory = f"template/rules/{module}/"
    paths = [
        path
        for path in output.splitlines()
        if path == single
        or (
            path.startswith(directory)
            and Path(path).parent.as_posix() == directory.rstrip("/")
            and path.endswith(".md")
        )
    ]
    if not paths:
        raise SyncError(f"baseline module has no rule files: {module}")
    return paths


def baseline_snapshot(commit, module):
    snapshot = {}
    for source in module_paths_from_git(commit, module):
        logical = Path(source).relative_to("template").as_posix()
        snapshot[logical] = run_git("show", f"{commit}:{source}")
    return snapshot


def filesystem_snapshot(root, module, subject, allow_missing=False):
    single = root / "rules" / f"{module}.md"
    directory = root / "rules" / module
    if single.exists() and directory.exists():
        raise SyncError(f"{subject} has both file and directory forms: {module}")
    if single.is_symlink() or directory.is_symlink():
        raise SyncError(f"{subject} module must not be a symlink: {module}")

    if single.is_file():
        paths = [single]
    elif directory.is_dir():
        paths = sorted(directory.glob("*.md"))
        if any(path.is_symlink() for path in paths):
            raise SyncError(f"{subject} module contains a symlink: {module}")
    elif allow_missing:
        return {}
    else:
        raise SyncError(f"{subject} module has no rule files: {module}")

    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in paths
    }


def classify(baseline, project, kit):
    if project == baseline and kit == baseline:
        return "unchanged"
    if project != baseline and kit == baseline:
        return "project-only"
    if project == baseline and kit != baseline:
        return "kit-only"
    if project == kit:
        return "converged"
    return "diverged"


def compare_module(state, module):
    if module not in state.modules:
        raise SyncError(f"module is not selected by the project: {module}")
    baseline = baseline_snapshot(state.baseline_commit, module)
    project = filesystem_snapshot(
        state.target, module, "project", allow_missing=True
    )
    kit = filesystem_snapshot(KIT / "template", module, "current kit")
    return Comparison(module, classify(baseline, project, kit), baseline, project, kit)


def comparisons(raw_target):
    state = load_state(raw_target)
    return state, tuple(compare_module(state, module) for module in state.modules)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="adopted project directory")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow approved changes while rechecking the current sync run",
    )
    args = parser.parse_args()

    try:
        state = load_state(args.target)
        if not args.allow_dirty:
            require_clean_repository(KIT, "Rulekit")
            require_clean_repository(state.target, "target")
        found = tuple(
            compare_module(state, module) for module in state.modules
        )
    except (OSError, SyncError, UnicodeError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    changed = [comparison for comparison in found if comparison.status != "unchanged"]
    print(f"Target: `{state.target}`")
    print(f"Baseline: `{state.baseline_commit}`")
    if not changed:
        print("\nAll selected modules are unchanged.")
        return 0

    print("\nChanged modules:")
    for comparison in changed:
        print(f"- `{comparison.module}` - {comparison.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
