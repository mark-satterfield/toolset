# Search Recipes — order of precedence

Searching a polyrepo is not "run ripgrep." It is a decision about **which tool, in a
deliberate order**. Many projects keep a "second brain" — Obsidian, a RAG/GraphRAG index,
NotebookLM, a vector DB — and provide tools to search it that are faster and more
authoritative than scanning files. Use them. Generic text search is the last resort, not the
first.

## The ladder — always in this order

### 1. Follow the project's own instructions FIRST

Read the project's `CLAUDE.md` / `AGENTS.md` before searching anything. It tells you **where**
specific kinds of data live and **how** to interact with each location. If it says
"documentation lives in the Obsidian vault; search it with the obsidian-cli," then that *is*
the search — do not reach for ripgrep just because a recipe lists it. The project's own
instructions override this file.

### 2. Use the project's second-brain tools for the data type

Match the question to the store that owns that kind of knowledge:

| Looking for… | Reach for… |
|---|---|
| Product / architecture / decisions / docs / notes | Obsidian CLI over the project's vault (`obsidian-cli vault="<vault>" search query="…"`) |
| "Which repo owns / implements X", cross-repo code semantics | GraphRAG (`mcp__mcp-graphrag-server__search`) |
| Call graph, impact, "what breaks if I change X", symbols/flows | GitNexus (`gitnexus_query` / `gitnexus_context` / `gitnexus_impact`) |
| Synthesised Q&A over a curated corpus | NotebookLM notebooks, where the project provides them |
| Semantic similarity over embedded content | the project's vector DB, where provided |

These are usually faster and more accurate than file scanning for their data type, because the
content is already indexed and curated. Prefer them.

### 3. Fall back to generic search only when the above don't apply

For raw code/text that no index covers, descend this ladder:
`rg` (ripgrep) → `git grep` → `gh search code` → `gh api`. Reach for these when there is no
second-brain tool for the target, or to confirm/locate an exact string that an index pointed
you toward.

## Capture what you learn

When a non-obvious search turns out to be the right way to find something — **especially where a
kind of information lives** — record it, so the next search is faster: as a recipe here, or as a
"where to find it" entry in the knowledge store (`.polyrepo/knowledge.yaml`, via
**polyrepo-info**). A large share of tribal knowledge is exactly this: *where things are.*

## Recipe shape

- **intent** — what you are trying to find
- **command** — the actual command/query, using the highest-precedence tool that applies
- **scope** — repos/vaults it runs across
- **notes** — caveats; when to prefer a different tool

## When search is the wrong tool

If the answer is **structural** — repos, owners, dependencies, groups, deploy waves — it is in
the manifest; ask **polyrepo-repo**, don't search. Search is for what the manifest does not
hold.
