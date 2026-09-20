# Reconciliation guidance

Use this reference only after the diagnostic mapping has been confirmed and
the interactive adoption phase has created a clean Rulekit preview.

## Confirm the base before reconciling

Confirm the project brief, type, modules, values, and repository purposes with
the owner before treating them as inputs to the renderer. Existing names and
Git roots are evidence, not approval of the proposed Rulekit layout.

For a project with one Git repository, propose one inner repository, normally
`project/`, with an inferred purpose. Ask whether that representation is
correct before accepting it. This proposes a Rulekit layout; it does not
authorize moving the existing repository or any files.

For multiple Git roots, present each nested root and its inferred purpose.
Exclude a root only when the owner confirms that it does not belong to the
project.

## Reconcile behavior, not lines

Work through one material semantic difference at a time. Group wrapping,
wording, and duplicates already covered by the core or a selected module.

For each material difference, show:

- the source evidence
- the corresponding Rulekit behavior, when one exists
- the viable choices and their consequences
- the exact preview diff for the recommended choice

The usual choices are:

- remove a covered duplicate from the preview
- preserve project-specific behavior outside managed Rulekit files
- propose portable behavior for Rulekit intake
- choose which side of a real conflict should govern the adopted project

The owner decides unresolved and conflicting cases because project knowledge
can make a textually similar rule mean something different. Do not infer that
approval of the base mapping also approves later replacements, moves, or
deletions.

Apply accepted decisions to the preview only. Keep unresolved items open, and
record moves or deletions separately for later approval.
