## Backlog: developed tasks and findings

`backlog/` is the owner's personal list of developed tasks and considered
findings that are not complete. It may hold a defect that unrelated work
exposed, drift with no current symptom, an idea worth preserving, or a rejected
proposal whose explanation prevents repeated investigation. It does not
automatically block current work or become external communication.

A backlog item is a developed version of an inbox thought. It records enough
context, evidence, constraints, and open questions to support future planning.
It is not the execution plan itself.

## Item format

Keep one item per Markdown file at `backlog/<slug>.md`. The slug describes the
task or problem, not merely the file or area where it was found. A descriptive
slug makes the item recognisable in links and helps find possible duplicates.

```markdown
---
worth: later
where: path/to/relevant-place:123
plan: plans/example-task.md
added: YYYY-MM-DD
---
# A concrete task or problem

Explain what should change, why the task is worth preserving, what is already
known or has been tried, and any constraints or open questions that will matter
when the work is planned.
```

The frontmatter fields are:

- `worth: yes | later | rejected` records the value decision, not execution
  status or schedule
  - `yes` means the task is accepted as worth doing. It may still be blocked or
    deliberately unscheduled
  - `later` means the value decision depends on an unknown or a future
    condition. The body names what would settle it
  - `rejected` means the task was deliberately declined. Keep it only while its
    explanation prevents the same idea from being rediscovered and debated
    again; otherwise delete it
- `where` is optional. When useful, it points to the most relevant place: a
  file or line, document, URL, device, command, or another concrete source. It
  is a navigation hint and may become stale
- `plan` is optional. When present, it links the current execution plan and
  shows that the task has been selected for planning or work
- `added: YYYY-MM-DD` records when the item entered the backlog and is never
  updated

When presenting the backlog, order `yes` items first, then `later`, then
`rejected`; within each group, show older items first.

The H1 is the task title. The body has no required sections and may be short or
detailed. Preserve enough reasoning that a future reader can understand the
task without the conversation that produced it. Do not turn the item into a
step-by-step execution plan. When the task is selected, recheck it against the
current project and create a separate plan if the work needs one.

Related items may link to one another with ordinary relative Markdown links.
Do not add a dependency system until real tasks need one.

## Maintaining the backlog

- Capture raw thoughts in `inbox.md`; move or rewrite one into `backlog/` only
  after it has been considered and developed into a task worth preserving
- A thought, review finding, or deferred change is not automatically a backlog
  item. Ask the owner before adding it
- Before adding an item, use its slug and `where` to find possible duplicates,
  then compare the underlying task. If an existing item describes the same
  task, leave it alone or update it when the new information changes its
  description or value decision; do not create a second file
- Do not treat a shared source path as proof of duplication. One place may have
  several unrelated problems
- Do not use checkboxes or an `in progress` marker as a second task tracker.
  The optional `plan` link already shows when a task has entered active planning
  or work
- Reading or reviewing the backlog is not permission to perform its tasks
- Remove an item when its work is complete, whether or not version-control
  history preserves the old context
- A `rejected` item may remain when its explanation still prevents repeated
  investigation. Remove it once that explanation no longer earns its place
