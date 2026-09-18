---
name: postreview
description: Review a newly created Rulekit project after rulekit:new applies it. Use only when the new skill delegates the resolved target for final context review.
user-invocable: false
argument-hint: [project-directory]
allowed-tools:
  - Agent
  - AskUserQuestion
  - Edit
  - Glob
  - Grep
  - Read
---

# Post-creation project review

The resolved project target passed by `rulekit:new` is:

`$ARGUMENTS`

Treat the complete argument as the target path. Stop with a clear explanation
if it is empty, does not exist, or does not contain `PROJECT.md`. Do not create
or regenerate project files.

Read `${CLAUDE_SKILL_DIR}/references/project-postreview.md`.

Do not call the `advisor` tool when the creation context, generated project,
and review checklists already determine the review. Use it only when a
genuinely complex decision remains unresolved.

## Start an independent reading

Start the read-only `rulekit:fresh-project-reader` agent before doing the main
review so it can work in parallel. Give it only:

- the resolved target path
- a request to review that target according to its own instructions

Do not give it the invocation prose, interview, temporary brief, current
conversation history, expected findings, or your own conclusions. Ask it to
read the generated project as a future assistant with no prior context and
return the requested report without editing anything.

If the Agent tool is unavailable or the agent fails, report the exact failure
and use `AskUserQuestion` to ask whether to continue with a self-review or
stop. Do not silently replace the independent pass. If the user chooses to
continue, read `${CLAUDE_PLUGIN_ROOT}/agents/fresh-project-reader.md`, apply
the same checklist yourself after the main review, and state that the
independent pass was not available.

## Review with creation context

While the fresh reader works, inspect the target:

1. Read `CLAUDE.md`, `PROJECT.md`, and `.kit.json`
2. Follow the instruction imports from `CLAUDE.md` and read their entry
   points
3. Verify a stable path named by `PROJECT.md` only when resolving a material
   question about that path. Do not perform a general filesystem scan
4. Apply `references/project-postreview.md` using the accepted creation
   context still present in this conversation

Use `Read` and `Grep` for this inspection. Use `Glob` only when it is available
and a specific unresolved question requires it. Do not use Bash to list or read
files. Finish reading the imported instructions before forming any finding.
Do not state a candidate finding, even in a progress update, until both reviews
are complete and synthesis has retained it.

Review the finished `PROJECT.md` as an instruction artifact for a future LLM
that will not have the creation conversation. Do not reopen
`.kit-preview/answers.json`, reconstruct the temporary brief, rerun
`rulekit:new`, or regenerate the project. Do not inspect the Rulekit plugin
source, manifest, or templates to adjudicate a finding: this review is based on
the generated target and the accepted creation context.

## Synthesize findings

After the main review, wait for the fresh-reader completion notification. Emit
at most one short status line, then end the turn. Do not poll, continue
inspection, or explain the review method while waiting.

When the report arrives, treat it as evidence, not authority. Combine it with
the main review and silently discard:

- minor wording or style preferences
- duplicated findings
- speculative additions
- findings that are false only because the fresh reader lacked creation
  context
- details that belong in project content, a README, inbox, or backlog rather
  than stable project orientation

Do not show provisional findings, the discarded list, or the investigation
used to reject them. Present only material omissions, contradictions, or
ambiguities that could steer future work incorrectly. If none remain, say that
the post-creation review passed and finish.

## Resolve material findings

First distinguish a missing stable project fact from a defect in an imported
behavior rule. If the finding requires changing a rule, report it as an
upstream Rulekit issue and do not mask it with instructions in `PROJECT.md`.

Ask only the questions needed to resolve the material findings. Use
`AskUserQuestion` and ask one question per interaction. Do not turn the
review into a second general interview.

Treat an unambiguous user answer as an accepted stable project fact. Unless it
conflicts with another explicit instruction, do not reopen the question or
argue against the resulting correction.

After the answers are clear, draft the smallest exact English change to the
finished `PROJECT.md`. Show that exact change through an available review
method and ask for approval. If no diff review method is available, show the
exact replacement text in the approval question.

Before presenting the change, re-read the complete proposed `PROJECT.md` as it
would appear after the edit. Confirm that it has no duplicate sections or path
entries, still follows the imported project-context rules, and changes only the
facts needed by the accepted answer. Rebuild the proposal if this check fails.

Edit only `PROJECT.md`, only after the user approves the exact proposed
change. Do not regenerate it or edit rules, scaffolds, `.kit.json`, or project
content. `PROJECT.md` is project-owned after apply: a justified postreview
edit is expected to differ from the scaffold and must not be rejected merely
because regeneration would overwrite it. Re-read the finished file and report
the material correction made.
