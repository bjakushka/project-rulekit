# project-rulekit

An opinionated Claude Code plugin for creating project instruction files,
adopting existing projects, and keeping shared rule modules in sync.

## What it is

A project told an assistant how to behave in its `CLAUDE.md`. A second project
needed the same rules, so they were copied. By the tenth project, the copies
had drifted and no two said the same thing.

Rulekit keeps shared rules in one catalogue. Each project records its selected
modules, Rulekit version, and values in `.kit.json`. Modules cover areas such
as project context, version control, secrets, inboxes, file-based backlogs, and
project notes. See [`manifest.json`](manifest.json) for the complete current
catalogue.

**Rulekit is opinionated and built for the author's own workflow, not as a
universal project system.**

## Why the rules are copied

A project gets its own rule files, and `CLAUDE.md` imports them with `@`. There
are three reasons for this.

**Imports load every time.** Claude reads the imported files at the start of
every session. A skill or script that loads the rules has to run first. If it
does not run, the rules are not there.

**The project works on its own.** Its rule files remain available on another
machine and without Rulekit. They are also in Git history, so a rule change
appears in a diff like any other change.

**Changes are easy to compare.** Selected module files are plain copies, so
Rulekit can compare them byte for byte and show what changed in the project or
in the kit. Core files such as `CLAUDE.md` are rendered with project values and
generated module imports.

## Running it

Clone the plugin and point Claude Code at its directory:

    git clone https://github.com/bjakushka/project-rulekit
    claude --plugin-dir ./project-rulekit

The plugin is named `rulekit`, so its skills are invoked as `rulekit:<name>`.
After editing the plugin, run `/reload-plugins` to load the changes without
restarting the session.

Three user-facing skills are available:

- `rulekit:new <directory>` creates a new project through a reviewed preview
- `rulekit:adopt <directory>` builds and reconciles a preview for an existing
  project, but does not apply it
- `rulekit:sync <directory>` compares selected rule modules with the kit and
  helps review changes in either direction

## Status

Rulekit is in active development. `new` works end to end. `adopt` prepares and
reconciles a migration preview; applying it is currently a manual step. `sync`
supports interactive review of existing module copies.

## License

MIT
