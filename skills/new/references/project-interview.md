<!--
Guide for turning a new-project conversation into a temporary project brief.
-->

# Project interview

Treat the invocation prose as the first interview answer. Use everything the
user already said before asking a follow-up question.

The result must orient a future assistant that has none of this conversation.
Learn enough to explain:

- what the project is
- what information or artifacts it holds or creates
- what goal it serves
- which inner repositories exist and what each one owns

Include only stable facts that materially help orientation. Essential domain or
technical context may belong there. Plans, tasks, status, behavior rules, and
facts already expressed by the generated file map do not.

Keep repository names, paths, purposes, and other layout facts out of the
context paragraph. They belong in the separately reviewed repository summary
and the generated `Repository layout` section.

Synthesize the context as one short English paragraph, normally two to four
sentences. Interpret the user's meaning; do not copy or literally translate the
conversation. Use only facts the user stated or that follow directly from
them. In particular, do not unpack a broad category into plausible examples
the user did not mention.

When the user describes one undivided project and says nothing about repository
layout, infer one inner repository at `project/` with the purpose `Project
artifacts`. For explicitly distinct inner repositories, use a short purpose
such as `REST API` or `Mobile application`. Ask about repository layout only
when the description implies several independently versioned artifacts or
leaves a material ambiguity.

Ask only for facts still missing after inference. Phrase questions in the
user's terms, not as storage keys or command syntax. Confirm the complete
inferred configuration once, together with module choices and manifest values.
Present the synthesized English context alone as a clearly labeled block within
that summary. Keep repository paths and purposes in the ordinary configuration
summary. Explain that future assistants will rely on this context after the
creation conversation is gone, then ask an open-ended question that lets the
user accept it or provide corrections. Do not combine that confirmation with an
unresolved question. Store the approved model-written context without another
rewrite. If the user asks to review an inference, discuss only the disputed
parts. Ask at most one material follow-up question at a time.
