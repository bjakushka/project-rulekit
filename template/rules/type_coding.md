## Project type: coding

- Treat generated code as untrusted and review it critically before relying on
  it
- Keep code straightforward enough for the owner to inspect and maintain
- Briefly explain non-obvious technical decisions
- Before changing code, read any project-specific technical orientation named
  by the project. Follow its existing architecture, conventions, and boundaries
- Add dependencies, abstractions, frameworks, build steps, or automation only
  when a demonstrated need justifies them
- Use the project's established formatter, linter, static analysis, tests,
  smoke checks, and CI as relevant guardrails
- Report what verification ran and any remaining gaps. Do not claim that a
  change works without suitable verification
- Use focused deterministic checks for mechanically verifiable contracts
- When practical, reproduce a defect before fixing it and cover it with a
  regression test that fails without the fix
- In code review, report only material findings. If the code is sound, say so
  instead of inventing issues
