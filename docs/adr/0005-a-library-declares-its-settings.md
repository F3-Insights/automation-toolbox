# 0005. A Library declares its settings file in library.yaml

Status: accepted, 2026-10-13. The owner asked that a runtime keep the toolbox's settings with its own configuration ("config like this needs to live in .sentinel"); the file names and shape were proposed by the session and accepted.

## Context

The scripts read the owner's settings from `~/.config/f3i-toolbox/settings.toml`, or the file `F3I_TOOLBOX_SETTINGS` names ([docs/settings.md](../settings.md)). A runtime that runs the toolbox's agents and scripts unattended, such as Sentinel, keeps everything of its own in one home folder and wants the settings its Runs depend on kept there too, backed up and moved with it, and checked before a Run starts. To do that without knowing the toolbox, the runtime needs three facts the toolbox alone knows: which environment variable names the file, where the scripts look without it, and which keys there are. Until now those facts were only prose in docs/settings.md, and the example in it showed a dozen of the keys.

## Decision

1. **A Library may carry `library.yaml` at its root.** It is plain data for any runtime, named for no runtime. The toolbox's:

   ```yaml
   name: f3i-toolbox
   settings:
     env: F3I_TOOLBOX_SETTINGS
     default: ~/.config/f3i-toolbox/settings.toml
     example: settings.example.toml
   ```

   `name` is the Library's name, independent of the folder it is cloned into. `settings.env` is the variable the scripts read the file's path from; `settings.default` is where they look without it; `settings.example` is a file beside `library.yaml`. A runtime that keeps the file elsewhere sets the variable to it for everything it starts, and sets nothing when it has no file, so the default applies.
2. **`settings.example.toml` holds every key docs/settings.md documents**, in the same tables, each with one comment line directly above it (what it is, required or optional, and its default) and a commented-out placeholder value (`# key = "~/path/to/..."`). Table headers are not commented out, so the file is valid TOML as it ships (every table empty) and with any key switched on. A placeholder that starts with `~/` marks a key whose value is a path. No placeholder names a real person, client or folder.
3. **docs/settings.md stays the place a key is documented.** A key added to, renamed in or removed from it changes the example in the same commit; `scripts/tests/test_settings_example.py` fails when the two differ, when a key has no comment line, or when the example stops reading as TOML.

## Consequences

- The toolbox's scripts do not change: they read `F3I_TOOLBOX_SETTINGS` or the default as before. A hand-started Claude Code session reads the default; a runtime that moves the file into its home links the default to it, so both read one file.
- A newcomer can start the settings file by copying the example, and a runtime can list every key with its help and edit the file without a table of the toolbox's keys of its own.
- The one-line comments are short forms of docs/settings.md's descriptions; when they differ, docs/settings.md is right and the example is fixed.
