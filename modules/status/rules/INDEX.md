## Status: where the project stands and what comes next

`status.md` in the project root is a short snapshot of the project's state.
The owner often comes back to a project after a long break and needs to see at
once what was done last, what is in progress, what can be taken next, and which
external events or actions are coming up. Keep it current, and short enough to
read in a minute.

It is a snapshot, not a log. Each update replaces what is no longer true;
history lives in version control.

## File format

```markdown
# Status

Updated: YYYY-MM-DD

## Last session

## In progress

## Next

## Upcoming
```

- `Updated` - the date of the last update
- `Last session` - what the most recent session did, in prose or points. About
  five lines, a little more when it earns it. Replace it at each update rather
  than appending to it
- `In progress` - what is being worked on now and where it stopped, about five
  lines. When nothing is, say so
- `Next` - a few options for what to take next, in prose or points, each
  linking to its details when there are any. Every option carries a short
  reason why it is worth taking now, so the owner can choose between them
  without opening the details. Going through the inbox is always an option;
  when there is truly nothing, say so
- `Upcoming` - external events and actions: appointments, scheduled dates,
  recurring commitments, follow-ups to send, letters to write. Project work
  belongs in `Next`, not here

`Upcoming` is one list, nearest first. Each item begins with a date in
`YYYY-MM-DD` form, a recurrence, or `no date`:

```markdown
- 2026-10-05 dentist appointment at 10:30
- every Monday English lesson
- no date write to the repair shop about the tablet
```

## Keeping it current

- When the owner asks where things stand, what was done last, or what is next,
  use the `status` skill
- When the owner ends the session or asks to update the status, use the
  `wrap-up` skill
- When the work of a session looks finished, for example after a commit,
  suggest `wrap-up` in one line. Do not run it unasked
- When a dated `Upcoming` item has passed, ask the owner whether to remove it
  or replace it with a follow-up. Do not remove it on your own
