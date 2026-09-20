# project-rulekit

Templates and rule modules for LLM instruction files, and a small tool to
keep them consistent across projects.

## What it is

A project told an assistant how to behave in its `CLAUDE.md`. A second
project needed the same rules, so they were copied. By the tenth project
the copies had drifted, and no two of them said the same thing.

This is the fix: the rules live in one place as modules, a project picks
the ones it needs, and a manifest records what it took.

## Why the rules are copied

A project gets its own copy of each rule file, and `CLAUDE.md` imports it
with `@`. Three reasons for that.

**Imports load every time.** Claude reads the imported files at the start
of every session, without being asked. A skill or a script that loads the
rules has to run first, and if it does not run, the rules are not there.

**The project works on its own.** The rule files live in the project.
Clone it on another machine, or open it without this plugin, and the rules
are still there. They are in the git history too, so a change to a rule
shows up in a diff like any other change.

**Each module is a separate file.** A project takes only the modules it
needs, and it can take a different variant of the same one. Every module is
a plain copy, so the tool can compare it byte for byte and see what the
project changed and what came from the kit.

## Running it

It is a Claude Code plugin. Clone it and point Claude Code at the directory:

    git clone https://github.com/bjakushka/project-rulekit
    claude --plugin-dir ./project-rulekit

The plugin is named `rulekit`, so its skills are invoked as `rulekit:<name>`.
After editing anything in the plugin, `/reload-plugins` picks the changes up
without restarting the session.

Two skills are available:

- `rulekit:new <directory>` - create a new project. It asks what the project
  is, prepares every file in a preview, shows it, and writes nothing until
  you approve. After that it reviews the result with you
- `rulekit:adopt <directory>` - look at a project that already exists and
  report how it maps to the modules. It reads only, and changes nothing

## Status

Early, but `new` works end to end. `adopt` only reports for now; it does not
migrate a project yet. Keeping a project in sync with the kit after it is
created is still to come.

## License

MIT
