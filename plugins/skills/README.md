# Skills

Catch-all bundle of frequently-used personal skills.

## Install

```bash
claude plugin add mark-satterfield/skills
```

## Bundled Skills

- **my-style** — Encodes Mark's voice, language, humor, and writing
  techniques. Apply on demand to any prose Mark is writing or has Claude
  write on his behalf. Does not auto-invoke.
- **grill-me** — Interview the user relentlessly about a plan or design
  until reaching shared understanding, resolving each branch of the
  decision tree. (Source: mattpocock.)
- **caveman** — Ultra-compressed communication mode. Cuts token usage
  ~75% by dropping filler, articles, and pleasantries while keeping
  full technical accuracy. (Source: mattpocock.)
- **polyrepo-steward** — Reactive and proactive caretaker, curator, and
  mentor for poly-repo projects. Knows the project's repos, their
  purposes, owners, dependencies, conventions, search patterns, rules,
  and documentation locations — and keeps that knowledge current as the
  project changes. Topology-agnostic (siblings, meta+satellites,
  monorepo+satellites, scattered, etc.) — discovers structure by
  interviewing the human and maintains a project-side manifest.
  Includes a companion read-only delegation agent
  (`polyrepo-cartographer`) for context-light lookups.

## Adding More

Drop a new skill into `skills/<name>/SKILL.md` with valid YAML
frontmatter (`name`, `description`) and it auto-registers.

## License

MIT
