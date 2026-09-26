---
name: sync
description: >-
  Compare an adopted project's rendered core rules and selected modules with
  its stored Rulekit baseline and the current catalogue, then guide
  owner-approved synchronization one item at a time.
argument-hint: [project-directory]
allowed-tools:
  - AskUserQuestion
  - Edit
  - Read
  - Write
  - 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/skills/sync/scripts/detect.py" *)'
  - 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/skills/sync/scripts/finalize.py" *)'
  - 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/skills/sync/scripts/show.py" *)'
---

# Synchronize core rules and modules

Compare rendered core rules plus the modules selected in the adopted project's
`.kit.json`. Scaffolds are project-owned after creation and remain outside
sync. Detection is mechanical, but direction, wording, and acceptance belong
to the owner. Never merge or copy a rule automatically.

Treat the first argument as the target path. Use the current working directory
when the argument is empty. The active Rulekit catalogue is always
`${CLAUDE_PLUGIN_ROOT}`.

## Detect differences

Run this command on one physical line:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/sync/scripts/detect.py" --target "<target>"
```

This initial invocation requires clean Git working trees at both
`${CLAUDE_PLUGIN_ROOT}` and the target root. If either repository has tracked or
untracked changes, report the refusal and stop until the owner commits or
reverts them. Do not use `--allow-dirty` for the initial invocation.

The script compares three byte-exact snapshots for rendered core and every
selected module:

- `baseline`: the Rulekit commit recorded in `.kit.json`
- `project`: the project's current rendered core or copied module
- `kit`: the current Rulekit working tree

The core snapshot contains the files declared by `core.rules` in the manifest.
It is rendered from each version's templates with the modules and values stored
in the project's `.kit.json`. Core scaffolds are not included.

The script reports only items that differ. Interpret its statuses as:

- `project-only`: only the project changed from baseline
- `kit-only`: only Rulekit changed from baseline
- `converged`: project and Rulekit contain the same change from baseline
- `diverged`: both changed and no longer match each other

If rendered core and every selected module are unchanged, report that no sync
is needed and stop.
If detection fails, report the refusal and stop. Do not repair `.kit.json` or
substitute another baseline.

## Review one item at a time

For reported rendered core, run this command on one physical line:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/sync/scripts/show.py" --target "<target>" --core
```

For each reported module, run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/sync/scripts/show.py" --target "<target>" --module "<module>"
```

Skip an item already reported as `converged`. The script shows
baseline-to-project, baseline-to-kit, and current-kit-to-project diffs and the
physical project and Rulekit template paths for every file. Core diffs show
rendered content; edit the Rulekit template, never replace it with a rendered
project file. Use the reported paths; do not run shell commands to locate the
files or copy them merely to prepare the comparison.

Explain the material difference in plain language, then ask the owner what the
shared rule should say. Use exactly one question in each `AskUserQuestion`
call. Resolve one item at a time.

Use these defaults as recommendations, never as automatic choices:

- for `project-only`, propose promoting portable behavior into Rulekit
- for `kit-only`, propose bringing the current Rulekit module into the project
- for `diverged`, compose a merged rule with the owner instead of choosing a
  side

Project-specific behavior does not belong in shared Rulekit core or a module.
When a project rule expresses a portable principle with local wording,
generalize the wording before proposing it for Rulekit.

## Apply an approved decision

Before editing, show the exact proposed diff for every affected project and kit
file. Apply only the owner's explicitly approved wording. The intended resolved
state is byte-identical content between the project and Rulekit's current
rendered output. Module files therefore match their Rulekit source files;
project core files match the output of their Rulekit templates. A generalized
merge replaces the local wording in the project as well as updating Rulekit.

Apply each accepted decision immediately, then recheck on one physical line:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/sync/scripts/detect.py" --target "<target>" --allow-dirty
```

The flag is only for rechecking changes approved and applied during this sync
run; never use it to bypass an initial cleanliness refusal. An item is resolved
for this run when it is `unchanged` or `converged`. Continue with the remaining
reported items. If the owner keeps a project-local difference, leave it
unresolved and say that future sync runs will report it again.

Do not change module selection, sync scaffold files, edit `.kit.json` by hand,
or commit either repository.

When only `unchanged` or `converged` items remain, report the changed files.
If this run changed Rulekit files, name `${CLAUDE_PLUGIN_ROOT}` as the repository
the owner must commit and use `AskUserQuestion` to wait for confirmation that
the commit is complete. If this run changed only project files, do not request
an unrelated Rulekit commit.

Do not say that committing Rulekit moves the stored baseline. After the owner
confirms the commit, or immediately when this run did not change Rulekit files,
run this command on one physical line:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/sync/scripts/finalize.py" --target "<target>"
```

The finalizer must verify that rendered project core and every selected module
match current Rulekit, and that the source templates and modules producing
those bytes are committed in `HEAD`. If it refuses, report the reason and stop;
do not edit `.kit.json` or substitute a commit by hand.

When the finalizer advances `.kit.json`, report that file as changed and use
`AskUserQuestion` to wait for confirmation that the owner committed the target
project repository. The sync is complete only after that confirmation. If the
finalizer reports that the baseline was already current, no state commit is
needed.
