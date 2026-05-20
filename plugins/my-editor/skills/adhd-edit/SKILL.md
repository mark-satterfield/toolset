---
name: adhd-edit
description: "Structural editing skill for long-form technical and explanatory writing. Analyzes, suggests restructuring, or rearranges content to fix ordering problems, forward references, audience level inconsistency, orphaned tangents, redundancy, and detail imbalance. Activates when the user references /adhd-edit in any context. Accepts file paths, attached files, inline content, or conversation references as input. Three modes inferred from natural language: analyze (default), suggest, rearrange. Do not auto-invoke."
---

# ADHD Editor

Structural editing skill for long-form technical and explanatory writing. Detects ordering problems, audience inconsistency, forward references, orphaned tangents, redundancy, and detail imbalance — the specific failure modes of discovery-written and ADHD-pattern drafts.

## Invocation

This skill activates when the user references `/adhd-edit` in any natural language context. There is no rigid command syntax. The agent infers **mode**, **input**, and **output** from the user's message.

### Inferring mode

Three modes exist. Default to **analyze** when the user doesn't specify.

| Mode | Triggers (examples, not exhaustive) |
|------|--------------------------------------|
| **analyze** | "analyze", "review", "check", "what's wrong with", "look at", "audit", "evaluate", or no mode verb at all |
| **suggest** | "suggest", "propose", "how should I restructure", "what order should", "recommend a structure" |
| **rearrange** | "rearrange", "reorder", "restructure", "fix the order", "reorganize", "rebuild" |

If ambiguous, ask. "Use /adhd-edit on this article" without a mode verb → analyze (safest default, no modifications).

### Inferring input

The input is whatever writing the user points at. Accept any of:

- A file path (`~/articles/draft.md`, `./post.html`, a path from conversation context)
- An attached/uploaded file
- Inline content (prose pasted directly into the message or in a code block)
- A reference to something already in conversation ("the article above", "that draft")
- A URL (fetch it, then analyze the content)

If no input is identifiable, ask.

### Inferring output

- **analyze** and **suggest** modes produce a report. Default format: HTML. The user can override ("give me markdown", "just tell me in chat").
- **rearrange** mode produces a new file. Default name: `<original-filename>-restructured.<ext>`. The user can specify a different output path or filename ("output as `final-draft.md`", "save to `~/Desktop/v2.html`").
- If the input was inline text (not a file), rearrange outputs the restructured content inline or to a file if the user specifies one.

### Rearrange safeguards

- Never overwrite the original file.
- Before writing, present the proposed moves and wait for confirmation — unless the user's message makes intent unambiguous ("rearrange it and save it", "just do it").
- All original content is preserved. Rearrange moves sections; it does not delete, merge, or rewrite.
- Redundancy sites and unresolved tangents are annotated with inline comments (`<!-- ADHD-EDIT: ... -->`). The author decides what to cut.

### Example invocations (all valid)

```
/adhd-edit the attached file and suggest a new structure
```
→ Mode: suggest. Input: attached file.

```
Use /adhd-edit to analyze this:
[pasted prose]
```
→ Mode: analyze. Input: inline content.

```
rearrange ~/drafts/claude-code-article.md using /adhd-edit and output as ~/drafts/claude-code-v2.md
```
→ Mode: rearrange. Input: file path. Output: specified path.

```
/adhd-edit — what's wrong with the structure of this post?
[pasted prose]
```
→ Mode: analyze. Input: inline content.

```
Can you /adhd-edit suggest how to reorder sections 3-8 of ./article.html?
```
→ Mode: suggest. Input: file path. Scope: sections 3–8 only (partial analysis is valid).

---

## Analysis Framework

All three modes execute these six analyses. The analyze report presents them as distinct sections. The suggest and rearrange modes use them as input to the restructuring proposal.

### 1. Concept Dependency Graph

Extract every concept, term, tool, technology, and acronym that is either **introduced** (defined, explained, or given context) or **assumed** (used without explanation).

For each concept, record:
- **First introduction point** — where it is defined or explained (section + approximate position)
- **First usage point** — where it is first required for comprehension
- **All subsequent usage points**

Flag **forward references**: any concept whose first usage precedes its first introduction. These are the "remember this for later" patterns.

Flag **orphaned introductions**: any concept introduced but never referenced again. These may be tangent artifacts.

Flag **undefined assumptions**: any concept used but never introduced anywhere in the document. These are implicit audience knowledge requirements.

Report format per finding:
```
FORWARD REF: "GitHub App installation token" — used in §3 (step 4), introduced in §7.
  Impact: Reader encounters step 4 without knowing what an installation token is.
  Suggested fix: Move introduction to before §3, or add a brief inline definition at first use.
```

### 2. Audience Level Audit

Score every section on a 1–5 assumed-knowledge scale:

| Level | Description | Example |
|-------|-------------|---------|
| 1 | No prior knowledge assumed | "Version control tracks changes to files over time" |
| 2 | General tech literacy | "Clone the repository and check out a new branch" |
| 3 | Practitioner familiarity | "Add a pre-commit hook that runs the linter" |
| 4 | Domain expertise | "The EventBridge rule pattern uses content-based filtering on detail-type" |
| 5 | Specialist knowledge | "B-tree vs LSM-tree index trade-offs in OLTP workloads" |

Compute:
- **Per-section score** (the highest assumption level within that section)
- **Document median**
- **Variance** — flag any section whose score deviates from the median by more than 1.5 levels
- **Drift direction** — does the document trend upward (starts accessible, ends expert), downward, or oscillate?

Report audience whiplash explicitly:
```
AUDIENCE WHIPLASH: §2 scores Level 1 (explains what git is), §8 scores Level 5
  (assumes knowledge of columnar storage and micro-partition pruning).
  Gap: 4 levels. Reader calibrated to Level 1–2 will not follow §8.
```

### 3. Tangent and Resolution Tracker

A **tangent** is any topic, aside, or narrative thread that diverges from the section's main purpose.

For each tangent, determine:
- **Setup point** — where the tangent begins
- **Resolution point** — where it connects back to the main thread (if ever)
- **Value classification**:
  - **Essential context** — the main thread is incomprehensible without this
  - **Useful enrichment** — adds understanding but isn't required
  - **Entertainment/color** — adds personality or engagement but no information
  - **Orphaned** — introduced but never resolved or connected back

Flag orphaned tangents and tangents whose resolution is more than 2 sections away from their setup (these suggest the tangent should be relocated closer to its resolution, or the resolution should be moved up).

```
ORPHANED TANGENT: §5 introduces 1Password CLI service account pattern (setup at ¶3).
  No subsequent section references or builds on this.
  Question: Is this essential context for a later step, or a candidate for removal?
```

```
DISTANT RESOLUTION: §2 ¶4 sets up "iCloud Private Relay blocking API calls."
  Resolution appears in §9 ¶2 (7 sections later).
  Reader has likely forgotten the setup. Consider relocating setup closer to §9,
  or moving resolution into §2 as a brief note.
```

### 4. Redundancy Detection

Identify passages that cover the same concept, instruction, or explanation more than once.

For each redundancy:
- **Locations** — all instances with section and paragraph
- **Overlap type**:
  - **Exact repetition** — same information, similar wording
  - **Rephrased repetition** — same information, different wording
  - **Partial overlap** — one instance is a superset of the other
  - **Intentional reinforcement** — repetition that serves a pedagogical purpose (flag but don't treat as a defect)
- **Recommended primary location** — which instance is better placed given the document's flow

```
REDUNDANCY: "GitHub App token refresh mechanism" explained in §3 ¶2 and §7 ¶4.
  Overlap type: Rephrased repetition (~80% information overlap).
  §7 ¶4 is the more complete explanation.
  Suggestion: Keep §7 ¶4 as primary. Replace §3 ¶2 with a brief forward reference
  or reduce to one sentence with a pointer.
```

### 5. Detail Balance

Measure the depth of coverage for each major topic relative to its role in the document's purpose.

Metrics per topic:
- **Word count** (or approximate paragraph count)
- **Role**: core (essential to the document's purpose), supporting (provides necessary context), peripheral (nice-to-have)
- **Depth ratio**: word count relative to role importance

Flag imbalances:
- A **core** topic with less coverage than a **peripheral** topic
- Any single topic consuming more than 40% of total document length unless the document is about that one topic
- Sections where depth drops abruptly (detailed → superficial) without signaling the shift to the reader

```
DETAIL IMBALANCE: "Shell environment debugging" (peripheral) — 800 words.
  "Token refresh mechanism" (core) — 120 words.
  The peripheral topic has 6.7x the depth of the core topic.
  Suggestion: Reduce shell debugging to essential steps, expand token refresh,
  or split shell debugging into a separate linked document.
```

### 6. Structural Pattern Analysis

Identify the document's dominant structural pattern:

| Pattern | Description | Best for |
|---------|-------------|----------|
| **Deductive** | Claim → evidence → implications | Arguments, proposals, decision docs |
| **Tutorial** | Setup → step-by-step → verification | How-to guides, walkthroughs |
| **Narrative** | Chronological journey, experience → insight | Blog posts, retrospectives, case studies |
| **Problem-Solution** | Problem → context → solution → validation | Technical articles, troubleshooting |
| **Reference** | Categorical, non-sequential | API docs, spec sheets, lookup tables |
| **Hybrid: Just-in-time** | Problem → (context + step) repeated → outcome | Complex tutorials with heavy context requirements |

Determine:
- **Declared or implied pattern** — what the document appears to be trying to be
- **Actual pattern** — what the structure actually does
- **Deviations** — where the structure breaks from its own pattern

```
STRUCTURAL DEVIATION: Document reads as Problem-Solution (declared in intro),
  but §4–§6 switch to Narrative (chronological trial-and-error).
  This creates a reader expectation mismatch. Options:
  1. Commit to Narrative for the full document (journey-style).
  2. Commit to Problem-Solution: collapse §4–§6 into the final working solution,
     move trial-and-error to an appendix or "what I tried" sidebar.
  3. Use Hybrid Just-in-time: interleave problem-context-step units.
```

---

## Environment and Platform Awareness

When analyzing technical writing, account for platform-specific context that affects solution ordering. If the document references macOS, 1Password, AWS, specific shells, or other tools, treat those as **constraint context** — information the reader needs before encountering steps that depend on them. Flag when constraint context appears after the constrained step.

---

## Output Conventions

### Analyze mode output structure

```
# ADHD Editor — Structural Analysis
## Document: <filename>
## Pattern: <detected pattern> | Audience: <median level> (range: <min>–<max>)
## Summary: <2-3 sentence overview of the document's primary structural issues>

### 1. Concept Dependency Graph
<findings>

### 2. Audience Level Audit
<per-section scores, whiplash flags, drift direction>

### 3. Tangent and Resolution Tracker
<findings>

### 4. Redundancy Detection
<findings>

### 5. Detail Balance
<findings>

### 6. Structural Pattern Analysis
<findings>

### Priority Actions
<top 3-5 highest-impact changes, ranked by severity>
```

### Suggest mode output structure

Everything from analyze, plus:

```
### Proposed Restructuring

#### Current Order:
1. <section title/summary>
2. ...

#### Proposed Order:
1. <section title/summary> [was §N]
2. ...

#### Move Rationale:
- §3 → position 1: <reason>
- ...

#### Author Decisions Required:
- <question about ambiguous intent>
- ...
```

### Rearrange mode output

Writes to a new file (default: `<filename>-restructured.<ext>`, or user-specified path):
- All content preserved
- Sections reordered per the proposal
- `<!-- ADHD-EDIT: ... -->` comments at redundancy sites and unresolved tangents
- A changelog comment block at the top of the file listing every structural change made

---

## What This Skill Does Not Do

- Does not edit prose, voice, tone, or style
- Does not fix grammar or spelling
- Does not rewrite sentences
- Does not delete content (marks candidates for author review)
- Does not evaluate factual accuracy
- Does not impose a single "correct" structure — presents options with trade-offs when multiple valid orderings exist
