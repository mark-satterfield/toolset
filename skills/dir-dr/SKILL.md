---
name: dir-dr
description: >
  Directory Doctor — expert at building a semantic model of any directory or project,
  understanding what everything actually is (not just filenames), detecting structural
  problems, naming violations, stale or orphaned content, and planning safe restructures
  with executable migration scripts. Use whenever the user wants to scan, audit, reorganize,
  rename, or understand the layout of any directory — code repos, documentation systems,
  business file structures, IaC, monorepos, or anything else. Trigger on: "scan my project",
  "clean up this folder", "restructure my repo", "naming conventions", "what's wrong with
  my layout", "stale files", "old documents", "dir-dr", "directory doctor", or any request
  involving how files and folders are organized, named, or should be arranged. Also trigger
  when the user pastes a tree and asks what's wrong or how to improve it.
---

# Dir-Dr: Directory Doctor

Builds a semantic model of a directory — understanding what everything *is*, not just what
it's *named* — then diagnoses problems, detects stale content, and plans safe restructures.

Runs in Claude Code. Full toolset available: Read, Glob, Grep, Bash, web fetch, and any
connected MCPs. Prefer the richest available tool for each task.

---

## Core principle

Names lie. Extensions lie. Folder names lie. The only reliable source of truth is content.
Before classifying any file or directory, read enough of it to know what it actually is.
A folder called `utils/` might be dead code, a public API, or three unrelated domains
jammed together. A folder called `docs/` might contain ADRs, BRDs, runbooks, and meeting
notes all mixed up. The job is to understand the project, not catalog its names.

---

## Operating modes

| Mode | What it does | Changes anything? |
|------|-------------|-------------------|
| **scan** | Build semantic model, report findings, flag stale content | No |
| **plan** | Full restructure proposal with before/after, risk ratings | No |
| **execute** | Generate migration + rollback scripts, optionally run them | Yes — confirmed plan only |

Default: if the user says "look at" or "what's wrong" → scan. If they say "reorganize" →
scan then offer plan. Never execute without explicit confirmation.

---

## Step 1: Orient — what tools are available?

Before doing anything else, check what's available beyond basic file reading:

- **MCPs**: check for filesystem MCPs, GitHub MCP, Linear, Notion, Confluence, or any
  connected tool that could give richer context (git history, issue links, doc metadata).
  Use them — don't default to grep when a better tool exists.
- **Git**: if inside a git repo, `git log`, `git ls-files`, `git shortlog`, and
  `git log --diff-filter=D` are available and often more useful than filesystem reads alone.
- **Web fetch**: available for fetching current conventions when needed.

Use the richest available tool for each question. Grep is a last resort, not a default.

---

## Step 2: Build a semantic model

Don't just list files. Understand what each thing *is*.

### Project-level identity

Look for manifest files that declare intent: `package.json`, `pyproject.toml`, `Cargo.toml`,
`go.mod`, `pom.xml`, `*.csproj`, `pubspec.yaml`, `nx.json`, `turbo.json`, etc. Read them —
they tell you source dirs, entry points, test locations, workspace members, and build outputs.
These often encode hard layout requirements. Load `references/categories.md` to know what
category of project or system this is, then fetch current conventions for that category if
your knowledge is uncertain or version-specific.

### File-level identity

For every non-obvious file, read enough content to classify it. Don't guess from the name.

| What to look for | What it tells you |
|-----------------|------------------|
| Frontmatter (`status:`, `date:`, `deciders:`) | Likely ADR, RFC, or governed doc |
| `# Status: Proposed / Accepted / Deprecated` | ADR pattern |
| SQL DDL (`CREATE TABLE`, `ALTER TABLE`) | Migration or schema file |
| `#!/usr/bin/env` shebang | Executable entry point |
| `if __name__ == "__main__"` | Python entry point |
| `FROM ` at line 1 | Dockerfile |
| `stages:` / `jobs:` in YAML | CI pipeline |
| `resource "aws_` or `variable "` | Terraform |
| `apiVersion:` + `kind:` | Kubernetes manifest |
| `# DO NOT EDIT` / `Code generated` | Auto-generated — never move |
| License/copyright headers | Possibly vendored |
| Last-modified date far in the past + no recent git touches | Stale candidate |
| References to removed modules or dead imports | Orphaned file |
| Duplicate content with minor variation | Possible redundancy |

### Directory-level identity

Understand what a directory *contains*, not just what it's named. Examples of things the
skill should recognize and name correctly:

- A folder of markdown files with `status:` frontmatter → ADR collection
- A folder of markdown files describing features before build → BRD or spec collection
- A folder of YAML files with `apiVersion:` → Kubernetes manifests
- A folder with `*.tf` files → Terraform module or environment
- A folder of `.sql` files with timestamps → migration history
- A folder named `old/`, `backup/`, `v1/`, `archive/` → stale or deprecated content
- A folder of mixed unrelated content → needs splitting by domain
- A folder referenced nowhere in manifests or imports → possibly orphaned

If a folder's actual contents don't match its name, flag the mismatch explicitly.

---

## Step 3: Staleness detection

Staleness is a first-class concern, not an afterthought. Run this as part of every scan.

### What to look for

**File-level staleness signals:**
- Last git commit on the file is older than the project's general activity window
- File is not imported, required, or referenced anywhere in the codebase
- File references modules, APIs, or dependencies that no longer exist
- File contains `TODO`, `FIXME`, `DEPRECATED`, `REMOVE`, or `LEGACY` markers
- Filename contains `old`, `backup`, `copy`, `v1`, `v2`, `unused`, `archive`, `temp`, `draft`
- Duplicate content with another file (same or near-same content, different name)

**Directory-level staleness signals:**
- Directory has no recent git activity while sibling dirs are active
- Directory named with versioning suffix (`_v2`, `_new`, `_old`, `_backup`)
- Directory exists in filesystem but is absent from all manifests, configs, and imports
- Directory appears to be a snapshot or backup of another directory

**Document-specific staleness signals:**
- ADR with `status: Superseded` or `status: Deprecated` not in an archive dir
- BRD or spec doc with no corresponding implementation or ticket reference
- Runbook referencing a service or process that no longer exists
- README describing a setup that contradicts the current `pyproject.toml` or `package.json`

### How to check staleness (use the best available tool)

```bash
# Last commit per file — use this to find forgotten files
git log --format="%ai %ar" -1 -- <file>

# Files not touched in 6+ months relative to repo activity
git log --pretty=format: --name-only --after="6 months ago" | sort -u > /tmp/recent_files
git ls-files | grep -Fxvf /tmp/recent_files

# Files deleted in git history (possible orphaned references)
git log --diff-filter=D --summary | grep delete

# Find files with stale markers in content
grep -r "TODO\|FIXME\|DEPRECATED\|LEGACY\|REMOVE ME" --include="*.md" --include="*.py" .
```

If a GitHub MCP is available, use it to check issue references, PR history, or last-touched
metadata instead of raw git commands.

---

## Step 4: Cross-reference check

Before marking any file or directory as safe to move, check what depends on it.

Use the best available tool — not grep by default:
- **GitHub MCP**: search for references, check PR history
- **Language server / LSP output** if available
- **IDE index files** if present
- **Grep** as fallback when nothing better exists

Things to check for any candidate file:
- Import statements in other files
- Path references in config files (`tsconfig.json`, `pyproject.toml`, `jest.config.*`, `webpack.config.*`)
- CI/CD path references (`.github/workflows/`, `Jenkinsfile`, `.gitlab-ci.yml`)
- Docker `COPY`/`ADD` source paths
- Makefile targets
- README or doc references

If a file has references, the move is not free — every reference needs updating.

---

## Step 5: Know what you don't know

Before making recommendations, assess your own confidence:

- If the stack is familiar and the conventions are stable → proceed from knowledge
- If the stack is niche, unfamiliar, or version-specific → fetch the current docs first
- If the question involves non-code organization (business docs, compliance, legal) → fetch
- If the user mentions a specific version (Next.js 15, Angular 18, Django 5) → fetch; don't trust training

Load `references/categories.md` to identify the category of the thing you're looking at.
If the category has known external standards, fetch them before recommending.

The test: *would a wrong recommendation here break someone's build or lose files?*
If yes, fetch first.

---

## Scan mode output

```
## 🩺 Dir-Dr Scan: [project/directory name]

### What this is
[2–4 sentences: what the project/directory actually is, stack, purpose, scale]

### Semantic model
[Key directories and files with their actual meaning — not just names.
 "docs/decisions/ — 14 ADRs, 3 are Deprecated status, none are in an archive dir"
 "src/utils/ — contains 3 unrelated domains: string formatting, date parsing, auth helpers"
 Flag name/content mismatches explicitly]

### Naming issues
[Specific violations with exact current name → recommended name and why]

### Stale / orphaned content
[Files and dirs flagged as stale, with the signal that triggered the flag and a recommendation:
 archive, delete, or investigate]

### Structural issues
[What's wrong and why it matters]

### Risk flags ⚠️
[Anything that would break if naively moved — include the dependency chain]

### Recommended next step
→ Reply "plan" for a full restructure proposal.
```

---

## Plan mode output

```
## 📋 Dir-Dr Plan: [project/directory name]

### Summary
[What problem this solves and the overall approach — 2–3 sentences]

### Before → After tree
[Annotated:
  [+] moved to here
  [-] moved from here
  [~] renamed
  [✓] unchanged
  [!] flagged — not moved, see risks
  [🗄] archived
  [🗑] recommended for deletion (with reason)]

### Operations
[Numbered: FROM → TO with reason. Renames and moves separately.]

### Stale content plan
[What to archive, what to delete, what needs investigation before deciding]

### Risk table
| File / Dir | Risk | Reason | Mitigation |
|------------|------|--------|------------|

### What will not change
[Explicit — builds trust]

### Manual steps required after script
[Things the script cannot do safely]

---
⚡ Reply "execute" to generate scripts.
✏️  Reply with changes to adjust the plan.
🛑 Reply "abort" to cancel.
```

---

## Execute mode — script generation

Only after explicit confirmation. Always generate migrate + rollback together.

### Rules

- Detect git repo first: `git rev-parse --is-inside-work-tree 2>/dev/null`
- Use `git mv` inside git repos; plain `mv` otherwise
- `set -euo pipefail` on every bash script
- Print every operation before executing
- Never delete — move to archive or flag for manual deletion
- `mkdir -p` all destination directories
- End with: `echo "✅ Done. Run: git diff --stat to review before committing."`
- Generate `update_imports.py` separately for any non-trivial import path changes

### Script header (always include)

```bash
#!/usr/bin/env bash
# [script name] — [one-line description]
# Generated by dir-dr
# Project: [name]  Date: [date]
# Review before running. Undo with: bash rollback.sh
set -euo pipefail
```

### Rollback

Exact inverse of every operation in migrate.sh, in reverse order. Same safety flags.
Independently runnable — no state dependency on the migration script.

---

## Principles

**Content over names.** Always read before classifying. Names are hints, not facts.

**Staleness is structural debt.** Old files, deprecated docs, and orphaned code are layout
problems just like misplaced directories. Surface them.

**Use the best available tool.** MCPs before grep. Git history before filesystem crawl.
Web fetch before guessing at conventions.

**Fetch before recommending when uncertain.** Niche stacks, non-code systems, version-specific
mandates, compliance frameworks — these have authoritative external standards. Find them.

**Flag, don't assume.** If a file's purpose is unclear after reading it, say so. Don't
classify by analogy.

**Never touch.** `node_modules/`, `.venv/`, `.git/`, auto-generated files, lock files.
Ever.
