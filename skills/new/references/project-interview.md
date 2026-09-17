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

Synthesize the context as concise English prose. Interpret the user's meaning;
do not copy or literally translate the conversation, and do not invent facts.

When the user describes one undivided project and says nothing about repository
layout, infer one inner repository at `project/`. Ask about repository layout
only when the description implies several independently versioned artifacts or
leaves a material ambiguity.

Ask only for facts still missing after inference. Phrase questions in the
user's terms, not as storage keys or command syntax. Confirm the complete
inferred configuration once, together with module choices and manifest values.
If the user asks to review an inference, discuss only the disputed or unresolved
parts. Ask at most one material follow-up question at a time.
