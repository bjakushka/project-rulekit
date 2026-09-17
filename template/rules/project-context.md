## Project context: stable facts and file map

- `PROJECT.md` holds stable project facts and the entry points a future
  assistant needs to orient itself
- Keep its file map aligned whenever work changes stable project paths or
  entry points
- Keep core Rulekit state and instruction files grouped as generated; do not
  enumerate individual rule or scaffold files
- Keep the repository layout to version-control facts and inner repository
  paths
- In the file map, list each inner repository once, with a short description
  of its purpose
- Add other stable primary entry points only when they materially help
  orientation
- Omit temporary and low-level implementation details
- Do not turn `PROJECT.md` into a README, backlog, or status log
- Keep behavior rules in rule modules, not in `PROJECT.md`
