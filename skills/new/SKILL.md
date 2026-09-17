---
name: new
description: Create a new rulekit-managed project by checking a target, interviewing the user, rendering an exact preview, and applying it after approval. Use when the user asks to create or initialize a project with rulekit.
argument-hint: [target-directory] [instructions...]
allowed-tools:
  - AskUserQuestion
  - Read
  - 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py" *)'
  - 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/answers.py" *)'
  - 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/build.py" *)'
  - 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/check-target.py" *)'
---

# New project

Treat the first argument as the target only when it clearly uses path syntax:
it starts with `.`, `/`, or `~`, or contains a path separator. Otherwise use
the current working directory and treat every argument as interview prose. Use
`./name` for a relative target. A target path that contains spaces must be
quoted.

Follow the conversation language established by higher-level instructions from
the first response. Do not switch languages because this skill is written in
English.

Do not call the `advisor` tool when the user instructions, manifest, and script
output already determine the simple choices. Use it only when a genuinely
complex decision remains unresolved.

Collect and validate answers, then render the project into the target's private
preview workspace. Apply that exact preview to the project root only after the
user explicitly approves it.

## Check the inputs

Run these commands in order. Use a separate Bash call for every command. Do not
combine them with `&&`, `;`, or auxiliary commands.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/check-target.py" --target "<target>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py" check
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py" list
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py" values
```

Use the target path reported by `check-target.py` from then on. Stop if either
check fails. Report the script output; do not bypass a refusal or mutate the
target by hand to make it pass.

Initialize the preview workspace:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/answers.py" --target "<target>" init
```

Use the resolved target reported by `check-target.py`. `init` creates a missing
target when needed and writes `.kit-preview/answers.json`. Stop on refusal; an
existing `.kit-preview` belongs to an earlier attempt and must not be
overwritten.

Read `${CLAUDE_SKILL_DIR}/references/project-interview.md`, then ask the script
for the temporary brief contract:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/answers.py" --target "<target>" brief --list
```

Treat the reported keys and argument shapes as the sole brief storage contract.
The reference guides the conversation; it does not define the JSON or CLI.

## Confirm inferred answers

Before asking individual questions, infer only answers that follow
unambiguously from the invocation or active higher-level instructions. Do not
guess from weak or indirect signals. If the user's intent is uncertain, leave
the answer unresolved and ask. An established
conversation language may prefill `CONVERSATION_LANGUAGE`. Explicit phrases
such as "non-coding project" or "without backlog" may answer module choices.
Silence does not answer an optional choice.

A declared value default is an inferred answer unless the invocation or active
instructions unambiguously supply a replacement. Include the default in the
summary and do not ask about it separately when the summary is accepted.

Required standalone modules are automatic, not inferred, and cannot be
removed. If a user instruction conflicts with them, explain the conflict and
keep them selected.

When at least one answer was inferred, show one summary containing:

- automatic required modules
- every inferred choice and value
- every inferred inner repository path and purpose
- every unresolved choice, value, or material project fact

Show the synthesized English context alone in a clearly separated project-brief
block. Explain that it will be the main project description available to future
assistants after this conversation is gone. Use `AskUserQuestion` to ask one
confirmation question about the inferred decisions and whether the context
describes the project correctly. Do not put any unresolved question in the
same interaction.

If the user confirms, store the displayed model-written context and the other
accepted answers through `answers.py`; do not expand, rewrite, or enrich the
context afterward. Otherwise the user would review one artifact and receive
another. If the user requests a review or provides corrections, discuss only
the disputed inferred parts, then show the revised context before storing it.
After the inferred answers are accepted, ask each unresolved question
separately.

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
python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/answers.py" --target "<target>" modules <selected-module>...
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
python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/answers.py" --target "<target>" value <key> <value>
```

Optional values without an answer may remain absent.

## Collect the project brief

Follow `references/project-interview.md`. Use the invocation and earlier
conversation before asking follow-up questions. The context is an English
orientation artifact for a future assistant, regardless of the conversation
language.

After each accepted brief answer, call `answers.py brief` with exactly the key
and argument shape reported by `brief --list`. A repositories update always
replaces the complete list, so include every accepted repository in one call.
If the user revises an answer, call the same command again with the replacement.
Interpret the user's meaning and ask about material ambiguity before drafting
the context. Then pass the final model-written English draft the user reviewed;
do not synthesize a different or richer version between review and storage.

Do not expose storage keys as interview questions, invent new keys, write
repository-layout or file-map Markdown, or create or edit `answers.json`
directly.

## Validate the answers

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/answers.py" --target "<target>" check
```

If it reports multiple problems, address all of them through the interview and
the appropriate `answers.py` commands, then run `check` again. Never create or
edit `answers.json` directly.

## Prepare the preview

When validation succeeds, run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/build.py" --target "<target>" prepare
```

Stop if preparation fails. Do not replace, repair, or remove preview files by
hand.

When preparation succeeds, report the resolved target, answers file path,
preview path, exact selected modules and values, concise project context, and
inner repositories. State that the generated files are ready for inspection
inside `.kit-preview/files` but have not been applied to the project root.

Use `AskUserQuestion` to ask whether to apply the preview now or inspect it
first. Put the apply option first and apply only when the user selects it. If
the user requests inspection, preserve the preview, show it with an available
review method, then ask the same question again. Do not assume that revdiff or
any other specific review tool is available. Preserve `.kit-preview` and stop
unless the apply option is selected.

When the user approves, run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/new/scripts/build.py" --target "<target>" apply
```

Stop and report the script output if application fails. Do not repair, copy, or
remove files by hand.

When application succeeds, report the resolved target and the exact selected
modules, values, and inner repositories. State that the generated files,
including the finished `PROJECT.md`, were applied and the temporary
`.kit-preview` workspace was removed.
