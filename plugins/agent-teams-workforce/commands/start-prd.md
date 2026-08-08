---
description: "Start a PRD at the top of the pipeline — Epic, TRD, Spec+Story per repo, Tasks"
argument-hint: "<prd-path-or-title> [repo,repo,...]"
allowed-tools: [Bash, Read, Glob, Skill, Workflow]
---

# Start a PRD

Take `$ARGUMENTS` from a PRD document to an emitted Epic → Story → Task hierarchy.

A PRD and its Epic are **one work item in two representations**, so this command
and `/agent-teams-workforce:work-bead <epic-id>` are two doors into the same
procedure. They differ only in which face you walked in holding. Yours is the
document; the Epic is the other face, and you resolve it below.

This is also the entry the bead router cannot provide: a PRD is a **file**, so
`bd ready` never returns one and `route-bead` never sees it.

## 1. Locate the PRD

The first argument is a path or a title. If it is a title, search the product docs:

```bash
ls ~/projects/SkillSpoke/skillspoke-docs/docs/product/
```

Prefer `obsidian-cli` (vault `skillspoke-docs`) when Obsidian is running; if it is
not, do not wait — the vault is a plain git repo of markdown, so read it off disk.

Read the PRD. Extract `title` and `body`. Stop and report if you cannot find it —
do not invent a PRD from the title.

## 2. Resolve the other face — the Epic

```bash
bd list --type epic | grep -i "<prd title>"
```

- Found → adopt it. Pass it through; it is not re-minted.
- Not found → **mint it** from the PRD. The Epic is a container: title and
  description from the PRD, no acceptance criteria, no WSJF score, no repo scope
  (one Epic may span repos).

```bash
bd create --type epic --title "<prd title>" --description "<prd summary>"
```

Minting completes the pair. It is not what authorizes the build — your invoking
this command is.

## 3. Hand off

Invoke the `elaborate-prd-epic` skill with the resolved pair, the repo span from
the second argument if given, and the BRD and SAD paths when they exist. It owns
the repo span, the `prd-to-spec` dispatch, writing the hierarchy into beads, and
the report.

Do not re-implement any of that here. If it needs to change, change it there so
both doors change together.
