---
description: >-
  Validate a plugin, skill, or command for structural correctness and quality.
  Use when you want to check if a component you've built meets all requirements
  before committing. Runs static checks: manifests, frontmatter, content rules.
argument-hint: "[--plugin <name> | --skill <name> | --command <path>]"
allowed-tools: [Bash, Read]
---

Validate a Claude Code component based on the arguments provided.

## Steps

1. Parse `$ARGUMENTS` to determine what to validate:
   - If arguments contain `--plugin <name>`: validate the plugin at `plugins/<name>/`
   - If arguments contain `--skill <name>`: validate the skill at `skills/<name>/`
   - If arguments contain `--command <path>`: validate the command file at the given path
   - If no arguments are given: ask the user what they want to validate (plugin, skill, or command) and the name or path

2. Determine the repo root by finding the directory that contains both `plugins/` and `skills/` subdirectories. Start from the current working directory and walk up if needed.

3. Run the appropriate validator script:
   - Plugin: `python3 <repo-root>/plugins/qa/scripts/validate_plugin.py <plugin-dir>`
   - Skill: `python3 <repo-root>/plugins/qa/scripts/validate_skill.py <skill-dir>`
   - Command: `python3 <repo-root>/plugins/qa/scripts/validate_command.py <command-file>`

4. Display the full output to the user exactly as produced by the script.

5. If the validator exits with code 1 (failures present):
   - List each failure clearly
   - Offer to fix the failures if they are straightforward (missing fields, incorrect metadata, prohibited content)
   - For each offered fix, describe what change will be made before making it

6. If the validator exits with code 2 (warnings only):
   - List the warnings
   - Explain what each warning means
   - Ask the user if they want to address the warnings
