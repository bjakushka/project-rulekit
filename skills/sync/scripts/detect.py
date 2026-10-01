#!/usr/bin/env python3
"""Compare rendered core rules and selected modules with current Rulekit."""

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
sys.path.insert(0, str(KIT / "scripts"))
sys.dont_write_bytecode = True

import render as project_render


@dataclass(frozen=True)
class SyncState:
    target: Path
    baseline_commit: str
    modules: tuple[str, ...]
    values: dict[str, str]
    baseline_declarations: dict[str, dict]
    current_declarations: dict[str, dict]

    def has_rules(self, module):
        """Whether the module ships rules, read from the kit's own layout."""
        return (KIT / "modules" / module / "rules").is_dir()

    def owned_skills(self, module):
        """The skill directories this module installs, by name."""
        root = KIT / "modules" / module / "skills"
        if not root.is_dir():
            return ()
        return tuple(sorted(p.name for p in root.iterdir() if p.is_dir()))


@dataclass(frozen=True)
class Comparison:
    kind: str
    name: str
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
    values = state.get("values")
    if not isinstance(commit, str) or not commit.strip():
        raise SyncError("Rulekit state has no valid `kit.commit`")
    if (
        not isinstance(modules, list)
        or not modules
        or not all(isinstance(module, str) and module for module in modules)
        or len(modules) != len(set(modules))
    ):
        raise SyncError("Rulekit state has no valid selected module list")
    if (
        not isinstance(values, dict)
        or not all(
            isinstance(key, str)
            and key
            and isinstance(value, str)
            and value
            for key, value in values.items()
        )
    ):
        raise SyncError("Rulekit state has no valid value map")

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

    return SyncState(
        target,
        commit,
        tuple(sorted(modules)),
        values,
        baseline_modules,
        current_modules,
    )


def manifest_from_git(commit):
    try:
        return json.loads(run_git("show", f"{commit}:manifest.json", text=True))
    except json.JSONDecodeError as error:
        raise SyncError(f"baseline manifest is invalid JSON: {error}") from error


def module_paths_from_git(commit, module, has_rules):
    """The baseline's rule files, or none when the module ships no rules."""
    if not has_rules:
        return []
    output = run_git(
        "ls-tree",
        "-r",
        "--name-only",
        commit,
        "--",
        f"modules/{module}/rules",
        text=True,
    )
    directory = f"modules/{module}/rules/"
    paths = [
        path
        for path in output.splitlines()
        if path.startswith(directory)
        and Path(path).parent.as_posix() == directory.rstrip("/")
        and path.endswith(".md")
    ]
    if not paths:
        raise SyncError(f"baseline module has no rule files: {module}")
    return paths


def module_entry_points_from_git(commit, modules, has_rules_of):
    entry_points = {}
    for module in modules:
        if not has_rules_of(module):
            continue
        paths = module_paths_from_git(commit, module, True)
        if f"modules/{module}/rules/INDEX.md" not in paths:
            raise SyncError(f"baseline module has no INDEX.md: {module}")
        entry_points[module] = Path(target_rule_path(module, "INDEX.md"))
    return entry_points


def current_module_entry_points(manifest, modules):
    declarations = manifest.get("modules", {})
    return {
        module: project_render.module_entry_point(KIT, module)
        for module in modules
    }


def kit_source_path(logical, module=None):
    """Where a project-relative path comes from inside the kit.

    A module's rules live under `modules/<key>/rules/` and its skills under
    `modules/<key>/skills/`, while a core file keeps its own name under `core/`.
    """
    parts = Path(logical).parts
    if parts[:1] == ("rules",) and len(parts) >= 3:
        return KIT / "modules" / parts[1] / "rules" / Path(*parts[2:])
    if parts[:2] == (".claude", "skills") and module is not None:
        return KIT / "modules" / module / "skills" / Path(*parts[2:])
    return KIT / "core" / logical


def target_rule_path(module, name):
    """The project-relative path of a rule file, as the renderer computes it."""
    return project_render.module_rule_target(module, name).as_posix()


def baseline_snapshot(commit, module, has_rules):
    snapshot = {}
    for source in module_paths_from_git(commit, module, has_rules):
        snapshot[target_rule_path(module, Path(source).name)] = run_git(
            "show", f"{commit}:{source}"
        )
    return snapshot


def filesystem_snapshot(
    directory, module, has_rules, subject, allow_missing=False
):
    """One module's rule files, keyed by where they belong in a project.

    `directory` is where the files sit: `modules/<key>/rules/` inside the kit,
    `rules/<key>/` inside a project. The key of the returned mapping is always
    the project-relative path, so the baseline, project and kit snapshots can be
    compared against each other. A module that ships only skills has no rule
    files to read.
    """
    if not has_rules:
        return {}

    if directory.is_symlink():
        raise SyncError(f"{subject} module must not be a symlink: {module}")

    if directory.is_dir():
        paths = sorted(directory.glob("*.md"))
        if any(path.is_symlink() for path in paths):
            raise SyncError(f"{subject} module contains a symlink: {module}")
    elif allow_missing:
        return {}
    else:
        raise SyncError(f"{subject} module has no rule files: {module}")

    snapshot = {}
    for path in paths:
        snapshot[target_rule_path(module, path.name)] = path.read_bytes()
    return snapshot


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


def skill_target_path(name):
    """Where a skill file lands in a project, as the renderer computes it."""
    return project_render.module_skill_target(name).as_posix()


def skill_paths_from_git(commit, module, skills):
    """The baseline's files for the skill directories a module owns."""
    if not skills:
        return []
    output = run_git(
        "ls-tree", "-r", "--name-only", commit,
        "--", f"modules/{module}/skills", text=True,
    )
    prefixes = tuple(f"modules/{module}/skills/{name}/" for name in skills)
    return [path for path in output.splitlines() if path.startswith(prefixes)]


def skill_baseline_snapshot(commit, module, skills):
    snapshot = {}
    for source in skill_paths_from_git(commit, module, skills):
        inner = Path(source).relative_to(f"modules/{module}/skills")
        content = run_git("show", f"{commit}:{source}")
        snapshot[skill_target_path(inner)] = content
    return snapshot


def skill_filesystem_snapshot(root, module, skills, subject):
    """One module's skill files, keyed by where they belong in a project.

    Only the skill directories the module owns are read, so a project-local
    skill sitting beside them never enters the comparison.
    """
    snapshot = {}
    for name in skills:
        directory = root / name
        if not directory.is_dir():
            continue
        if directory.is_symlink():
            raise SyncError(f"{subject} skill must not be a symlink: {name}")
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            if path.is_symlink():
                raise SyncError(
                    f"{subject} skill contains a symlink: {module}/{name}"
                )
            inner = Path(name) / path.relative_to(directory)
            snapshot[skill_target_path(inner)] = path.read_bytes()
    return snapshot


def compare_module(state, module):
    if module not in state.modules:
        raise SyncError(f"module is not selected by the project: {module}")
    baseline = baseline_snapshot(
        state.baseline_commit, module, state.has_rules(module)
    )
    project = filesystem_snapshot(
        state.target / "rules" / module,
        module,
        state.has_rules(module),
        "project",
        allow_missing=True,
    )
    kit = filesystem_snapshot(
        KIT / "modules" / module / "rules",
        module,
        state.has_rules(module),
        "current kit",
    )

    skills = state.owned_skills(module)
    baseline.update(
        skill_baseline_snapshot(state.baseline_commit, module, skills)
    )
    project.update(
        skill_filesystem_snapshot(
            state.target / ".claude" / "skills", module, skills, "project"
        )
    )
    kit.update(
        skill_filesystem_snapshot(
            KIT / "modules" / module / "skills", module, skills, "current kit"
        )
    )

    return Comparison(
        "module",
        module,
        classify(baseline, project, kit),
        baseline,
        project,
        kit,
    )


def core_rule_names(manifest, subject):
    core = manifest.get("core")
    rules = core.get("rules") if isinstance(core, dict) else None
    if (
        not isinstance(rules, list)
        or not rules
        or not all(isinstance(rule, str) and rule for rule in rules)
        or len(rules) != len(set(rules))
    ):
        raise SyncError(f"{subject} has no valid core rule list")
    unsupported = sorted(set(rules) - {"CLAUDE.md"})
    if unsupported:
        raise SyncError(
            f"{subject} declares unsupported core rules: "
            + ", ".join(unsupported)
        )
    return tuple(sorted(rules))


def rendered_core_snapshot(
    template,
    manifest,
    state,
    entry_points,
    subject,
):
    rules = core_rule_names(manifest, subject)
    try:
        claude, _values = project_render.render_claude_text(
            template,
            state.modules,
            state.values,
            manifest.get("modules", {}),
            manifest.get("values", {}),
            entry_points,
        )
    except (KeyError, project_render.ProjectError) as error:
        detail = (
            error.reason
            if isinstance(error, project_render.ProjectError)
            else error
        )
        raise SyncError(f"could not render {subject} core: {detail}") from error
    return {"CLAUDE.md": claude.encode("utf-8")} if "CLAUDE.md" in rules else {}


def baseline_core_snapshot(state, commit=None):
    commit = state.baseline_commit if commit is None else commit
    manifest = manifest_from_git(commit)
    try:
        template = run_git(
            "show",
            f"{commit}:core/CLAUDE.md",
        ).decode("utf-8")
    except UnicodeDecodeError as error:
        raise SyncError("baseline core template is not UTF-8 text") from error
    return rendered_core_snapshot(
        template,
        manifest,
        state,
        module_entry_points_from_git(commit, state.modules, state.has_rules),
        "baseline manifest",
    )


def current_core_snapshot(state):
    manifest = read_json(KIT / "manifest.json", "current manifest")
    try:
        template = (KIT / "core" / "CLAUDE.md").read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise SyncError("current core template is not UTF-8 text") from error
    return rendered_core_snapshot(
        template,
        manifest,
        state,
        current_module_entry_points(manifest, state.modules),
        "current manifest",
    )


def project_core_snapshot(state, rule_names):
    snapshot = {}
    for name in rule_names:
        path = state.target / name
        if path.is_symlink():
            raise SyncError(f"project core rule must not be a symlink: {name}")
        if path.is_file():
            snapshot[name] = path.read_bytes()
    return snapshot


def compare_core(state):
    baseline = baseline_core_snapshot(state)
    kit = current_core_snapshot(state)
    project = project_core_snapshot(state, sorted(set(baseline) | set(kit)))
    return Comparison(
        "core",
        "rendered-core",
        classify(baseline, project, kit),
        baseline,
        project,
        kit,
    )


def comparisons(raw_target):
    state = load_state(raw_target)
    return (
        state,
        compare_core(state),
        tuple(compare_module(state, module) for module in state.modules),
    )


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
        core = compare_core(state)
        modules = tuple(
            compare_module(state, module) for module in state.modules
        )
    except (
        OSError,
        SyncError,
        UnicodeError,
        json.JSONDecodeError,
        project_render.ProjectError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    changed_modules = [
        comparison for comparison in modules if comparison.status != "unchanged"
    ]
    print(f"Target: `{state.target}`")
    print(f"Baseline: `{state.baseline_commit}`")
    if core.status == "unchanged" and not changed_modules:
        print("\nRendered core rules and all selected modules are unchanged.")
        return 0

    if core.status != "unchanged":
        print("\nChanged core:")
        print(f"- `rendered-core` - {core.status}")
    if changed_modules:
        print("\nChanged modules:")
        for comparison in changed_modules:
            print(f"- `{comparison.name}` - {comparison.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
