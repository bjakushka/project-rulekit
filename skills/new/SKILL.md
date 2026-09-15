---
name: new
description: Start a rulekit-managed project by checking a target and interviewing the user for its modules and template values. Use when the user asks to create or initialize a project with rulekit.
argument-hint: [target-directory] [instructions...]
allowed-tools:
  - AskUserQuestion
  - 'Bash(mktemp -d /tmp/rulekit-new.XXXXXX)'
  - 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py" *)'
  - 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/answers.py" *)'
  - 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/check-target.py" *)'
---

# New project

Treat the first argument as the target directory path. If it is absent, use the
current working directory. Treat the remaining arguments as user instructions
for the interview. A target path that contains spaces must be quoted; use `.`
when passing instructions for the current directory.

Follow the conversation language established by higher-level instructions from
the first response. Do not switch languages because this skill is written in
English.

Do not call the `advisor` tool when the user instructions, manifest, and script
output already determine the simple choices. Use it only when a genuinely
complex decision remains unresolved.

This version only collects and validates temporary answers. It does not create
the target, render templates, or copy files into the target.

## Check the inputs

Run these commands in order. Use a separate Bash call for every command. Do not
combine them with `&&`, `;`, or auxiliary commands.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/check-target.py" "<target>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py" check
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py" list
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py" values
```

Use the target path reported by `check-target.py` from then on. Stop if either
check fails. Report the script output; do not bypass a refusal or mutate the
target to make it pass.

Create a private temporary directory and initialize the answers file:

```bash
mktemp -d /tmp/rulekit-new.XXXXXX
python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/answers.py" --file "<temporary-directory>/answers.json" init
```

Use the directory printed by `mktemp` in the next command. Keep it so the user
can inspect the result.

## Confirm inferred answers

Before asking individual questions, infer answers that follow unambiguously
from the invocation or active higher-level instructions. An established
conversation language may prefill `CONVERSATION_LANGUAGE`. Explicit phrases
such as "non-coding project" or "without backlog" may answer module choices.
Silence does not answer an optional choice.

Required standalone modules are automatic, not inferred, and cannot be
removed. If a user instruction conflicts with them, explain the conflict and
keep them selected.

When at least one answer was inferred, show one summary containing:

- automatic required modules
- every inferred choice and value
- every unresolved choice and value

Ask one confirmation question: use these decisions, or review the inferred
answers individually. If the user confirms, store the inferred answers through
`answers.py` and ask only the unresolved questions. If the user requests a
review, ask both inferred and unresolved questions individually. If the user
provides corrections in free text, apply the clear corrections and ask only
about anything still ambiguous or unresolved.

## Choose modules

Use only names and descriptions reported by `manifest.py list`.
Ask exactly one question in each user-interaction call. Never batch module or
value questions.

1. Start the selection with every required module that is not part of a group
2. For each unresolved module group, ask one question and add the chosen
   member. A required group must have one choice; an optional group may have
   none
3. Ask separately about each unresolved optional standalone module
4. After every module answer or accepted inference summary, replace the stored
   module list with the complete current selection, even when an optional
   module was skipped and the selection did not change:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/answers.py" --file "<answers-file>" modules <selected-module>...
```

Let the script sort and validate the names. If the user revises a choice, call
`modules` again with the revised complete selection.

## Collect values

Ask for each value not confirmed in the inference summary, one at a time.
Include its prompt and default in the question. Use earlier instructions as
context. If the user accepts a default, pass that exact value. Do not invent a
value for a required field.

After each answer, store it through the script:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/answers.py" --file "<answers-file>" value <key> <value>
```

Optional values without an answer may remain absent.

## Validate the answers

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/answers.py" --file "<answers-file>" check
```

If it reports multiple problems, address all of them through the interview and
the appropriate `answers.py` commands, then run `check` again. Never create or
edit `answers.json` directly.

When validation succeeds, report the resolved target, the answers file path,
and the exact selected modules and values. State that the target is unchanged
and generation is not implemented yet.
