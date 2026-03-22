---
description: Discover spec candidates across the SkillSpoke fleet by merging code evidence with functional plans. Appends to docs/specs/candidates.md. Run scoped by domain to avoid context exhaustion.
argument-hint: "[domain-scope]"
allowed-tools: Read, Glob, Grep, Bash, Task, AskUserQuestion
---

# Discover Spec Candidates (SkillSpoke Fleet)

Reverse-engineer the SkillSpoke fleet into a list of spec candidates by merging two sources of equal authority:
- **Code** (GraphRAG + GitNexus): what is actually built
- **Functional plans** (`docs/plans/functional/`): what has been designed

Neither source dominates. Things in code but not in plans are candidates. Things in plans but not in code are candidates. Things in both are candidates. The goal is an exhaustive inventory of everything that warrants a formal spec.

**Run scoped** to avoid context exhaustion: `/pmo:discover-more auth`, `/pmo:discover-more opportunities`, etc.
**Output persists** to `docs/specs/candidates.md` — append-safe across multiple scoped runs.

Specs are capability-scoped, not service-scoped. One spec may span multiple services, repos, and UI surfaces. There are two spec types:

- **Functional**: organized around what a user does or experiences (e.g., "job application tracking", "candidate profile creation")
- **Technical**: organized around how the platform behaves internally, cross-cutting (e.g., "event envelope standard", "M2M authentication contract", "idempotency policy")

---

## Process

### Step 1 — Parse scope

Extract the domain keyword from `$ARGUMENTS` (e.g., `auth`, `opportunities`, `events`, `chat`, `profile`).

- If provided: use it as a semantic filter appended to every search query in Step 4. Only surface candidates clearly related to this domain.
- If empty: run without filter. Expect high token usage. Consider scoping.

### Step 2 — Confirm indexes

Run both in parallel:
- `mcp__mcp-graphrag-server__list_indexed_repos` — note repo count
- `mcp__gitnexus__list_repos` — note repo count

If GraphRAG is unavailable: proceed with GitNexus only, note in output.
If GitNexus is unavailable: proceed with GraphRAG only, note in output.
If both unavailable: stop. Report: "Both indexes unavailable. Run `npx gitnexus analyze` to reindex."

### Step 3 — Load functional plans

Glob `docs/plans/functional/*.md` and read every file.

For each file extract:
- The capability or system it describes
- Named actors (user roles, system actors)
- Named services, APIs, data entities
- Explicit cross-service dependencies mentioned
- UI surfaces described

Also read `docs/adr/ADR-*.md` titles and decisions — use these to avoid suggesting specs for decisions already captured as ADRs. ADRs are architectural decisions, not specs; do not exclude spec candidates just because an ADR exists in the same area.

Read `docs/openspec/specs/*/spec.md` titles — exclude candidates already fully specced.

### Step 4 — Discover via GraphRAG and GitNexus

Run ALL searches below. Do not skip any. If a scope argument was provided, append it to every query.

**GraphRAG searches** — content similarity across files, commits, issues, docs:

From functional plans (for each named capability, service, and entity extracted in Step 3):
- `mcp__mcp-graphrag-server__search: "<capability or entity name>"`

Standard searches (always run):
- `mcp__mcp-graphrag-server__search: "authentication login session token Cognito"`
- `mcp__mcp-graphrag-server__search: "signup registration onboarding account creation"`
- `mcp__mcp-graphrag-server__search: "OAuth social login Google Apple Microsoft LinkedIn"`
- `mcp__mcp-graphrag-server__search: "opportunity job match score verdict scoring"`
- `mcp__mcp-graphrag-server__search: "job search automation bot discovery"`
- `mcp__mcp-graphrag-server__search: "candidate profile resume career history"`
- `mcp__mcp-graphrag-server__search: "application tracking pipeline kanban status"`
- `mcp__mcp-graphrag-server__search: "document generation cover letter resume tailoring"`
- `mcp__mcp-graphrag-server__search: "chat AI assistant conversation message"`
- `mcp__mcp-graphrag-server__search: "notification email push websocket real-time"`
- `mcp__mcp-graphrag-server__search: "event EventBridge publisher envelope schema"`
- `mcp__mcp-graphrag-server__search: "calendar interview scheduling slot"`
- `mcp__mcp-graphrag-server__search: "company research enrichment profile"`
- `mcp__mcp-graphrag-server__search: "career path exploration role ladder"`
- `mcp__mcp-graphrag-server__search: "settings preferences user configuration"`
- `mcp__mcp-graphrag-server__search: "admin IAM roles permissions user management"`
- `mcp__mcp-graphrag-server__search: "pricing tier subscription billing plan"`
- `mcp__mcp-graphrag-server__search: "market research job market salary industry"`
- `mcp__mcp-graphrag-server__search: "M2M machine-to-machine service-to-service OAuth2 client credentials"`
- `mcp__mcp-graphrag-server__search: "idempotency retry deduplication"`
- `mcp__mcp-graphrag-server__search: "CDK Lambda API Gateway DynamoDB stack"`
- `mcp__mcp-graphrag-server__search: "secrets rotation SSM Parameter Store"`
- `mcp__mcp-graphrag-server__search: "WebSocket connection real-time push"`
- `mcp__mcp-graphrag-server__search: "type vault enumeration code-dependent value"`
- `mcp__mcp-graphrag-server__search: "plugin architecture extensibility hook"`
- `mcp__mcp-graphrag-server__search: "mobile React Native screen navigation"`
- `mcp__mcp-graphrag-server__search: "observability logging error handling CloudWatch"`
- `mcp__mcp-graphrag-server__search: "data view DDV dynamic extraction"`
- `mcp__mcp-graphrag-server__search: "leads marketing pre-launch waitlist"`
- `mcp__mcp-graphrag-server__search: "support ticket help desk"`

**GitNexus searches** — code-graph similarity across symbols, call chains, execution flows:

From functional plans (mirror of GraphRAG capability searches):
- `mcp__gitnexus__query: {query: "<capability or entity name>"}` for each term from Step 3

Standard searches (always run):
- `mcp__gitnexus__query: {query: "authentication login session token Cognito"}`
- `mcp__gitnexus__query: {query: "signup registration onboarding account creation"}`
- `mcp__gitnexus__query: {query: "OAuth social login Google Apple Microsoft LinkedIn"}`
- `mcp__gitnexus__query: {query: "opportunity job match score verdict scoring"}`
- `mcp__gitnexus__query: {query: "job search automation bot discovery"}`
- `mcp__gitnexus__query: {query: "candidate profile resume career history"}`
- `mcp__gitnexus__query: {query: "application tracking pipeline kanban status"}`
- `mcp__gitnexus__query: {query: "document generation cover letter resume tailoring"}`
- `mcp__gitnexus__query: {query: "chat AI assistant conversation message"}`
- `mcp__gitnexus__query: {query: "notification email push websocket real-time"}`
- `mcp__gitnexus__query: {query: "event EventBridge publisher envelope schema"}`
- `mcp__gitnexus__query: {query: "calendar interview scheduling slot"}`
- `mcp__gitnexus__query: {query: "company research enrichment profile"}`
- `mcp__gitnexus__query: {query: "career path exploration role ladder"}`
- `mcp__gitnexus__query: {query: "settings preferences user configuration"}`
- `mcp__gitnexus__query: {query: "admin IAM roles permissions user management"}`
- `mcp__gitnexus__query: {query: "pricing tier subscription billing plan"}`
- `mcp__gitnexus__query: {query: "market research job market salary industry"}`
- `mcp__gitnexus__query: {query: "M2M machine-to-machine service-to-service OAuth2 client credentials"}`
- `mcp__gitnexus__query: {query: "idempotency retry deduplication"}`
- `mcp__gitnexus__query: {query: "CDK Lambda API Gateway DynamoDB stack"}`
- `mcp__gitnexus__query: {query: "secrets rotation SSM Parameter Store"}`
- `mcp__gitnexus__query: {query: "WebSocket connection real-time push"}`
- `mcp__gitnexus__query: {query: "type vault enumeration code-dependent value"}`
- `mcp__gitnexus__query: {query: "plugin architecture extensibility hook"}`
- `mcp__gitnexus__query: {query: "mobile React Native screen navigation"}`
- `mcp__gitnexus__query: {query: "observability logging error handling CloudWatch"}`
- `mcp__gitnexus__query: {query: "data view DDV dynamic extraction"}`
- `mcp__gitnexus__query: {query: "leads marketing pre-launch waitlist"}`
- `mcp__gitnexus__query: {query: "support ticket help desk"}`

GitNexus results are grouped by execution process. Pay attention to which processes a symbol participates in — this reveals cross-repo coordination patterns invisible to content search.

### Step 5 — Merge and identify candidates

Combine all GraphRAG results, GitNexus results, and functional plan content into a single working set.

Group by **functional capability or technical concern** — not by repo or service. Ask: "what is this from the user's or platform's perspective?" One candidate may aggregate evidence from many repos.

For each candidate:

1. **Name it** — a clear, capability-scoped title (e.g., "Job Application Tracking", "Event Envelope Contract", "Opportunity Match Scoring")
2. **Type it** — Functional or Technical
3. **Map its scope** — list every repo, service, and UI surface with evidence
4. **Describe it** — one paragraph: what does this capability/concern do, who is involved, what does it touch?
5. **Note sources** — which evidence came from code only, functional plan only, or both
6. **Flag gaps** — anything described in the functional plan with no code evidence, or in code with no plan coverage

Do not cap the number of candidates. Surface everything the evidence supports.

Skip candidates already fully covered by an existing spec in `docs/openspec/specs/`.

### Step 6 — Append to candidate file

Append all new candidates to `docs/specs/candidates.md`.

The file is append-safe: if it already exists from a prior scoped run, add new candidates under a new scope heading. Do not overwrite existing entries.

File format:

```markdown
# Spec Candidates

<!-- Generated by /pmo:discover-more. Append-safe. Do not hand-edit ordering. -->

## [Scope: {scope argument or "full fleet"}] — {date}

### {Candidate Title}

- **Type**: Functional | Technical
- **Scope**: {comma-separated list of repos and UI surfaces}
- **Sources**: Code only | Plan only | Both
- **Gaps**: {what is in plans but not code, or in code but not plans — "None" if fully covered by both}

{One paragraph describing what this capability or concern does, who is involved, what it touches, and why it warrants a spec.}

**Evidence**:
- `{repo-name}` — {what was found, via GraphRAG / GitNexus / both}
- `{functional-doc}` — {what the plan describes}

---
```

### Step 7 — Print summary

After writing the file, print to screen:

```
## Discover Run Complete

Scope: {scope or "full fleet"}
Repos searched: {N} GraphRAG, {M} GitNexus
Functional plans read: {X}

New candidates added: {count}
Candidate file: docs/specs/candidates.md

Run again with a different scope to continue building the inventory:
  /pmo:discover-more auth
  /pmo:discover-more opportunities
  /pmo:discover-more events
  /pmo:discover-more profile
  /pmo:discover-more chat
  /pmo:discover-more admin
  /pmo:discover-more mobile
  /pmo:discover-more infrastructure
```

---

## Rules

- Candidates are capability-scoped, not service-scoped. One candidate may span many repos and UI surfaces.
- Both sources have equal authority: code evidence and functional plan content are merged, not ranked.
- Do NOT cap the number of candidates. Surface everything the evidence supports.
- Do NOT summarize. Each candidate entry must be specific enough to hand directly to `/pmo:spec` and produce a complete spec without guessing.
- Functional plan content is NOT evidence of implementation. Code evidence from GraphRAG/GitNexus is NOT evidence of design intent. Treat them as independent inputs that together form the full picture.
- MUST run both `mcp__mcp-graphrag-server__list_indexed_repos` and `mcp__gitnexus__list_repos` before searching.
- MUST read all `docs/plans/functional/*.md` files before searching.
- MUST read `docs/adr/ADR-*.md` titles — use to avoid duplicating ADR coverage in specs, but do not exclude spec candidates because an ADR exists nearby.
- MUST read `docs/openspec/specs/*/spec.md` titles — exclude only candidates already fully specced.
- Do NOT read files in other repos directly. GraphRAG and GitNexus provide cross-repo evidence.
- Repo names in output MUST match exactly the names returned by the index tools.
- Every candidate MUST cite specific evidence — repo names and what was found, noting which tool found it.
- Candidates MUST NOT be based on speculation. Every candidate needs at least one piece of concrete evidence from either GraphRAG, GitNexus, or a functional plan.
- Append to `docs/specs/candidates.md` — never overwrite. Prior runs' candidates are permanent.
- If scope is provided, only surface candidates clearly related to that domain. Save out-of-scope findings for the appropriate scoped run.
- Use `##` for run headings, `###` for candidate titles within the file.
