---
name: wrap-up
description: >-
  Bring the project's status.md up to date at the end of a session: replace the
  last session, update the work in progress and the options for what is next,
  and settle passed and new external events with the owner. Use when the owner
  says the session is ending, asks to wrap up, or asks to update the status.
disable-model-invocation: false
allowed-tools:
  - AskUserQuestion
  - 'Bash(python3 ${CLAUDE_PROJECT_DIR}/.claude/skills/status/scripts/report.py *)'
  - Read
---

Bring `status.md` in the project root up to date with this session. This skill
is the procedure for updating it. It maintains the status only: reviewing how
the session went is a different job.

The file's format and limits are defined in `rules/status/INDEX.md`, which is
loaded with the project instructions. Reread it if it is not in view.

## 1. Run the report

The `status` skill owns the report script; both skills come from the same
module, so it is always there:

```bash
python3 ${CLAUDE_PROJECT_DIR}/.claude/skills/status/scripts/report.py --target "${CLAUDE_PROJECT_DIR}"
```

Take today's date, the passed items and the structure notes from the report;
do not recompute them. If the script exits with an error, give the owner its
`result`, `reason` and `next`, and stop.

## 2. Read the file and recall the session

Read `status.md`. Then go over this session: what was done, what is
unfinished and where it stopped, what came up to take later, and any external
event or action that was mentioned, such as an appointment, a date, or a letter
or follow-up to send.

## 3. Ask the owner

Ask in one batch, before drafting:

- for each passed dated `Upcoming` item from the report: remove it, or replace
  it with a follow-up the owner names
- whether anything is missing that this session cannot show: progress made
  elsewhere, new events, other options for what is next

Skip the batch when there are no passed items and the session leaves nothing
in doubt.

## 4. Draft the update

Build the new file from the old one, the session, and the owner's answers.
Use only what those show; do not invent.

- `Updated` - today's date from the report
- `Last session` - replace it with what this session did
- `In progress` - remove what got done, record what is unfinished and where it
  stopped
- `Next` - drop options that are done or no longer relevant, add new ones, and
  keep a short reason on every option
- `Upcoming` - apply the owner's answers on passed items, add new events and
  actions, keep the list nearest first
- fix the structure notes from the report, if any

## 5. Show it and write

Show the proposed change the way the project's review rules prescribe, and
write it only after the owner approves. Then confirm in one line that the
status is updated.
