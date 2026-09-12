<!--
Project facts and file map. Not LLM behavior rules (those live in CLAUDE.md).
-->

# Project context

{{ONE_OR_TWO_SENTENCES: what this project is, what it holds, and its goal}}.

## Repository layout

Version control: {{VCS - e.g. git, mercurial, svn}}.

Outer repo (this one) - meta only: instructions, notes, plans, decisions.

{{INNER_REPOS: one line per inner repo, e.g.
- project/ - the material and its sources. A separate repo with its own .git,
  gitignored from the outer repo because it is standalone. Reading and editing
  inside is allowed, except whatever it gitignores itself
}}

## File map

- CLAUDE.md - how the assistant behaves (read first every session)
- PROJECT.md - project facts and this file map
- inbox.md - raw ideas, not ready to work on
- backlog.md - actionable tasks
- plans/<task-name>.md - plan for a task too large to start from a backlog entry (created when first needed)
- project/ - inner repo with the material
{{FILE_MAP: add project-specific files/folders, one per line}}

## People

<!-- Delete this section if the project involves no one but me. -->
{{OPTIONAL_PEOPLE: who's involved and their role, one per line, e.g.
- {{name}} ({{nickname}}) - {{role / relationship}}
}}

## Meta

{{OPTIONAL_META: anything worth knowing that isn't derivable from the files:
external links, related projects, conventions, status.}}
