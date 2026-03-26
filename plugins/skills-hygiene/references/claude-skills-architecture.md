# Claude Skills & Agent Architecture: Expert Domain Knowledge

Comprehensive reference guide for understanding the architecture, implementation patterns, and advanced practices in Claude Skills, plugins, hooks, and related agentic systems.

---

## Core Architecture & Design Philosophy

### The Meta-Tool Pattern

Claude Skills operate through a **meta-tool architecture** fundamentally different from traditional tools. Instead of executing discrete actions directly (like Read or Bash), skills inject specialized instructions into the conversation context and modify Claude's execution environment on-demand.

**Key distinction:**
- **Traditional tools** (Read, Write, Bash) execute immediately and return results
- **Skills** are discovery-based containers that inject instructions, alter permissions, and dynamically change model parameters for the duration of their activation
- **The Skill tool itself** is a meta-tool that manages all individual skills—when invoked, it loads a specific skill's content into context

### Progressive Disclosure Architecture

Skills employ a three-tier loading pattern optimized for token efficiency and context window management:

1. **Metadata Loading** (~100 tokens)
   - Claude scans all available skills' frontmatter (name, description, location)
   - Uses fuzzy matching on description text to identify relevance
   - No full skill content loaded at this stage
   - Metadata serves as the discovery mechanism

2. **Full Instructions** (<5,000 tokens recommended)
   - Complete SKILL.md body loads only when skill activation is determined
   - Markdown content structured for clarity and step-by-step workflows
   - Can reference bundled resources without loading them upfront

3. **Bundled Resources** (as needed)
   - Reference files (docs, schemas, templates) loaded only when referenced in instructions
   - Scripts execute via bash; code itself never enters context (only output)
   - Assets and templates loaded progressively based on actual task requirements
   - On-demand file access means a skill with 50 reference files uses minimal context if only 2 are needed

**Architectural benefit:** Multiple skills remain discoverable without overwhelming context. A project with 30 skills adds ~3,000 tokens for metadata only, full content loads on demand.

---

## Implementation Architectures

### Comparison: Skills vs. Plugins vs. Subagents vs. MCP Servers

| Component | Purpose | Scope | Invocation | Sharing | Use Case |
|-----------|---------|-------|-----------|---------|----------|
| **Skills** | Domain-specific instructions & workflows | Task-specific | Auto + Manual (/) | Across tools | Teaching Claude how to do things |
| **Plugins** | Bundled package (commands, skills, hooks, agents, MCP) | Project/Team | Manual setup | Marketplace | Standardize team setups |
| **Subagents** | Isolated agent instances with separate context | Long-running tasks | Explicit (Task tool) | Limited | Parallel work, prevent context pollution |
| **MCP Servers** | External tool/data source integrations | System integration | Automatic | Local config | Connect APIs, databases, services |
| **Hooks** | Deterministic automation at lifecycle events | Event-triggered | Automatic (no prompt) | Via plugins | Enforce standards, block actions |

**Decision matrix:**
- **Use Skills when:** capabilities should be discoverable, multi-turn workflows, teaching Claude specialized knowledge
- **Use Plugins when:** packaging multiple components for team distribution or marketplace
- **Use Subagents when:** needing parallel execution, specialized focus, preventing context growth
- **Use MCP when:** integrating external systems (GitHub, Jira, databases, APIs)
- **Use Hooks when:** deterministic enforcement is required (formatting, validation, security gates)

### Directory Structure Standards

Standard skill directory layout (follows Agent Skills open specification):

```
my-skill/
├── SKILL.md                 # Required: YAML frontmatter + instructions
├── scripts/                 # Optional: Python, Bash, JavaScript executables
│   ├── validator.py
│   └── processor.sh
├── references/              # Optional: Detailed documentation files
│   ├── PATTERNS.md
│   ├── SCHEMA.md
│   └── advanced-workflows.md
└── assets/                  # Optional: Templates, configs, static resources
    ├── template.json
    └── example-output.html
```

**Key constraints:**
- SKILL.md must be in root directory
- Directory name should match skill name in frontmatter
- Keep main SKILL.md under 500 lines (split into reference files if longer)
- Reference files focus on specific topics, loaded progressively

### Plugin Structure (Claude Code specific)

Plugins bundle multiple extension types with optional hot-reload during development:

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json              # Plugin metadata & configuration
├── .mcp.json                    # Optional: MCP server definitions
├── commands/                    # Optional: Slash command definitions (legacy)
├── skills/                      # Optional: Agent skills
│   └── my-skill/SKILL.md
├── agents/                      # Optional: Subagent definitions
│   └── reviewer-agent.md
├── hooks/                       # Optional: Event handlers
│   └── pre-commit-hook.sh
└── README.md                    # Documentation & installation
```

**Plugin components:**
- **Slash commands:** User-triggered actions (explicit invocation)
- **Skills:** Auto-discovered capabilities (pattern matching on description)
- **Subagents:** Specialized isolated agent instances
- **Hooks:** Automatic lifecycle event triggers
- **MCP servers:** External tool integrations

---

## SKILL.md Frontmatter Reference

Mandatory and optional metadata fields that control skill discovery and behavior:

```yaml
---
# REQUIRED
name: skill-name                    # 64 chars max, becomes /slash-command name
description: |                      # 200 chars max, CRITICAL for auto-discovery
  Use when [specific condition].
  Clear keywords for fuzzy matching.

# OPTIONAL - Claude Code extensions
allowed-tools:                      # Whitelist tools available in skill context
  - Read
  - Write
  - Bash
  # Omit to allow all tools

disable-model-invocation: false     # true = user-only invocation, no auto-discovery

arguments:                          # For parameterized skills
  - name: environment
    description: Target environment
    required: true

agent: Explore                      # Subagent to use (built-in: Explore, Plan, or custom)
context: fork                       # Execution context (fork = isolated, default = shared)

# OPTIONAL - Anthropic API
model-override: claude-opus-4.5     # Switch model during skill execution
extended-thinking: true             # Enable extended thinking (impacts token cost)
thinking-budget: 10000              # Max thinking tokens
---
```

**Discovery mechanism:** Claude uses description field with fuzzy matching. Example matches:
- Description: "Reviews Python code for security"
- User request: "check this for vulnerabilities" → Matched and loaded
- User request: "format this file" → Not matched

**Best practices for descriptions:**
- Include specific domains/languages ("Python", "Rust", "React")
- Mention use cases clearly ("when asked to", "for", "to")
- Add keywords related to the task ("security", "performance", "bugs")
- ❌ Poor: "Helps with code"
- ✅ Good: "Reviews Python/JavaScript code for security vulnerabilities, PEP 8 compliance, and performance issues"

---

## Skill Invocation Patterns

### Automatic (Model-Driven) Invocation

Claude automatically activates skills matching the current task context without explicit user request.

**How it works:**
1. User submits task prompt
2. Claude scans all available skill descriptions (frontmatter)
3. Fuzzy matching evaluates relevance between task and description
4. If match confidence exceeds threshold, skill content loads
5. Full SKILL.md instructions injected into conversation
6. Claude follows skill instructions for the remainder of the task

**Key behavior:**
- Multiple skills can activate for single task (skill stacking)
- Skills activate transparently; user may not realize they're active
- Works across conversation turns (skill remains active until context purge)
- Activated skills modify Claude's behavior only for their task scope

### Manual (User-Triggered) Invocation

Users explicitly invoke skills via slash commands.

```bash
/skill-name                         # Basic invocation
/skill-name argument1 arg2          # With arguments ($ARGUMENTS replaced in skill)
/skill-name[N]                      # Access argument by position ($N syntax)
```

**With arguments:**
```yaml
---
name: deploy
arguments:
  - name: environment
    required: true
---
Deploy to $ARGUMENTS environment following these steps...
```

User invokes: `/deploy production` → $ARGUMENTS = "production"

---

## Hook System Deep Dive

Hooks provide deterministic automation—guaranteed execution at specific lifecycle events. Unlike prompts (suggestions), hooks are hard-coded rules.

### 15 Lifecycle Events (Complete Reference)

| Event | Timing | Primary Use | Blocking? | Arguments |
|-------|--------|-------------|-----------|-----------|
| **PreToolUse** | Before any tool executes | Block dangerous commands, modify inputs | Yes (exit 2) | tool_name, tool_input, tool_use_id |
| **PostToolUse** | After tool execution succeeds | Auto-format, logging, post-processing | No (too late) | tool_name, tool_input, tool_output |
| **PostToolUseFailure** | After tool execution fails | Error handling, logging, recovery | No | tool_name, error object, exit_code |
| **PermissionRequest** | User shown permission dialog | Auto-approve safe ops | Yes (JSON decision) | tool_name, requires_review flag |
| **UserPromptSubmit** | User enters prompt, before Claude sees it | Skill activation, context injection | Via additionalContext | prompt_text, session metadata |
| **SessionStart** | Session begins or resumes | Inject context, load project state | No (stdout context only) | source (startup/resume/clear) |
| **SessionEnd** | Session terminates | Cleanup, logging, notifications | No | reason (exit/sigint/error) |
| **PreCompact** | Before context compaction | Backup transcripts, pre-compaction logging | No | n/a |
| **PostCompact** | After compaction completes | Post-compaction verification | No | n/a |
| **Stop** | When Claude finishes response | Enforce task completion, notifications | Yes (exit 2 = keep working) | $ARGUMENTS with response |
| **SubagentStop** | Subagent finishes | Validate subagent completion | Yes (exit 2 = keep working) | agent_id, completion status |
| **TaskComplete** | Long-running task finishes | Final logging, notifications | No | task metadata |
| **Notification** | Claude sends notification | Intercept/suppress alerts | No | notification_type, content |
| **ToolError** | Tool execution fails | Enhanced error handling | No | tool_name, error details |
| **SubagentSpawn** | New subagent created | Track agent creation, TTS announcements | No | agent_id, agent_type |

### Hook Types

**Command hooks** (shell scripts):
```json
{
  "type": "command",
  "command": "bash .claude/hooks/formatter.sh",
  "matcher": "Write|Edit",
  "async": false
}
```
- Receive event JSON on stdin
- Output/exit codes control behavior
- Minimal overhead (~1-5ms)
- Ideal for: formatting, validation, blocking

**Prompt hooks** (LLM-based):
```json
{
  "type": "prompt",
  "prompt": "Should this deployment proceed? Check for test failures: $ARGUMENTS",
  "timeout": 30,
  "matcher": "Stop"
}
```
- Send prompt to fast Claude (Haiku by default)
- Single-turn semantic evaluation
- Slower than command hooks (LLM call overhead)
- Response: `{"ok": true}` or `{"ok": false, "reason": "..."}`
- Ideal for: intelligent decisions requiring context

**Agent hooks** (agentic):
```json
{
  "type": "agent",
  "agent": "code-validator",
  "timeout": 60
}
```
- Spawn full subagent with tool access (Read, Grep, Glob)
- Multi-turn verification workflows
- Highest overhead (full agent spawn)
- Best for: complex validation requiring codebase analysis
- Ideal for: ensuring all modified files have tests

### Exit Code Semantics

**Standard exits:**
- `exit 0` – Allow action, proceed normally
- `exit 1` – Non-blocking warning, shows stderr in verbose mode
- `exit 2` – Block action (PreToolUse/Stop only), send stderr to Claude as feedback
- Other non-zero codes – Non-blocking, shown only in verbose mode

**PreToolUse blocking example:**
```bash
#!/bin/bash
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')

# Block dangerous patterns
if echo "$COMMAND" | grep -E 'drop table|rm -rf|curl.*|bash'; then
  echo "Blocked: dangerous command detected" >&2
  exit 2  # Block execution
fi

exit 0  # Allow
```

### Matcher Patterns

Matchers filter which tools/events trigger hooks:

```json
{
  "matcher": "Write|Edit|MultiEdit",      // Pipe-delimited tool names
  "matcher": "Edit",                       // Single tool
  "matcher": "*",                          // All tools
  "matcher": "mcp__github__.*",            // Regex for MCP tools
  "matcher": "Bash(git commit:*)",         // Tool with sub-operation
  "matcher": "startup",                    // Named matcher (SessionStart)
  "matcher": "compact"                     // Named matcher (PreCompact)
}
```

### Common Hook Patterns

**Auto-formatting on file write:**
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "npx prettier --write \"$CLAUDE_TOOL_INPUT_FILE_PATH\""
          }
        ]
      }
    ]
  }
}
```

**Block dangerous bash operations:**
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/security-check.sh"
          }
        ]
      }
    ]
  }
}
```

**Inject project context at session start:**
```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cat .claude/session-context.md"
          }
        ]
      }
    ]
  }
}
```

**Enforce task completion:**
```json
{
  "hooks": {
    "Stop": [
      {
        "type": "prompt",
        "prompt": "Check if all requirements from the original task are complete: $ARGUMENTS. Return {\"ok\": false, \"reason\": \"...\"} if work remains.",
        "timeout": 30
      }
    ]
  }
}
```

---

## MCP (Model Context Protocol) Integration

MCP servers provide standardized access to external tools and data sources. They can be bundled in plugins or configured standalone.

### Plugin MCP Configuration

**In .mcp.json (plugin root):**
```json
{
  "database-tools": {
    "command": "${CLAUDE_PLUGIN_ROOT}/servers/db-server",
    "args": ["--config", "${CLAUDE_PLUGIN_ROOT}/config.json"],
    "env": {
      "DB_URL": "${DB_URL}",
      "API_KEY": "${CLAUDE_PLUGIN_VAULT}"
    }
  },
  "github-mcp": {
    "type": "sse",
    "url": "https://mcp.github.com/sse"
  }
}
```

**In plugin.json (inline):**
```json
{
  "mcpServers": {
    "plugin-api": {
      "command": "${CLAUDE_PLUGIN_ROOT}/servers/api-server",
      "args": ["--port", "8080"]
    }
  }
}
```

### Transport Types

- **stdio** – Local process, most secure, requires binary installed
- **SSE (Server-Sent Events)** – Remote HTTP streaming, firewall-friendly
- **HTTP** – Stateless REST requests (recommended for cloud services)
- **WebSocket** – Real-time bidirectional communication (rare)

### Tool Naming Convention

MCP tools appear with plugin-scoped prefixes:
```
mcp__plugin_<plugin-name>_<server-name>__<tool-name>

Examples:
mcp__plugin_github_github__create_issue
mcp__plugin_jira_jira__search_issues
mcp__plugin_asana_asana__create_task
```

**Security best practice:** Explicitly whitelist specific tools in allowed-tools, never use wildcards:
```yaml
allowed-tools:
  - mcp__plugin_github_github__create_issue
  - mcp__plugin_github_github__search_issues
# ❌ DON'T: ["mcp__plugin_github_github__*"]
```

---

## Agents & Subagents

### Subagent Orchestration

Subagents are isolated Claude Code instances spawned for parallel work or specialized focus. They prevent context pollution in long-running sessions.

**Spawning a subagent:**
```yaml
---
name: deep-research
description: Investigate a topic thoroughly with isolated context
context: fork
agent: Explore
---
Research $ARGUMENTS thoroughly:
1. Find relevant files using Glob and Grep
2. Read and analyze the code
3. Summarize findings with specific file references

Results returned to main conversation
```

**Execution model:**
- Main agent spawns subagent via Task tool
- Subagent runs in isolated context with separate transcript
- Subagent results summarized and returned to main
- No context growth in main session (subagent context isolated)

**Use cases:**
- Parallel validation (multiple code reviewers)
- Specialized deep dives (research into specific domains)
- Long-running analysis (prevent main transcript bloat)
- Role separation (architect vs. implementor workflow)

---

## Discovery Mechanisms

### How Claude Finds Skills

1. **Filesystem scanning** at skill path discovery time:
   - `~/.claude/skills/` (user level, highest priority)
   - `.claude/skills/` (project level)
   - Enterprise-defined locations

2. **Frontmatter extraction** for all discovered skills:
   - Name, description, location, metadata parsed
   - ~100 tokens total for 20 skills

3. **Fuzzy matching** on current task:
   - Description text compared against user prompt + context
   - Relevance scoring determines activation
   - Multiple skills can match single task

4. **On-demand loading** when match identified:
   - Full SKILL.md loads into context
   - Script binaries remain on filesystem
   - Reference files loaded only when mentioned

### Skill Priority & Conflicts

When multiple skills share same name (different locations):

**Priority order (highest to lowest):**
1. Enterprise-level skills
2. Personal skills (`~/.claude/skills/`)
3. Project skills (`.claude/skills/`)

**Conflict resolution:**
- First match in priority order wins
- Use unique naming to avoid conflicts
- Or explicitly invoke with `/skill-name`

---

## Open Standard Specification

Claude Skills follow the **Agent Skills specification** (agentskills.io) for platform interoperability.

### Platforms Adopting Agent Skills Standard

- **Anthropic Claude** (claude.ai, Claude Code, API)
- **Microsoft** (GitHub Copilot, VS Code)
- **OpenAI** (Codex)
- **Figma** (design tool integration)
- **Cursor** (editor)
- **Atlassian** (Jira, Confluence)

**Implication:** A skill written to Agent Skills spec works across all platforms with minimal modification. Platform-specific features (hooks, MCP in plugins) are extensions layered on top.

### Specification Compliance

**Required:**
- SKILL.md in root directory
- YAML frontmatter with name/description
- Markdown body with clear instructions

**Optional but recommended:**
- scripts/ directory for executables
- references/ for detailed docs
- assets/ for templates/configs
- Keep SKILL.md under 5,000 tokens
- Include examples and expected outputs

---

## Best Practices

### Skill Design

1. **Keep SKILL.md focused and concise**
   - Single responsibility principle
   - Under 500 lines main content
   - Reference files for supplemental info
   - Clear section headers and examples

2. **Write descriptions for discovery**
   - Include specific use cases
   - Use domain-specific keywords
   - Mention when to use ("when", "for", "to")
   - ✅ "Reviews TypeScript code for type safety and unused variables"
   - ❌ "Code review skill"

3. **Bundle supporting resources**
   - Templates in assets/
   - Schema definitions in references/
   - Scripts in scripts/ with shebang
   - Progressive disclosure = lower token cost

4. **Test incrementally**
   - Start with basic instructions
   - Add complexity gradually
   - Test both auto and manual invocation
   - Verify with `/help` that skill loads correctly

### Plugin Development

1. **Compose skills, don't duplicate**
   - Each skill single concern
   - Skills can stack naturally
   - Avoid overlapping descriptions

2. **Use plugin.json metadata**
   - Version bumping
   - Dependencies declaration
   - Environment variable documentation

3. **Hot-reload during development**
   - Edit SKILL.md and file changes apply immediately
   - Restart Claude Code to reload hooks
   - Hook file changes require review in /hooks

### Hook Implementation

1. **Use PreToolUse for blocking decisions**
   - Exit 0 = allow, exit 2 = block
   - Message sent via stderr
   - Most common hook pattern

2. **Use PostToolUse for formatting/validation**
   - Runs after tool executes
   - Can't block (too late)
   - Useful for auto-format, logging

3. **Use SessionStart for context injection**
   - Load project state (git status, branch)
   - Inject coding guidelines
   - Set environment variables
   - Runs once per session

4. **Use Stop hook for task completion enforcement**
   - Exit 2 forces Claude to keep working
   - Prevents premature stopping
   - Use prompt hook for intelligent evaluation

### MCP Integration

1. **Prefer HTTP for cloud services**
   - Firewall-friendly (outbound HTTPS)
   - Stateless (easier scaling)
   - No local binary required

2. **Use stdio for local services**
   - Maximum security/control
   - Single machine scope
   - Requires process management

3. **Document all environment variables**
   - List in README
   - Example configuration
   - Vault/secret management approach

---

## Troubleshooting & Common Pitfalls

### Skill Discovery Issues

**Problem:** Skill never activates automatically
**Root causes:**
- Description too vague or irrelevant to task
- Skill name/description keywords don't match user language
- Skill disabled via `disable-model-invocation: true`

**Solutions:**
- Rewrite description with specific use case keywords
- Include exact terms users might employ
- Verify with `/skill-name` manual invocation first

**Problem:** Wrong skill activates (skill stacking)
**Root cause:** Multiple skill descriptions match task context

**Solution:**
- Make descriptions more specific and distinct
- Use domain-specific language in descriptions
- Test with explicit invocation to isolate

### Context & Performance Issues

**Problem:** Skills consuming too much context
**Root cause:** SKILL.md too large, all reference files loaded upfront

**Solutions:**
- Split long SKILL.md into multiple reference files
- Structure instructions to reference files only when needed
- Test with `/help` and observe token count

**Problem:** Hook overhead affecting performance
**Root cause:** Too many hooks, non-async execution, LLM-based hooks overused

**Solutions:**
- Use async: true for long-running hooks
- Prefer command hooks over prompt hooks
- Minimize LLM-based hooks (use sparingly for complex decisions)
- Profile hook performance with detailed logging

---

*Last updated: February 2026. This document reflects Claude Skills architecture, Agent Skills specification, and Claude Code plugin system as of Q1 2026.*
