## Project context: stable facts and repository orientation

- `PROJECT.md` holds stable workspace facts and the entry points a future
  assistant needs to orient itself
- Keep the repository layout to version-control facts and inner repository
  paths
- In the file map, list each inner repository once with a concise purpose;
  keep core Rulekit state and instruction files grouped rather than enumerating
  individual rules or scaffolds
- After the file map, give every listed inner repository its own
  `## Repository` heading with the path in backticks, as shown below. Start
  with its purpose, then add stable repository-specific context when a one-line
  description is not enough
- Add an `Orientation map:` under that repository heading when named entry
  points materially help the assistant choose where to read next. Keep it a
  short router of stable files or directories, not a generated file tree
- Start from a relevant named entry point before scanning an inner repository
  broadly. A root `README.md` is a useful human-facing overview when it exists,
  but is recommended rather than required
- Keep detailed navigation with the content it describes, such as domain
  indexes in a knowledge repository or architecture documents in a coding
  repository
- Add other stable workspace entry points only when they materially help
  orientation; omit temporary and low-level implementation details
- Do not require `CODEBASE.md`, `ORIENTATION.md`, or another universal map file
- Do not turn `PROJECT.md` into a README, backlog, or status log
- Reusable behavior belongs in modules, while stable project-specific
  contracts and instructions may remain in `PROJECT.md` after the standard
  context and repository sections

Use this shape for each inner repository:

```markdown
## Repository `<path>/`

<Stable purpose and repository-specific context.>

Orientation map:

- `<entry-point>.md`
  <Description of what it contains or when to read it>

- `<directory-path>/`
  <Description of what it contains or when to read it>

- ...
```

Omit `Orientation map:` when the repository has no useful stable entry points
to name.
