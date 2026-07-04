# @mark-satterfield/toolset

A curated collection of Claude Code plugins, published to the `mark-satterfield` marketplace namespace. Although they target Claude Code, most plugins work well with other agent harnesses (e.g. Codex) too.

## Structure

Everything is a plugin under `plugins/<name>/`. Each plugin bundles its own commands, skills, agents, and hooks, and documents itself in a `README.md` (human-facing) and a `CLAUDE.md` (agent-facing). There is no top-level `skills/` directory — skills live inside the plugin that owns them, with loose or miscellaneous skills collected in the `plugins/skills` catch-all.

## Installation

Install a plugin by its **marketplace name** (a few differ from the directory name — see the table):

```bash
claude plugin add mark-satterfield/<marketplace-name>
```

Or copy the plugin directory into your Claude config manually:

```bash
cp -r plugins/<name> ~/.claude/plugins/     # global
cp -r plugins/<name> .claude/plugins/       # project-local
```

Then enable the plugin in Claude Code settings.

## Plugins

| Marketplace name | Directory | Description |
| --- | --- | --- |
| `prompt` | [prompt-library](./plugins/prompt-library) | Prompt-template management: create, search, run, compose, orchestrate |
| `gitignore-guardian` | [gitignore-guardian](./plugins/gitignore-guardian) | `.gitignore` management + protective PreToolUse hooks |
| `chat-history` | [chat-history](./plugins/chat-history) | Extract Claude Code session history into a project `.chats/` |
| `dir-dr` | [dir-dr](./plugins/dir-dr) | Directory Doctor — audit, map, and safely reorganize directory structure |
| `skills-hygiene` | [skills-hygiene](./plugins/skills-hygiene) | Deduplicate, promote, audit, and generalize skill installations |
| `agent-teams-workforce` | [agent-teams-workforce](./plugins/agent-teams-workforce) | Phase-gated SDLC agent workforce (primary, under active development) |
| `award-web-builder` | [award-web-builder](./plugins/award-web-builder) | Award-tier website builder agent with design-system skills |
| `self-improving-agent` | [self-improving-agent](./plugins/self-improving-agent) | Curate memory; promote learnings to rules and skills |
| `research-summarizer` | [research-summarizer](./plugins/research-summarizer) | Structured research summarization and briefs |
| `skills` | [skills](./plugins/skills) | Catch-all bundle of frequently-used personal skills |
| `my-editor` | [my-editor](./plugins/my-editor) | Personal editing and writing-style toolkit |
| `patent` | [patent](./plugins/patent) | Patent-prep toolkit: ideate → draft → triage (free public data only) |
| `obsidian` | [obsidian](./plugins/obsidian) | Obsidian toolkit: CLI, Bases, Canvas, Markdown, Defuddle |
| `cds` | [cds](./plugins/cds) | Customizable Design System — brand-neutral stylesheet/mock/component generator |
| `memre` | [memre](./plugins/memre) | Memory-and-deliverable hygiene: residue linter/fixer, PostToolUse residue hook, auto-memory audit, markdown-to-beads importer |

_In development (not yet on the marketplace):_ **forge** (`plugins/forge`) — tooling for the FORGE framework: author precise, gap-free instructions an AI agent can execute without interpretation.

## License

MIT
