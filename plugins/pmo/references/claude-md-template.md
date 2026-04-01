## Architecture Context

This project uses the design pluginfor architecture governance.

- Architecture Decision Records are in `docs/adr/`
- Specifications are in `docs/openspec/specs/`

### Design Plugin Skills

| Skill | Purpose |
|-------|---------|
| `/pmo:adr` | Create a new Architecture Decision Record |
| `/pmo:spec` | Create a new specification |
| `/pmo:list` | List all ADRs and specs with status |
| `/pmo:status` | Update the status of an ADR or spec |
| `/pmo:docs` | Generate a documentation site |
| `/pmo:init` | Set up CLAUDE.md with architecture context |
| `/pmo:prime` | Load architecture context into session |
| `/pmo:check` | Quick-check code against ADRs and specs for drift |
| `/pmo:audit` | Comprehensive design artifact alignment audit |
| `/pmo:discover` | Discover implicit architecture from existing code |
| `/pmo:plan` | Break a spec into trackable issues with project grouping and branch conventions |
| `/pmo:organize` | Retroactively group issues into tracker-native projects |
| `/pmo:enrich` | Add branch naming and PR conventions to existing issues |
| `/pmo:work` | Pick up tracker issues and implement them in parallel using git worktrees |
| `/pmo:review` | Review and merge PRs using reviewer-responder agent pairs |

Run `/pmo:prime [topic]` at the start of a session to load relevant ADRs and specs into context.

### Governing Comments

When implementing code governed by ADRs or specs, leave comments referencing the governing artifacts:

```
// Governing: ADR-0001 (chose JWT over sessions), SPEC-0003 REQ "Token Validation"
```

These comments help future sessions (and `/pmo:check`) trace implementation back to decisions.

### Workflow

1. **Decide**: `/pmo:adr` — record the architectural decision
2. **Specify**: `/pmo:spec` — formalize requirements with RFC 2119 language
3. **Plan**: `/pmo:plan` — break the spec into trackable issues in your tracker
4. **Enrich**: `/pmo:organize` and `/pmo:enrich` — add projects and branch conventions
5. **Build**: `/pmo:work` — pick up issues and implement in parallel using git worktrees
6. **Review**: `/pmo:review` — review and merge PRs with spec-aware code review
7. **Validate**: `/pmo:check` and `/pmo:audit` to catch drift
