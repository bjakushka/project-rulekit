# Reconciliation guidance

Use this reference only after the base mapping has been confirmed and a clean
Rulekit preview exists. Reconciliation builds the approved future project in
`.kit-preview/files/`; it never changes the source project.

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
- add portable behavior to the copied Rulekit module in the preview
- choose which side of a real conflict should govern the adopted project

The owner decides unresolved and conflicting cases because project knowledge
can make a textually similar rule mean something different. Do not infer that
approval of the base mapping also approves later replacements, moves, or
deletions.

Apply accepted decisions to the preview only. Keep unresolved items open, and
record moves or deletions separately for later approval.

When the owner decides that behavior belongs in Rulekit generally, edit the
copied module under `.kit-preview/files/rules/`. Do not edit the active Rulekit
catalogue during adoption. The project's `.kit.json` keeps the source Rulekit
commit, so a future sync can show this local module change and offer it back to
Rulekit.

## Collect the checklist

Initialize reconciliation through the state script. The model must not read or
edit `reconciliation.json` directly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/adopt/scripts/reconcile.py" --target "<resolved-target>" state init
```

While the state is `collecting`, start `rulekit:adopt-reconciliation-reader`.
Give it only the resolved target, `.kit-preview/files/`, verified diagnostic
findings, the exact `${CLAUDE_PLUGIN_ROOT}/skills/adopt/scripts/reconcile.py`
path, and a request to follow its own instructions. It registers every finding
through `item add` without choosing outcomes or returning evidence into the
main context.

Wait for the reader. A short progress update may say collection is still
running, but do not ask a blocking question before the checklist is ready. An
early question makes the owner decide from incomplete evidence and leaves the
answer unrelated to a registered item.

The initial collection does not seal the list. If the main skill discovers
another material difference while discussing an item, verify it against the
source and preview, then append it through the same one-line command:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/adopt/scripts/reconcile.py" --target "<resolved-target>" item add --id "<id>" --summary "<summary>" --source "<source-reference>" --preview "<preview-reference>"
```

Repeat `--source` and `--preview` as needed. A finding with no corresponding
preview behavior may omit `--preview`.

After the reader finishes, enter the decision loop:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/adopt/scripts/reconcile.py" --target "<resolved-target>" state ready
```

## Resolve one item at a time

Request the first open item:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/adopt/scripts/reconcile.py" --target "<resolved-target>" item next
```

Read its cited evidence again. In chat, show only the small block needed for an
informed decision:

- what the existing project does
- what the clean preview does
- viable choices and their consequences
- the recommended choice
- the exact minimal preview diff for that choice

Then call `AskUserQuestion`. Do not decide from textual similarity or silently
accept the recommendation. The owner's project knowledge governs the outcome.

One item represents one independently decidable outcome, not necessarily one
file. Never combine unrelated choices merely because they occur in the same
file. When a decision would copy or change a group of files, list the exact
paths and obtain explicit approval for that group first. Approval of the final
layout is not approval of an inferred file list.

After approval, apply that exact decision immediately and only under
`.kit-preview/files/`. Read the changed preview paths to verify the result, then
record the completed item:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/adopt/scripts/reconcile.py" --target "<resolved-target>" item done "<id>" --note "<short-reason>" --changed-preview "<preview-relative-path>" --source-action "<later-source-action>"
```

Repeat `--changed-preview` and `--source-action` as needed. Either list may be
empty: the preview may already match the accepted policy, and some decisions
need no later source change. Keep the note short and explain why the owner chose
the outcome, not the whole conversation.

When the accepted outcome depends on an exact copy, entry count, or unchanged
text, verify it with a deterministic comparison before completing the item.

Continue with `item next`. When no open items remain, check whether the work
revealed another material difference and append it if needed.

Before completing, print the accepted decisions without reading state directly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/adopt/scripts/reconcile.py" --target "<resolved-target>" item list --status done
```

Start `rulekit:adopt-reconciliation-reviewer`. Give it the resolved target,
finished preview, exact reconciliation script path, and completed-item report.
Wait without asking side questions. If it registers omissions, return to
`item next`; after resolving them, run the reviewer again. Only a pass with no
unexplained material omissions or preview rule violations may proceed.

After a clean reviewer pass, ask whether the owner wants to review the finished
preview. Do not require a particular review tool; use what is available in the
current environment. If the owner declines, continue. If the review finds a
material difference or rule violation, add it as a reconciliation item, resolve
it, and run the reviewer again.

Only after the owner declines or finishes that review with no unresolved
remarks, complete reconciliation:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/adopt/scripts/reconcile.py" --target "<resolved-target>" state complete
```

`complete` means that reconciliation is complete, not that the source project
has been changed or the adoption transaction has been approved.

Reconciliation records where content should end up, not how Git history will
move. Do not record `git init`, copy or remove `.git`, or choose a history
strategy unless the owner explicitly decides it during the future apply.

## Resume safely

On a repeated adopt invocation, `state init` validates the existing state and
reports its phase without resetting it:

- `collecting`: rerun the collector; an identical `item add` is a no-op, then
  run `state ready`
- `reconciling`: continue with `item next`
- `complete`: report the finished preview and stop

If an interruption happens after the owner approves a choice but before the
preview edit and `item done`, the item stays open and may be shown again. This
is safer than recording a decision that was not applied.
