#!/usr/bin/env python3
"""Validate a Rulekit project specification and render its clean file tree."""

import json
import re
import shutil
import subprocess
import textwrap
from collections import Counter
from pathlib import Path


STATE_FILENAME = ".kit.json"
IMPORTS_START = "<!-- kit:imports -->"
IMPORTS_END = "<!-- /kit:imports -->"
PLACEHOLDER = re.compile(r"{{([A-Z][A-Z0-9_]*)}}")
RESERVED_TARGET_PATHS = (
    ".git",
    ".gitignore",
    ".kit-preview",
    STATE_FILENAME,
    "CLAUDE.md",
    "PROJECT.md",
    "rules",
)


class ProjectError(Exception):
    def __init__(self, exit_code, result, reason, next_step):
        super().__init__(reason)
        self.exit_code = exit_code
        self.result = result
        self.reason = reason
        self.next_step = next_step


def run_git(kit_root, *arguments):
    try:
        completed = subprocess.run(
            ["git", "-C", str(kit_root), *arguments],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as error:
        raise ProjectError(
            2,
            "failed to read the current kit version",
            str(error),
            "make Git available and retry",
        )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ProjectError(
            2,
            "failed to read the current kit version",
            detail or f"Git exited with status {completed.returncode}",
            "check that the plugin is inside its Git repository and retry",
        )
    return completed.stdout


def kit_version(kit_root):
    changed = run_git(
        kit_root,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        "manifest.json",
        "template",
    ).rstrip("\n")
    paths = sorted(line[3:] for line in changed.splitlines() if line)
    commit = run_git(kit_root, "rev-parse", "--verify", "HEAD").strip()
    return commit, paths


def module_selection_problems(modules, selected, require_complete=False):
    if not all(isinstance(name, str) for name in selected):
        return [("module names must be strings", "replace invalid module names")]

    problems = []
    duplicates = sorted(
        name for name, count in Counter(selected).items() if count > 1
    )
    if duplicates:
        problems.append(
            (
                f"module names were repeated: {', '.join(duplicates)}",
                "pass every selected module exactly once",
            )
        )

    unknown = sorted(set(selected) - set(modules))
    if unknown:
        problems.append(
            (
                f"unknown modules: {', '.join(unknown)}",
                f"choose from: {', '.join(sorted(modules))}",
            )
        )

    selected_set = set(selected)
    if require_complete:
        required = sorted(
            name
            for name, module in modules.items()
            if module.get("required") and module.get("group") is None
        )
        missing = sorted(set(required) - selected_set)
        if missing:
            problems.append(
                (
                    f"required modules are missing: {', '.join(missing)}",
                    "add the missing modules and retry",
                )
            )

    groups = {}
    for name, module in modules.items():
        group = module.get("group")
        if group is not None:
            groups.setdefault(group, []).append(name)

    for group in sorted(groups):
        members = sorted(groups[group])
        chosen = sorted(selected_set.intersection(members))
        required_group = any(modules[name].get("required") for name in members)
        if len(chosen) > 1:
            problems.append(
                (
                    f"group `{group}` allows one module but selected: "
                    f"{', '.join(chosen)}",
                    f"choose one of: {', '.join(members)}",
                )
            )
        elif require_complete and required_group and not chosen:
            problems.append(
                (
                    f"required group `{group}` has no selected module",
                    f"choose one of: {', '.join(members)}",
                )
            )

    return problems


def stored_value_problem(key, value, declaration):
    if not isinstance(value, str):
        return f"value `{key}` must be a string"
    if declaration.get("required") and not value.strip():
        return f"required value is empty: {key}"
    choices = declaration.get("choices")
    if choices is not None and value not in choices:
        return (
            f"value `{key}` is not supported: {value}; "
            f"choose from: {', '.join(choices)}"
        )
    return None


def value_problems(values, selected):
    problems = []
    unknown = sorted(set(selected) - set(values))
    if unknown:
        problems.append(f"unknown value keys: {', '.join(unknown)}")

    required = sorted(
        key for key, declaration in values.items() if declaration.get("required")
    )
    missing = sorted(set(required) - set(selected))
    if missing:
        problems.append(f"required values are missing: {', '.join(missing)}")

    for key in sorted(set(selected).intersection(values)):
        problem = stored_value_problem(key, selected[key], values[key])
        if problem:
            problems.append(problem)
    return problems


def scaffold_output_path(name):
    path = Path(name)
    suffix = ".tmpl.md"
    if path.is_absolute() or ".." in path.parts or not path.name.endswith(suffix):
        raise ProjectError(
            2,
            "failed to validate project brief",
            f"invalid scaffold template path in the manifest: {name}",
            "run `python3 scripts/manifest.py check` and fix the manifest",
        )
    return path.with_name(f"{path.name[:-len(suffix)]}.md")


def normalize_repository_path(raw_path):
    path = raw_path.strip().rstrip("/")
    if not path:
        return None, "repository path is empty"
    if path.startswith("/") or "\\" in path:
        return None, f"repository path must be relative and use `/`: {raw_path}"
    if any(ord(character) < 32 for character in path):
        return None, f"repository path contains a control character: {raw_path}"

    parts = path.split("/")
    if any(part in ("", ".", "..", "~") for part in parts):
        return None, f"repository path is not normalized or safe: {raw_path}"
    if re.match(r"^[A-Za-z]:", parts[0]):
        return None, f"repository path must not use a drive prefix: {raw_path}"
    return "/".join(parts), None


def paths_overlap(left, right):
    left_parts = tuple(part.casefold() for part in left.split("/"))
    right_parts = tuple(part.casefold() for part in right.split("/"))
    common = min(len(left_parts), len(right_parts))
    return left_parts[:common] == right_parts[:common]


def generated_target_paths(modules, selected_modules):
    generated = set(RESERVED_TARGET_PATHS)
    for name in selected_modules:
        module = modules.get(name)
        if module is None:
            continue
        for scaffold in module.get("scaffold", []):
            generated.add(scaffold_output_path(scaffold).as_posix())
    return sorted(generated)


def brief_problems(brief, modules, selected_modules, require_complete=False):
    problems = []
    context = brief["context"]
    if require_complete and (context is None or not context.strip()):
        problems.append("project brief context is missing or empty")
    elif isinstance(context, str) and not context.strip():
        problems.append("project brief context is empty")

    repositories = brief["repositories"]
    if require_complete and not repositories:
        problems.append("project brief has no inner repositories")

    normalized = []
    for repository in repositories:
        path, problem = normalize_repository_path(repository["path"])
        if problem:
            problems.append(problem)
            continue
        if path != repository["path"]:
            problems.append(f"repository path is not normalized: {repository['path']}")
        if not repository["purpose"].strip():
            problems.append(f"repository purpose is empty: {repository['path']}")
        normalized.append(path)

    for index, path in enumerate(normalized):
        for other in normalized[index + 1:]:
            if paths_overlap(path, other):
                problems.append(f"repository paths overlap: {path}, {other}")

    reserved = generated_target_paths(modules, selected_modules)
    for path in normalized:
        conflicts = [
            candidate for candidate in reserved if paths_overlap(path, candidate)
        ]
        if conflicts:
            problems.append(
                f"repository path `{path}` conflicts with generated or reserved "
                f"path: {conflicts[0]}"
            )
    return problems


def specification_problems(draft, modules, values, require_complete=True):
    problems = [
        reason
        for reason, _next_step in module_selection_problems(
            modules, draft["modules"], require_complete=require_complete
        )
    ]
    problems.extend(value_problems(values, draft["values"]))
    problems.extend(
        brief_problems(
            draft["brief"],
            modules,
            draft["modules"],
            require_complete=require_complete,
        )
    )
    return problems


def module_rule_files(kit_root, module):
    directory = kit_root / "template" / "rules" / module
    if directory.is_dir():
        return sorted(directory.glob("*.md"))
    return [directory.with_suffix(".md")]


def module_entry_point(kit_root, module):
    directory = kit_root / "template" / "rules" / module
    if directory.is_dir():
        return Path("rules") / module / "INDEX.md"
    return Path("rules") / f"{module}.md"


def resolved_values(declarations, stored):
    values = {}
    for key in sorted(declarations):
        if key in stored:
            values[key] = stored[key]
        elif declarations[key].get("default") is not None:
            values[key] = declarations[key]["default"]
    return values


def render_claude(
    kit_root, template, modules, values, module_declarations, value_declarations
):
    text = template.read_text(encoding="utf-8")
    rendered_values = resolved_values(value_declarations, values)

    for key, value in rendered_values.items():
        text = text.replace(f"{{{{{key}}}}}", value)

    remaining = sorted(set(PLACEHOLDER.findall(text)))
    if remaining:
        raise ProjectError(
            2,
            "failed to render CLAUDE.md",
            f"template placeholders have no value: {', '.join(remaining)}",
            "declare and collect every template value, then retry",
        )

    imports = [
        f"@{module_entry_point(kit_root, name).as_posix()}"
        for name in modules
        if module_declarations[name].get("load") == "always"
    ]
    block = "\n".join([IMPORTS_START, *sorted(imports), IMPORTS_END])
    pattern = re.compile(
        rf"^{re.escape(IMPORTS_START)}$.*?^{re.escape(IMPORTS_END)}$",
        flags=re.MULTILINE | re.DOTALL,
    )
    text, replacements = pattern.subn(block, text)
    if replacements != 1:
        raise ProjectError(
            2,
            "failed to render CLAUDE.md",
            "the template must contain exactly one complete `kit:imports` block",
            "restore or fix template/CLAUDE.md, then retry",
        )
    return text, rendered_values


def markdown_bullet(path, description):
    return textwrap.fill(
        f"- `{path}` - {description}",
        width=80,
        subsequent_indent="  ",
    )


def wrapped_prose(text):
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return "\n\n".join(
        textwrap.fill(
            " ".join(paragraph.split()),
            width=80,
            break_long_words=False,
            break_on_hyphens=False,
        )
        for paragraph in paragraphs
    )


def project_context_block(context):
    return f"# Project context\n\n{wrapped_prose(context)}"


def repository_layout_block(version_control, repositories):
    lines = [
        "## Repository layout",
        "",
        f"Version control: {version_control}.",
        "",
        *wrapped_prose(
            "The outer repository holds project instructions, Rulekit state, "
            "and workspace-level intake and coordination files."
        ).splitlines(),
        "",
        "Inner repositories:",
        "",
    ]
    lines.extend(f"- `{repository['path']}/`" for repository in repositories)
    return "\n".join(lines)


def file_map_block(draft):
    return "\n".join(
        markdown_bullet(f"{repository['path']}/", repository["purpose"])
        for repository in draft["brief"]["repositories"]
    )


def render_project(template, draft, rendered_values):
    text = template.read_text(encoding="utf-8")
    if "VERSION_CONTROL" not in rendered_values:
        raise ProjectError(
            2,
            "failed to render PROJECT.md",
            "the manifest must declare a resolved `VERSION_CONTROL` value",
            "restore or fix the manifest value declaration, then retry",
        )
    blocks = {
        "FILE_MAP": file_map_block(draft),
        "PROJECT_CONTEXT": project_context_block(draft["brief"]["context"]),
        "REPOSITORY_LAYOUT": repository_layout_block(
            rendered_values["VERSION_CONTROL"], draft["brief"]["repositories"]
        ),
    }

    for key, block in blocks.items():
        marker = f"{{{{{key}}}}}"
        if text.count(marker) != 1:
            raise ProjectError(
                2,
                "failed to render PROJECT.md",
                f"the template must contain exactly one `{marker}` marker",
                "restore or fix template/PROJECT.tmpl.md, then retry",
            )
        text = text.replace(marker, block)

    remaining = sorted(set(PLACEHOLDER.findall(text)))
    if remaining:
        raise ProjectError(
            2,
            "failed to render PROJECT.md",
            f"template markers have no renderer: {', '.join(remaining)}",
            "declare a renderer for every PROJECT.md template marker",
        )
    return text


def gitignore_pattern(path):
    escaped = "".join(
        f"\\{character}" if character in "!#*?[] " else character
        for character in path
    )
    return f"/{escaped}/"


def render_gitignore(repositories):
    patterns = sorted(
        gitignore_pattern(repository["path"]) for repository in repositories
    )
    return "\n".join(patterns) + "\n"


def render_tree(
    kit_root,
    destination,
    draft,
    module_declarations,
    value_declarations,
    kit_commit,
):
    problems = specification_problems(
        draft, module_declarations, value_declarations, require_complete=True
    )
    if problems:
        raise ProjectError(
            1,
            f"refused to render project tree: {destination}",
            "; ".join(problems),
            "complete the project specification and retry",
        )
    if destination.is_symlink() or not destination.is_dir():
        raise ProjectError(
            2,
            f"failed to render project tree: {destination}",
            "the render destination is not a regular directory",
            "provide a new empty staging directory and retry",
        )
    if any(destination.iterdir()):
        raise ProjectError(
            2,
            f"failed to render project tree: {destination}",
            "the render destination is not empty",
            "provide a new empty staging directory and retry",
        )

    claude, values = render_claude(
        kit_root,
        kit_root / "template" / "CLAUDE.md",
        draft["modules"],
        draft["values"],
        module_declarations,
        value_declarations,
    )
    (destination / "CLAUDE.md").write_text(claude, encoding="utf-8")

    project = render_project(
        kit_root / "template" / "PROJECT.tmpl.md",
        draft,
        values,
    )
    (destination / "PROJECT.md").write_text(project, encoding="utf-8")

    repositories = draft["brief"]["repositories"]
    for repository in repositories:
        (destination / repository["path"]).mkdir(parents=True)

    uses_git = values["VERSION_CONTROL"].casefold() == "git"
    if uses_git:
        (destination / ".gitignore").write_text(
            render_gitignore(repositories), encoding="utf-8"
        )

    copied_rules = 0
    for module in draft["modules"]:
        for source in module_rule_files(kit_root, module):
            relative = source.relative_to(kit_root / "template")
            output = destination / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, output)
            copied_rules += 1

    copied_scaffolds = 0
    for module in draft["modules"]:
        for name in module_declarations[module]["scaffold"]:
            source = kit_root / "template" / name
            output = destination / scaffold_output_path(name)
            if output.exists():
                raise ProjectError(
                    2,
                    "failed to prepare module scaffold",
                    f"multiple generated files use the path: {output}",
                    "fix the manifest so every generated path is unique",
                )
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, output)
            copied_scaffolds += 1

    state = {
        "kit": {"commit": kit_commit},
        "modules": sorted(draft["modules"]),
        "values": values,
    }
    with (destination / STATE_FILENAME).open("w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    return {
        "copied_rules": copied_rules,
        "copied_scaffolds": copied_scaffolds,
        "repositories": len(repositories),
        "uses_git": uses_git,
    }
