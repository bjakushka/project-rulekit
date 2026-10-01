---
name: reflect
description: Review the current session and propose what is worth keeping - mistakes made, knowledge gained, what the owner's behaviour showed, and where each finding belongs. Use when the owner asks to reflect on the session, review how it went, or close it out.
disable-model-invocation: true
allowed-tools:
  - AskUserQuestion
  - 'Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/selected-modules.py *)'
  - Glob
  - Read
---

Reflect on the session that just happened. The subject is the session, not the
state of the project: what was done, what was learned, what that implies. A
survey of what has drifted apart across project files is a different job.

Read the project's instructions first, so nothing already written is proposed
again: `CLAUDE.md`, and the entry point of each module the script below
reports.

## What qualifies

Keep only what still matters in six months.

Include:

- strategic approaches worked out during the session, and why they were chosen
- constraints and decisions that emerged, with the reasoning behind them
- conventions noticed more than once
- gaps in the instructions that this session exposed
- what the owner's corrections revealed about how they want work done

Exclude:

- the specific bug fixed or feature built
- a workaround used once
- file contents, command output, anything the repository already records
- history for its own sake: what changed is in version control

Ask of each finding: would this speed up the work in six months, or is it a
detail that belongs in the commit it came from?

**If nothing qualifies, say so and stop.** Report that the session produced no
new strategic knowledge, and do not ask the owner to choose between findings
that were manufactured to fill the report.

## The report

Four sections. Where a section has nothing substantive, write "nothing to
report" rather than padding it. Every claim cites a specific moment from the
session. Propose; never apply.

Write as a detached analyst, not a coach.

### 1. What went wrong

Independent of the instructions - what did this session get wrong?

- assumptions about the task, the project, or the owner's intent
- an approach taken where a better one was available, and what it was
- a check or tool call skipped that would have prevented an error
- an answer given from memory where verification was warranted

### 2. What was learned

Strategic knowledge the session produced: approaches, constraints, decisions
and the reasoning behind them, directions ruled out and why.

Name a target for each item - which file, which section. Where that target is
an instruction file, leave the wording to section 4 and say so here; every diff
in the report belongs to that one section.

### 3. What the owner's behaviour showed

Report a pattern only with evidence from at least two moments in this session.
A single event belongs in section 1 or 2.

- what the owner accepted unchanged, and what kind of output it was
- what the owner reworked or rejected, and what the correction was
- corrections that information available at the time would have avoided

State the evidence, not an inferred preference:

- weak: "the owner prefers short answers"
- strong: "in three places - the migration plan, the API sketch, the error
  message draft - the owner cut the output by half. For a draft or a review,
  start shorter than feels complete."

### 4. What the instructions should say

Gaps this session exposed, and ambiguities the owner had to resolve by hand.

Every proposed change is a diff. A suggestion that cannot be written as one is
dropped rather than described in prose.

```diff
# file: rules/plans.md, section "Maintaining a plan"
- Mark completed actions with ordinary Markdown checkboxes
+ Mark completed actions with ordinary Markdown checkboxes, and record what
+ verified them. A step marked done without saying how it was checked reads as
+ complete when it is not.
```

A new section appears as pure `+` lines, with its target file and heading.

## Where findings belong

The project decides this, not the kit. Ask it what it has:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/selected-modules.py
```

The script reports the modules this project installed and what each is for.
Match each finding to one of them and say where it should go. Where nothing
fits, say so rather than inventing a destination.

Do not look inside the Rulekit plugin for modules the project has not
installed. What the catalogue could offer is not the question.

## Confirming with the owner

Use `AskUserQuestion` to let the owner choose what to keep. Build the options
from what was actually found:

- first option: everything, each item to the destination proposed for it
- then the most significant findings, one per option, each labelled with its
  destination
- last: none

Where a single finding was made, ask about that one rather than building a list.

Apply exactly what the owner selects, to the destination shown in the label. A
choice of what to keep is not a choice to move something elsewhere: to change a
destination, the owner says so.
