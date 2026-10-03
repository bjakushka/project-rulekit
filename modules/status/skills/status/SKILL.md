---
name: status
description: >-
  Report where the project stands: what the last session did, what is in
  progress, what can be taken next, and which external events are coming up.
  Use when the owner asks where things stand, what was done last, what to do
  next or what is coming up, or comes back to the project after a break.
disable-model-invocation: false
allowed-tools:
  - AskUserQuestion
  - 'Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/report.py *)'
  - Read
---

Tell the owner where the project stands, from `status.md` in the project root.
This skill only reads. Updating the file is the `wrap-up` skill's job, and
nothing here changes a file.

The file's format is defined in `rules/status/INDEX.md`, which is loaded with
the project instructions. Reread it if it is not in view.

## 1. Run the report

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/report.py --target "${CLAUDE_PROJECT_DIR}"
```

The report holds the facts about dates: today, how old the status is, and which
`Upcoming` items have passed or are near. Take them from the report; do not
recompute them.

If the script exits with an error, give the owner its `result`, `reason` and
`next`, and stop.

## 2. Read the file

Read `status.md` for the content the report does not carry: the last session,
the work in progress, and the options in `Next`.

## 3. Tell the owner

Keep it short enough to take in at a glance. Summarize; do not paste the file.

- If the status is `never` updated, or stale by the report, say so first: what
  follows may not match reality
- Then the time-bound items: passed ones, which `wrap-up` will ask about, and
  those within the next 7 days
- Then the sections in the file's order: the last session, the work in
  progress, and the `Next` options, each with its reason
- Later and undated `Upcoming` items in one or two lines
- Structure notes from the report, if any, in one line

## 4. Offer to go deeper

Ask the owner whether to look further, offering only what this project has,
for example the inbox, the backlog, the active plans, or uncommitted changes in
its repositories. Go no further than the owner chooses.
