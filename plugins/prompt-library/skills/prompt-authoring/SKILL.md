---
name: Prompt Authoring
description: Activates when a user is writing, editing, designing, or asking about prompt templates. Provides guidance on variable syntax, frontmatter schema, category namespacing, composition patterns, and best practices for reusable, maintainable prompts in the prompt-library plugin.
version: 1.0.0
---

## Variable Syntax

Use `{{variable}}` for required variables and `{{variable|default}}` for optional ones:

```
You are a {{role}} specializing in {{domain|software engineering}}.
```

- Required variables with no default will prompt the user for a value at run time
- Default values are used when the user provides no inline value
- Variable names must be alphanumeric with underscores: `{{my_variable}}` not `{{my variable}}`
- Declare all variables in the frontmatter `variables` array with a description

## Frontmatter Schema

Every prompt file must have YAML frontmatter:

```yaml
---
name: category/prompt-name
description: One sentence describing what this prompt does
tags: [tag1, tag2]
variables:
  - name: variable_name
    description: What this variable represents
    default: optional default value
pinned: false
---
```

Required fields: `name`, `description`
Optional fields: `tags`, `variables`, `pinned`

## Category Namespacing

Organize prompts using path-style names. The name becomes the file path:

```
coding/review        → .claude/prompts/coding/review.md
coding/refactor      → .claude/prompts/coding/refactor.md
writing/email        → .claude/prompts/writing/email.md
writing/summary      → .claude/prompts/writing/summary.md
```

Keep category names broad (3-5 categories max per library). Prefer:
- `coding/` over `typescript/` and `python/` separately
- `writing/` over `email/` and `docs/` separately

## Scope: Global vs Project-Local

- **Global** (`~/.claude/prompts/`): prompts you use across all projects — general-purpose templates, personal preferences, role definitions
- **Project-local** (`.claude/prompts/`): prompts specific to this codebase — architecture-specific instructions, project conventions, team patterns

Project-local prompts override global prompts with the same name.

Use `--global` flag on `/prompt:create` to save globally. Default is project-local.

## Writing Effective Prompts

**Be specific, not vague:**
```
# Weak
Be concise and helpful.

# Strong
Respond in 3 sentences or fewer. Prioritize what the user must know now over background context.
```

**Define output format when it matters:**
```
Return a JSON object with keys: { summary: string, issues: string[], recommendation: string }
```

**Front-load the core instruction:**
Put the most important directive first. Claude weighs earlier instructions more heavily.

**One prompt, one purpose:**
If a prompt does two unrelated things, split it. Use `/prompt:exec` to run them together.

## Compose vs Exec

**Use `/prompt:compose`** when:
- Two prompts have overlapping intent and you want one authoritative version
- A base template and a specialized template should merge into a single coherent prompt
- Duplication or contradictions exist between two prompts

**Use `/prompt:exec --sequential`** when:
- Two prompts are independent tasks that happen to be run together
- Output from the first informs the second
- The prompts cover different domains and should remain separate

**Use `/prompt:exec --parallel`** when:
- Two prompts are completely independent
- You want both results simultaneously
- Order does not matter

## Pin for Quick Access

Mark frequently used prompts with `pinned: true` in frontmatter (or `--pin` flag on create/edit). Pinned prompts appear first in `/prompt:list`.
