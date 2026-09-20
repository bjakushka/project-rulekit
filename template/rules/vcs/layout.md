### How the repositories are organised

- This is a multi-repo setup: the outer meta repo plus one or more inner repos
- The outer repo holds meta only: project instructions, Rulekit state, and
  workspace-level intake and coordination files
- Each inner repo is standalone, with its own `.git`
- The outer ignore only separates repository histories; it does not restrict
  reading or editing inside the inner repo
- Leave paths ignored by the inner repo itself alone unless explicitly permitted
- An inner repo never contains active LLM instructions governing work on that
  repository - no active `CLAUDE.md`, `AGENTS.md`, `rules/`, or `.claude/`.
  Keeping them in the outer repo preserves one workspace-level source of truth
- LLM instructions produced by the project are artifacts rather than active
  workspace instructions and may live in an inner repo
- Never mix changes from two repos in one commit
- Before any repo operation, know which repo you are in
