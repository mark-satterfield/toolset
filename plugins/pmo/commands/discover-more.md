---
description: Discover implicit architectural decisions and spec-worthy subsystems in an existing codebase.
argument-hint: "[scope]"
allowed-tools: Read, Glob, Grep, Task, AskUserQuestion
---

# Discover Implicit Architecture (SkillSpoke Fleet)

Explore the SkillSpoke fleet to discover implicit architectural decisions and specification-worthy subsystems. Uses GraphRAG for cross-repo discovery and reads `docs/plans/functional/` as requirement seeds. Produces a suggestion report -- does NOT create any files.

## Process

1. **Parse the scope**: Extract the optional scope from `$ARGUMENTS`.
   - A domain keyword: `auth`, `payments`, `notifications` -- used as a semantic filter appended to all GraphRAG searches
   - If `$ARGUMENTS` is empty, run full discovery with no filter

2. **Confirm GraphRAG index is available**:
   - Run `mcp__mcp-graphrag-server__list_indexed_repos` once
   - If the index is empty or unavailable, report: "GraphRAG index unavailable. Run `npx gitnexus analyze` to index the fleet before running this skill."
   - Note the indexed repo count for the discovery report header

3. **Load existing design artifacts and known requirements**:
   - Glob `docs/adrs/ADR-*.md` and read each file's title, context, and decision outcome
   - Glob `docs/openspec/specs/*/spec.md` and read each file's title and overview
   - Build an exclusion list of already-documented decisions and subsystems
   - Glob `docs/plans/functional/*.md` and read all files
     - Extract: capability names, actor names, domain terms, named services/systems
     - These become the primary seed terms for GraphRAG searches in Step 4
     - Treat these files as statements of intent -- NOT as evidence of implementation
   - If no functional docs exist, note it and proceed with architectural discovery only

4. **Discover system behavior across the fleet using GraphRAG**:

   Run semantic searches using terms derived from the functional docs (Step 3) and standard architectural categories. Run all standard searches; do not skip categories.

   **Searches seeded from functional docs**:
   - For each capability name and domain term extracted in Step 3, run:
     `mcp__mcp-graphrag-server__search: "<capability or domain term>"`
   - Run additional searches for related technical concerns implied by each capability
     (e.g., a "login" capability implies searches for "session", "token", "MFA", "Cognito")

   **Standard architectural searches** (always run regardless of functional docs):
   - `mcp__mcp-graphrag-server__search: "authentication authorization session token"`
   - `mcp__mcp-graphrag-server__search: "database schema migration ORM"`
   - `mcp__mcp-graphrag-server__search: "API REST endpoint route handler"`
   - `mcp__mcp-graphrag-server__search: "event message queue pub sub"`
   - `mcp__mcp-graphrag-server__search: "CDK CloudFormation infrastructure stack"`
   - `mcp__mcp-graphrag-server__search: "error handling logging observability"`
   - `mcp__mcp-graphrag-server__search: "frontend component UI state management"`
   - `mcp__mcp-graphrag-server__search: "deployment CI CD pipeline"`

   If a scope argument was provided, append it as a semantic qualifier to every search:
   e.g., scope="payments" → `mcp__mcp-graphrag-server__search: "payments authentication"`

   Treat GraphRAG results as cross-repo code evidence. Each result includes the repo name --
   use the exact repo name as it appears in the result (it matches `repositories/structure.json`).

5. **Merge, reconcile, and deduplicate findings**:
   - Combine all GraphRAG search results
   - For each capability found in the functional docs, classify its implementation status:
     - **Implemented**: GraphRAG found clear evidence in one or more repos
     - **Partially implemented**: GraphRAG found some evidence but gaps exist
     - **Not found**: No code evidence found -- mark as a spec gap
   - Group related findings across repos into coherent subsystems
   - Remove findings that overlap with existing ADRs or specs (exclusion list from Step 3)
   - For partial overlaps, note what the existing artifact covers and what remains undocumented

6. **Assign confidence levels** to each suggestion:
   - **High**: Explicit evidence in multiple repos or in core service files
   - **Medium**: Inferred from consistent patterns across a few files or repos
   - **Low**: Inferred from limited evidence or indirect signals

7. **Classify suggestions** into two categories:
   - **Suggested ADRs**: Implicit decisions where an alternative existed (technology choices, pattern choices, architectural trade-offs)
   - **Suggested Specs**: Subsystem boundaries with enough complexity to warrant formal specification (evidence in 2+ repos, clear interface, distinct responsibility)

8. **Produce the discovery report** using the output format below.

## Output Format

```
## Discovery Report

Analyzed {scope or "entire SkillSpoke fleet"}: {N} repos indexed by GraphRAG.
Functional docs: {X} capability files read from docs/plans/functional/.
Found {A} suggested ADRs and {B} suggested specs.
Existing artifacts: {C} ADRs, {D} specs (excluded from suggestions).

### Capability Coverage (from docs/plans/functional/)

| Capability | Status | Repos with Evidence |
|------------|--------|---------------------|
| {capability} | Implemented / Partial / Not Found | {repo names} |

### Suggested ADRs

| # | Confidence | Decision | Evidence | Command |
|---|------------|----------|----------|---------|
| 1 | High | {short decision title} | {repos + key evidence} | `/pmo:adr {description}` |
| 2 | Medium | {short decision title} | {repos + key evidence} | `/pmo:adr {description}` |

{For each suggestion, add a brief paragraph below the table:}

**1. {Decision title}**
{2-3 sentences explaining what was found, what the implicit decision is, and what alternatives likely existed.}
Evidence: `{repo}` -- `{file or pattern}`

### Suggested Specs

| # | Confidence | Subsystem | Repos | Command |
|---|------------|-----------|-------|---------|
| 1 | High | {subsystem name} | {repo names} | `/pmo:spec {capability}` |
| 2 | Medium | {subsystem name} | {repo names} | `/pmo:spec {capability}` |

{For each suggestion, add a brief paragraph below the table:}

**1. {Subsystem name}**
{2-3 sentences explaining the subsystem's responsibility, its cross-repo boundaries, and why it warrants a formal spec.}
Evidence: `{repo1}` -- `{pattern}`, `{repo2}` -- `{pattern}`

### Already Documented

{List existing ADRs and specs that cover areas found in the fleet. Omit if none.}

- ADR-XXXX: {title} -- covers {what area}
- SPEC-XXXX: {title} -- covers {what area}

### Next Steps

Pick the suggestions you want to formalize:

{For each high-confidence suggestion, repeat the command:}
```
/pmo:adr {description}
/pmo:spec {capability}
```

Or prime your session with existing context first: `/pmo:prime`
```

### Empty Results

If no suggestions are found:

```
## Discovery Report

Analyzed {scope or "entire SkillSpoke fleet"}: {N} repos indexed by GraphRAG.
No implicit architectural decisions or spec-worthy subsystems were identified.

This may indicate:
- The GraphRAG index is stale -- run `npx gitnexus analyze` to reindex
- A narrower scope might reveal more: `/pmo:discover-more auth`
- All major decisions are already documented in docs/adrs/ and docs/openspec/specs/

### Next Steps
- Create your first ADR manually: `/pmo:adr [description]`
- Create your first spec manually: `/pmo:spec [capability]`
```

## Rules

- This skill is READ-ONLY -- it MUST NOT create, modify, or delete any files
- Use `mcp__mcp-graphrag-server__search` as the primary discovery tool -- it covers all 60+ SkillSpoke repos in one call
- MUST run `mcp__mcp-graphrag-server__list_indexed_repos` before searches to confirm the index is available
- MUST read `docs/plans/functional/*.md` if present and use those terms to seed GraphRAG searches
- Functional docs state intent -- they are NOT evidence of implementation
- GraphRAG results are evidence of implementation -- they are NOT statements of intent
- Repo names in output MUST match exactly the names returned by GraphRAG (which match `repositories/structure.json`)
- If scope argument is provided, use it as a semantic filter appended to all GraphRAG searches
- Do NOT attempt to directly read files in other repos -- GraphRAG provides cross-repo evidence
- Every suggestion MUST cite specific evidence -- repo names and patterns from GraphRAG results
- Suggestions MUST NOT be based on speculation or assumptions about code that was not found in GraphRAG results
- MUST read existing ADRs and specs before producing suggestions to avoid duplicating already-documented decisions
- MUST include a confidence level (High, Medium, Low) for every suggestion
- MUST include a ready-to-use `/pmo:adr` or `/pmo:spec` command for every suggestion
- Sort suggestions by confidence (High first, then Medium, then Low) within each section
- Keep the report concise -- prefer fewer high-quality suggestions over many low-confidence ones
- Use `##` for the top-level heading and `###` for sections within the report
