---
name: sync
description: >-
  Compare an adopted project's selected rule modules with its stored Rulekit
  baseline and the current catalogue, then guide owner-approved synchronization
  one module at a time.
argument-hint: [project-directory]
allowed-tools:
  - AskUserQuestion
  - Edit
  - Read
  - Write
  - 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/skills/sync/scripts/detect.py" *)'
  - 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/skills/sync/scripts/show.py" *)'
---

# Synchronize rule modules

Compare only the modules selected in the adopted project's `.kit.json`.
Detection is mechanical, but direction, wording, and acceptance belong to the
owner. Never merge or copy a rule automatically.

Treat the first argument as the target path. Use the current working directory
when the argument is empty. The active Rulekit catalogue is always
`${CLAUDE_PLUGIN_ROOT}`.

## Detect differences

Run this command on one physical line:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/sync/scripts/detect.py" --target "<target>"
```

The script compares three byte-exact module snapshots:

- `baseline`: the Rulekit commit recorded in `.kit.json`
- `project`: the project's current copied module
- `kit`: the current Rulekit working tree

It reports only selected modules that differ. Interpret its statuses as:

- `project-only`: only the project changed from baseline
- `kit-only`: only Rulekit changed from baseline
- `converged`: project and Rulekit contain the same change from baseline
- `diverged`: both changed and no longer match each other

If every selected module is unchanged, report that no sync is needed and stop.
If detection fails, report the refusal and stop. Do not repair `.kit.json` or
substitute another baseline.

## Review one module at a time

For each reported module except `converged`, run this command on one physical
line:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/sync/scripts/show.py" --target "<target>" --module "<module>"
```

The script shows baseline-to-project, baseline-to-kit, and current-kit-to-project
diffs and the physical project and Rulekit paths for every module file. Use
those reported paths; do not run shell commands to locate the files or copy
them merely to prepare the comparison.

Explain the material difference in plain language, then ask the owner what the
shared rule should say. Use exactly one question in each `AskUserQuestion`
call. Resolve one module at a time.

Use these defaults as recommendations, never as automatic choices:

- for `project-only`, propose promoting portable behavior into Rulekit
- for `kit-only`, propose bringing the current Rulekit module into the project
- for `diverged`, compose a merged rule with the owner instead of choosing a
  side

Project-specific behavior does not belong in a shared Rulekit module. When a
project rule expresses a portable principle with local wording, generalize the
wording before proposing it for Rulekit.

## Apply an approved decision

Before editing, show the exact proposed diff for every affected project and kit
file. Apply only the owner's explicitly approved wording. The intended resolved
state is byte-identical module content in the project and current Rulekit. A
generalized merge therefore replaces the local wording in the project as well
as updating Rulekit.

Apply each accepted decision immediately, then run `detect.py` again. A module
is resolved for this run when it is `unchanged` or `converged`. Continue with
the remaining reported modules. If the owner keeps a project-local difference,
leave it unresolved and say that future sync runs will report it again.

Do not update `.kit.json`, change module selection, sync core or scaffold files,
or commit either repository. The stored baseline can advance only after the
owner commits the accepted Rulekit changes; that is outside this version of the
skill.

When only `unchanged` or `converged` modules remain, report the changed files.
If this run changed Rulekit files, name `${CLAUDE_PLUGIN_ROOT}` as the repository
the owner must commit and use `AskUserQuestion` to wait for confirmation that
the commit is complete. If this run changed only project files, do not request
an unrelated Rulekit commit.

Do not say that committing Rulekit moves the stored baseline. After the owner
confirms the commit, explain that `.kit.json` remains unchanged in this version
of the skill. A new Rulekit commit only makes a later baseline update possible.
