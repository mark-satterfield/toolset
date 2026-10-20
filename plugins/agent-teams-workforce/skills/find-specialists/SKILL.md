---
name: find-specialists
description: >-
  The catalog of every agent of the agent-teams-workforce plugin, each with its description, the
  skills it loads and the MCP servers its tools reach, and the commands that search it. Use when
  deciding which specialist agents a subject of the design needs: to ask a specialist a question
  in your own session, or to name an agent and its request in your result for work done outside
  your session. The agents you choose are your decision; nothing else chooses them.
allowed-tools: [Bash, Read]
---

# Find specialists

`catalog.json` beside this file is the one home of the list of the plugin's agents. Each entry
is one agent, as its own definition file states it:

| Member | What it says |
|---|---|
| `name` | The name you start it by, and name it by in a request |
| `description` | What it is for |
| `skills` | The skills it loads when it starts: its specialised instructions |
| `mcpServers` | The MCP servers its tools reach, for example `aws-mcp` or `awslabs-dynamodb-mcp-server` |

The shape is `schemas/specialist-catalog.schema.json`.

## Searching it

Each command prints one JSON document:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/find-specialists/scripts/specialist_catalog.py" find <word> [<word> ...]
python3 "${CLAUDE_PLUGIN_ROOT}/skills/find-specialists/scripts/specialist_catalog.py" show <agent>
python3 "${CLAUDE_PLUGIN_ROOT}/skills/find-specialists/scripts/specialist_catalog.py" list
```

`find` returns the agents whose name, description, skills or MCP servers contain any of the
words, the most matches first. Search by the subject, in several words: `find sqs queue
dead-letter`, `find kms encryption key`, `find dynamodb table access pattern`. `list` gives every
name and description when you want to see the whole roster.

## Choosing

Every agent you use has a reason to be used: a subject of this Epic's design that its
description covers and that its skills and MCP servers equip it for. Choose from what the
entries say, never from a habit or a fixed list. A subject the Epic does not reach gets no
agent. A subject no agent covers, or one an agent covers without what the subject needs, is
yours to design with your own tools and resources; your definition says how you then recommend
a specialist to the owner.

## Using the agents you chose

- A question, or a quick bounded piece of work: start the agent in your own session by its
  `name`, as your definition says.
- Work done outside your session: name the agent and state its request in your result, as
  your definition and the result's schema say. The script starts that agent by the name you
  give, with your request, and hands you its answer. It decides nothing about which agent runs,
  and refuses a name the catalog does not list.

## How the catalog stays current

Nothing in `catalog.json` is written by hand. `scripts/specialist_catalog.py generate` writes it
from the front matter of every `agents/*.md` file, and `generate --check` fails when the file
differs from what the definitions give. The repository's pre-commit hook
`specialist-catalog-fresh` runs the check whenever an agent definition or this skill changes, so
a change to an agent that does not regenerate the catalog cannot be committed. After you change
an agent, run:

```bash
uv run --no-project --python 3.14 --with pyyaml python plugins/agent-teams-workforce/skills/find-specialists/scripts/specialist_catalog.py generate
```
