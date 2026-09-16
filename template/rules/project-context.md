## Project context: stable facts and file map

- `PROJECT.md` holds stable project facts and the entry points a future
  assistant needs to orient itself
- Keep its file map aligned whenever work changes stable project paths or
  entry points
- List stable top-level paths and primary entry points, each with a short
  description of its purpose
- Describe a collection such as `rules/` as one entry instead of enumerating
  its contents, unless a file inside it is itself a primary entry point
- Omit generated, temporary, and low-level implementation details
- Do not turn `PROJECT.md` into a README, backlog, or status log
- Keep behavior rules in rule modules, not in `PROJECT.md`
