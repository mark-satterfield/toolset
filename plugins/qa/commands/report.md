---
description: >-
  Generate a Markdown test execution report from the last /qa:test run.
  Shows pass/fail summary, failure details, and warnings table.
argument-hint: "[--out <filename>]"
allowed-tools: [Bash, Read, Write]
---

Generate a Markdown QA test execution report.

## Steps

1. Determine the repo root by finding the directory that contains both `plugins/` and `skills/` subdirectories. Start from the current working directory and walk up if needed.

2. Parse `$ARGUMENTS` for `--out <filename>`. If `--out` is present, extract the filename value.

3. Run the report generator:
   - With output file: `python3 <repo-root>/plugins/qa/scripts/generate_report.py --out <filename>`
   - Without output file: `python3 <repo-root>/plugins/qa/scripts/generate_report.py`

4. If `--out` was given:
   - Confirm the file was written
   - Display the absolute path to the written file
   - Offer to show the report content if the user wants to review it inline

5. If no `--out` was given:
   - Display the full report output to the user

6. If the generator errors (e.g., no last run file found):
   - Explain that `/qa:test` must be run first to generate results
   - Offer to run the full test suite immediately
