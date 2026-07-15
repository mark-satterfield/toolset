---
description: Configure the CUSTOMIZABLE_DESIGN_SYSTEM_* environment variables and bootstrap the customizable-design-elements.yaml file.
allowed-tools: Read, Write, Edit, Bash, Glob, AskUserQuestion
---

# /cds:setup

Invoke the `setup` skill in this plugin. Load and execute `skills/setup/SKILL.md` and follow its discovery checklist, pipeline, halt conditions, and hard rules exactly.

## Process

1. Load `skills/setup/SKILL.md`.
2. Walk the user through the discovery checklist (existing YAML or bootstrap; global or project install; optional asset / stylesheet / mocks / shells output defaults).
3. Apply the pipeline (locate the target `settings.json`, ensure `env` exists, merge captured values, write with two-space indentation, preserve unrelated keys).
4. Report the resulting `env` block to the user as confirmation.

## Notes

- This command is the only sanctioned entry point for setup. The `setup` skill carries `disable-model-invocation: true`, so natural-language phrasing does not auto-route — explicit invocation via `/cds:setup` is required.
- The skill is idempotent: running `/cds:setup` again reads current values and presents them as defaults.
- See `README.md` for the env-var contract if the user prefers to configure by hand instead.
