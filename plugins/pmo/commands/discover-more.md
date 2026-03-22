---
description: Discover implicit architectural decisions and spec-worthy subsystems in an existing codebase.
argument-hint: "[scope]"
allowed-tools: Read, Glob, Grep, Task, AskUserQuestion
---

# Discover Implicit Architecture (SkillSpoke Fleet)

Explore the SkillSpoke fleet to discover implicit architectural decisions and specification-worthy subsystems. Uses GraphRAG for cross-repo semantic content discovery and GitNexus for cross-repo code-graph discovery. Reads `docs/plans/functional/` as requirement seeds. Produces a suggestion report -- does NOT create any files.

## Process

1. **Parse the scope**: Extract the optional scope from `$ARGUMENTS`.
   - A domain keyword: `auth`, `payments`, `notifications` -- used as a semantic filter appended to all searches
   - If `$ARGUMENTS` is empty, run full discovery with no filter

2. **Confirm indexes are available**:
   - Run `mcp__mcp-graphrag-server__list_indexed_repos` once -- note the count for the report header
   - Run `mcp__gitnexus__list_repos` once -- note the count for the report header
   - If GraphRAG is unavailable, report: "GraphRAG index unavailable. Run `npx gitnexus analyze` to index the fleet."
   - If GitNexus is unavailable, proceed with GraphRAG only and note the gap in the report header
   - Both tools cover the full SkillSpoke fleet. GraphRAG searches content (files, commits, issues); GitNexus searches the code graph with embeddings (symbols, call chains, execution flows).

3. **Load existing design artifacts and known requirements**:
   - Glob `docs/adr/ADR-*.md` and read each file's title, context, and decision outcome
   - Glob `docs/openspec/specs/*/spec.md` and read each file's title and overview
   - Build an exclusion list of already-documented decisions and subsystems
   - Glob `docs/plans/functional/*.md` and read all files
     - Extract: capability names, actor names, domain terms, named services/systems
     - These become the primary seed terms for searches in Step 4
     - Treat these files as statements of intent -- NOT as evidence of implementation
   - If no functional docs exist, note it and proceed with architectural discovery only

4. **Discover system behavior across the fleet**:

   Run searches using terms derived from the functional docs (Step 3) and standard architectural categories. Run ALL searches from BOTH tools; do not skip any.

   **GraphRAG searches** (content similarity -- files, commits, issues, relationships):

   Seeded from functional docs:
   - For each capability name and domain term extracted in Step 3, run:
     `mcp__mcp-graphrag-server__search: "<capability or domain term>"`
   - Run additional searches for related technical concerns implied by each capability
     (e.g., a "login" capability implies searches for "session", "token", "MFA", "Cognito")

   Standard architectural searches (always run):
   - `mcp__mcp-graphrag-server__search: "authentication authorization session token"`
   - `mcp__mcp-graphrag-server__search: "database schema migration ORM"`
   - `mcp__mcp-graphrag-server__search: "API REST endpoint route handler"`
   - `mcp__mcp-graphrag-server__search: "event message queue pub sub"`
   - `mcp__mcp-graphrag-server__search: "CDK CloudFormation infrastructure stack"`
   - `mcp__mcp-graphrag-server__search: "error handling logging observability"`
   - `mcp__mcp-graphrag-server__search: "frontend component UI state management"`
   - `mcp__mcp-graphrag-server__search: "deployment CI CD pipeline"`

   **GitNexus searches** (code-graph similarity -- symbols, execution flows, call chains):

   Seeded from functional docs:
   - For each capability name and domain term extracted in Step 3, run:
     `mcp__gitnexus__query: {query: "<capability or domain term>"}`
   - Run additional searches for technical concerns implied by each capability (same implied terms as GraphRAG)

   Standard architectural searches (always run):
   - `mcp__gitnexus__query: {query: "authentication authorization session token"}`
   - `mcp__gitnexus__query: {query: "database schema migration ORM"}`
   - `mcp__gitnexus__query: {query: "API REST endpoint route handler"}`
   - `mcp__gitnexus__query: {query: "event message queue pub sub"}`
   - `mcp__gitnexus__query: {query: "CDK CloudFormation infrastructure stack"}`
   - `mcp__gitnexus__query: {query: "error handling logging observability"}`
   - `mcp__gitnexus__query: {query: "frontend component UI state management"}`
   - `mcp__gitnexus__query: {query: "deployment CI CD pipeline"}`

   GitNexus returns results grouped by execution process and ranked by relevance. Pay attention to which processes a symbol participates in -- this reveals cross-repo coordination patterns that GraphRAG content search cannot surface.

   If a scope argument was provided, append it as a semantic qualifier to every search in both tools:
   e.g., scope="payments" → `mcp__mcp-graphrag-server__search: "payments authentication"` and `mcp__gitnexus__query: {query: "payments authentication"}`

5. **Merge, reconcile, and deduplicate findings**:
   - Combine all GraphRAG and GitNexus results
   - When both tools return evidence for the same subsystem, treat it as higher-confidence signal
   - When only one tool finds evidence, note which tool found it -- this often indicates the nature of the pattern (document-level vs. code-structural)
   - For each capability found in the functional docs, classify its implementation status:
     - **Implemented**: Evidence found in one or more repos by either tool
     - **Partially implemented**: Some evidence exists but gaps remain
     - **Not found**: No code evidence from either tool -- mark as a spec gap
   - Group related findings across repos into coherent subsystems
   - Remove findings that overlap with existing ADRs or specs (exclusion list from Step 3)
   - For partial overlaps, note what the existing artifact covers and what remains undocumented

6. **Assign confidence levels** to each suggestion:
   - **High**: Evidence from both GraphRAG and GitNexus, or explicit evidence in multiple repos from either tool
   - **Medium**: Evidence from one tool across a few files or repos, or consistent pattern with limited cross-repo reach
   - **Low**: Inferred from limited evidence or indirect signals from a single tool

7. **Classify suggestions** into two categories:
   - **Suggested ADRs**: Implicit decisions where an alternative existed (technology choices, pattern choices, architectural trade-offs)
   - **Suggested Specs**: Subsystem boundaries with enough complexity to warrant formal specification (evidence in 2+ repos, clear interface, distinct responsibility)

8. **Produce the discovery report** using the output format below.

## Output Format

```
## Discovery Report

Analyzed {scope or "entire SkillSpoke fleet"}: {N} repos indexed by GraphRAG, {M} repos indexed by GitNexus.
Functional docs: {X} capability files read from docs/plans/functional/.
Found {A} suggested ADRs and {B} suggested specs.
Existing artifacts: {C} ADRs, {D} specs (excluded from suggestions).

### Capability Coverage (from docs/plans/functional/)

| Capability | Status | Repos with Evidence | Source |
|------------|--------|---------------------|--------|
| {capability} | Implemented / Partial / Not Found | {repo names} | GraphRAG / GitNexus / Both |

### Suggested ADRs

| # | Confidence | Decision | Evidence | Command |
|---|------------|----------|----------|---------|
| 1 | High | {short decision title} | {repos + key evidence} | `/pmo:adr {description}` |
| 2 | Medium | {short decision title} | {repos + key evidence} | `/pmo:adr {description}` |

{For each suggestion, add a brief paragraph below the table:}

**1. {Decision title}**
{2-3 sentences explaining what was found, what the implicit decision is, and what alternatives likely existed.}
Evidence: `{repo}` -- `{file or pattern}` (via {GraphRAG / GitNexus / both})

### Suggested Specs

| # | Confidence | Subsystem | Repos | Command |
|---|------------|-----------|-------|---------|
| 1 | High | {subsystem name} | {repo names} | `/pmo:spec {capability}` |
| 2 | Medium | {subsystem name} | {repo names} | `/pmo:spec {capability}` |

{For each suggestion, add a brief paragraph below the table:}

**1. {Subsystem name}**
{2-3 sentences explaining the subsystem's responsibility, its cross-repo boundaries, and why it warrants a formal spec.}
Evidence: `{repo1}` -- `{pattern}` (via {GraphRAG / GitNexus / both}), `{repo2}` -- `{pattern}` (via {GraphRAG / GitNexus / both})

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

Analyzed {scope or "entire SkillSpoke fleet"}: {N} repos indexed by GraphRAG, {M} repos indexed by GitNexus.
No implicit architectural decisions or spec-worthy subsystems were identified.

This may indicate:
- The GraphRAG or GitNexus index is stale -- run `npx gitnexus analyze` to reindex
- A narrower scope might reveal more: `/pmo:discover-more auth`
- All major decisions are already documented in docs/adr/ and docs/openspec/specs/

### Next Steps
- Create your first ADR manually: `/pmo:adr [description]`
- Create your first spec manually: `/pmo:spec [capability]`
```

## Rules

- This skill is READ-ONLY -- it MUST NOT create, modify, or delete any files
- Use BOTH `mcp__mcp-graphrag-server__search` and `mcp__gitnexus__query` for discovery -- they are complementary, not interchangeable
  - GraphRAG: content-similarity across files, commits, issues, and relationships
  - GitNexus: code-graph-aware similarity across symbols, call chains, and execution flows
- MUST run `mcp__mcp-graphrag-server__list_indexed_repos` and `mcp__gitnexus__list_repos` before searches
- MUST read `docs/plans/functional/*.md` if present and use those terms to seed searches in both tools
- Functional docs state intent -- they are NOT evidence of implementation
- Search results from either tool are evidence of implementation -- they are NOT statements of intent
- Repo names in output MUST match exactly the names returned by the discovery tools
- If scope argument is provided, use it as a semantic filter appended to all searches in both tools
- Do NOT attempt to directly read files in other repos -- GraphRAG and GitNexus provide cross-repo evidence
- Every suggestion MUST cite specific evidence -- repo names and patterns from search results, noting which tool found them
- Suggestions MUST NOT be based on speculation or assumptions about code that was not found in search results
- MUST read existing ADRs and specs before producing suggestions to avoid duplicating already-documented decisions
- MUST include a confidence level (High, Medium, Low) for every suggestion
- MUST include a ready-to-use `/pmo:adr` or `/pmo:spec` command for every suggestion
- Evidence found by both tools independently elevates confidence; evidence from only one tool does not reduce it
- Sort suggestions by confidence (High first, then Medium, then Low) within each section
- Keep the report concise -- prefer fewer high-quality suggestions over many low-confidence ones
- Use `##` for the top-level heading and `###` for sections within the report
