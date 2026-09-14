# project-rulekit

Templates and rule modules for LLM instruction files, and a small tool to
keep them consistent across projects.

## What it is

A project told an assistant how to behave in its `CLAUDE.md`. A second
project needed the same rules, so they were copied. By the tenth project
the copies had drifted, and no two of them said the same thing.

This is the fix: the rules live in one place as modules, a project picks
the ones it needs, and a manifest records what it took.

## Running it

It is a Claude Code plugin. Clone it and point Claude Code at the directory:

    git clone https://github.com/bjakushka/project-rulekit
    claude --plugin-dir ./project-rulekit

The plugin is named `rulekit`, so its skills are invoked as `rulekit:<name>`.
After editing anything in the plugin, `/reload-plugins` picks the changes up
without restarting the session.

There are no skills yet - see Status.

## Status

Early. The modules are few, the coding type is a placeholder, and assembly
is manual. Skills to automate it are planned.

## License

MIT
