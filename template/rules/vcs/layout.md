### How the repositories are organised

- This is a multi-repo setup: the outer meta repo plus one or more inner repos
- The outer repo holds meta only: instructions, notes, plans, decisions
- Each inner repo is standalone, with its own `.git`, gitignored from the outer 
  one. Reading and editing inside is allowed, except what it gitignores itself
- **An inner repo NEVER contains LLM instruction files** - no `CLAUDE.md`, no 
  `AGENTS.md`, no `rules/`, no `.claude/`. That is the whole point of the split: 
  the inner repo is the project itself, the outer one is the harness around it. 
  Instructions about the inner repo live in the outer repo
- Never mix changes from two repos in one commit
- Before any repo operation, know which repo you are in
