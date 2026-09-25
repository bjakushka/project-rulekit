## Plans: guides for active work

`plans/` holds execution plans for work that needs more structure than a
backlog item. Keep one plan per Markdown file at
`plans/yyyymmdd-plan-name.md`, using the date when planning started.

A plan is a working guide for the owner and the assistant. It should make the
work understandable, resumable after a break, and possible to hand off without
turning it into instructions for an autonomous executor. Read only the plan
related to the current work; do not load the whole directory automatically.

## Plan format

Start with an H1 title followed by a status. The allowed values are `active`
and `complete`. Keep a paused or blocked plan active and describe the blocker
in its body instead of adding another status.

A useful plan contains:

- `Goal`: the expected result, why it matters, and what done means
- `Context`: only facts, constraints, dependencies, and sources needed for this
  work
- `Steps`: ordered, coherent results with concrete actions and checks
- `Completion`: final conditions that show the whole plan is complete

Add `Scope` when it is useful to name what is included, excluded, or deferred.
Add `Approach` when the chosen solution or its reasoning is not obvious. Add
`Follow-up` for external or deferred work that should not look complete merely
because the local changes are done. Omit optional sections when they add no
value.

A step may name affected files or areas and may include several paragraphs
when the result cannot be explained clearly in one line. Keep general project
rules and standard quality commands in project instructions; repeat only the
constraints and checks specific to this work.

Checks describe both what to do and what result is acceptable. They may be
tests, linters, commands, manual scenarios, diff review, or verification of
documents and facts, depending on the project and the work.

## Backlog relationship

A plan may be created from a backlog item or independently. When a backlog item
exists, link both directions: add a relative `Source` link in the plan and set
the backlog item's optional `plan` field. Creating a plan does not complete,
delete, or otherwise rewrite the backlog item.

Keep both links current. When either file is removed, remove or update the link
from the remaining file.

## Maintaining a plan

- Mark completed actions with ordinary Markdown checkboxes
- Add newly discovered steps and blockers where they affect the work
- Update the scope, order, or chosen approach when the work changes
- Keep the plan useful for the next work session instead of preserving an
  obsolete original version
- Record durable project decisions in the project's decision records when they
  exist, and link to them from the plan; keep only the context needed to perform
  the work in the plan itself

When the work is complete, the owner decides whether to delete the plan or keep
it with `Status: complete`. Do not delete, archive, move, or preserve completed
plans automatically. Before finishing, move durable results to the appropriate
project documentation or decision record so the plan is not their only source.
