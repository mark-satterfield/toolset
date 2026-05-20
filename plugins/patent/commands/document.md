---
description: Generate a finished document from an idea directory — invention disclosure, USPTO PPA draft, non-provisional skeleton, IDS prior-art summary, claim chart, or defensive publication. Writes markdown source and renders PDF when a renderer is available.
argument-hint: "[slug] [document-type]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# /patent:document

Invoke the `patent-document-generation` skill on a fully-scoped idea.

## Process

1. Resolve `$ARGUMENTS`. Two arguments expected:
   - `slug` — required, identifies which idea directory
   - `document-type` — optional. One of: `invention-disclosure`, `ppa`, `non-provisional`, `ids`, `claim-chart`, `defensive-publication`. If absent, the skill prompts the user with the six options.

2. Verify the directory has the files required for the chosen document type:

   | Document type | Required files |
   |---|---|
   | invention-disclosure | `idea.md` at `shaped`+ |
   | ppa | `idea.md` at `claim-ready` |
   | non-provisional | `idea.md` + `claims.md` |
   | ids | `prior-art.md` |
   | claim-chart | `claims.md` + `prior-art.md` |
   | defensive-publication | `idea.md` + `decision.md` (recording the choice) |

3. If a required file is missing, the skill tells the user which earlier skill to run, and stops.

4. Load and execute `skills/patent-document-generation/SKILL.md`.

5. On completion, the skill outputs the file path. PDF rendering is attempted via pandoc, md-to-pdf, or weasyprint — if none is available, only the markdown is generated and the user is told.

## Notes

- Every fact in every generated document traces to a file in the idea directory. The skill does not invent content.
- The plugin does not file with the USPTO. Filing is the inventor's separate step.
