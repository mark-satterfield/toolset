# Skills

Catch-all bundle of frequently-used personal skills, plus a small skill-authoring toolkit.

## Install

```bash
claude plugin add mark-satterfield/skills
```

## Bundled skills

- **grill-me** — Interview the user relentlessly about a plan or design until
  reaching shared understanding, resolving each branch of the decision tree.
  (Source: mattpocock.)
- **caveman** — Ultra-compressed communication mode. Cuts token usage ~75% by
  dropping filler, articles, and pleasantries while keeping full technical
  accuracy. (Source: mattpocock.)
- **writing-great-skills** — The vocabulary and principles for writing and editing
  skills that behave predictably: invocation, description, information hierarchy,
  pruning, leading words, failure modes. User-invoked reference, and the source of
  truth the tools below cite. (Forked and assimilated.)
- **agent-skills-analyzer** — Plugin-architecture review: separates role (subagent)
  from playbook (skill), applies fork heuristics, and detects structural
  anti-patterns across a plugin's agents and skills, with a stdlib audit script.
  (Forked and assimilated.)

## Agents

- **skill-validator** — Read-only subagent that audits a single `SKILL.md` for
  frontmatter completeness, description trigger-quality, and tool coverage, emitting
  a structured report. Applies the `writing-great-skills` description principles at
  the single-file grain.

## Commands

- **`/skills:analyze-skills [plugin-or-repo-root]`** — Run the
  `agent-skills-analyzer` architectural audit and report findings by severity with a
  per-file verdict.
- **`/skills:gerund`** — Generate a whimsical gerund to make the human smile.

## The skill-authoring toolkit

Three artifacts at three altitudes — a framework and two consumers, not competing
tools:

- **writing-great-skills** — the reference (why and how a skill should read).
- **skill-validator** — the single-file checker (one `SKILL.md`).
- **agent-skills-analyzer** — the plugin-wide architectural review.

The reference is the single source of truth; the two tools cite it.

## Adding more

Drop a new skill into `skills/<name>/SKILL.md` with valid YAML frontmatter
(`name`, `description`) and it auto-registers.

## License

MIT
