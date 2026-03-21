---
description: >-
  Run the full QA test suite against all plugins, skills, and marketplace registration.
  Use before committing or publishing to catch structural errors, missing fields,
  invalid frontmatter, and broken marketplace entries.
argument-hint: "[<plugin-name>]"
allowed-tools: [Bash, Read]
---

Run the QA validation test suite.

## Steps

1. Determine the repo root by finding the directory that contains both `plugins/` and `skills/` subdirectories. Start from the current working directory and walk up if needed.

2. Check `$ARGUMENTS`:
   - If `$ARGUMENTS` is non-empty: treat the value as a plugin name and run against that plugin only:
     ```
     python3 <repo-root>/plugins/qa/scripts/run_tests.py --plugin <name> --repo-root <repo-root>
     ```
   - If `$ARGUMENTS` is empty: run the full test suite:
     ```
     python3 <repo-root>/plugins/qa/scripts/run_tests.py --all --repo-root <repo-root>
     ```

3. Display the full output to the user exactly as produced by the script.

4. If any failures are present:
   - List each failing component and its specific failures clearly
   - Group failures by component (plugin name, skill name, command file)
   - Offer to fix each failure, describing the change before making it

5. If warnings are present but no failures:
   - List the warnings grouped by component
   - Explain what each warning means
   - Ask the user if they want to address them
