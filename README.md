# project-rulekit

Templates and rule modules for LLM instruction files, and a small tool to
keep them consistent across projects.

## What it is

A project told an assistant how to behave in its `CLAUDE.md`. A second
project needed the same rules, so they were copied. By the tenth project
the copies had drifted, and no two of them said the same thing.

This is the fix: the rules live in one place as modules, a project picks
the ones it needs, and a manifest records what it took.

## Status

Early. The modules are few, the coding type is a placeholder, and assembly
is manual. Skills to automate it are planned.

## License

MIT
