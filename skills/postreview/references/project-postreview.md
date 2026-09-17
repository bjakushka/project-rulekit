# Project post-review checklist

Review the finished `PROJECT.md` against the accepted creation conversation
and the generated project on disk.

## Check

- The project context faithfully captures the user's stated purpose and the
  assistant's expected role
- A future assistant can understand the project without access to the
  creation conversation
- Material constraints already stated by the user are present; no unsupported
  facts or new requirements were added
- Repository paths, purposes, and version-control facts match the generated
  project
- The file map names stable orientation-level entry points and does not list
  temporary or low-level implementation details
- Project context, repository layout, and file map do not duplicate the same
  explanation unnecessarily
- Behavior rules remain in rule files rather than becoming prose in
  `PROJECT.md`

## Report only material issues

A finding is material when leaving it unresolved could make a future assistant
misunderstand the project, put work in the wrong place, or violate an explicit
constraint. Do not ask for ordinary domain content that can be added during
later project work.
