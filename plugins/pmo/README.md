# design

A Claude Code plugin for architecture governance: ADRs, specifications, sprint planning, parallel implementation, code review, and documentation generation.

## Skills

| Skill | Invoke | Description |
|-------|--------|-------------|
| **ADR** | `/pmo:adr [description] [--review]` | Create an ADR using MADR format with Mermaid diagrams |
| **Spec** | `/pmo:spec [capability] [--review]` | Create spec.md + design.md with RFC 2119 requirements and Mermaid diagrams |
| **Init** | `/pmo:init` | Set up CLAUDE.md with architecture context for design-aware sessions |
| **Prime** | `/pmo:prime [topic]` | Load ADR and spec context into the session, optionally filtered by topic |
| **Check** | `/pmo:check [target]` | Quick-check code against ADRs and specs for drift |
| **Audit** | `/pmo:audit [scope] [--review] [--scrum]` | Comprehensive drift audit; use `--scrum` for team-triaged findings grouped into prioritized remediation themes |
| **Docs** | `/pmo:docs [project name]` | Generate docs with scaffold/integration modes and manifest-based upgrades |
| **List** | `/pmo:list [adr\|spec\|all]` | List all ADRs and specs with their status |
| **Discover** | `/pmo:discover [scope]` | Discover implicit architecture from an existing codebase |
| **Plan** | `/pmo:plan [spec-name or SPEC-XXXX] [--scrum] [--review] [--project <name>] [--no-projects] [--branch-prefix <prefix>] [--no-branches]` | Break a spec into trackable issues; use `--scrum` for a full team-groomed ceremony with spec audit, multi-agent grooming, and automatic organize + enrich |
| **Organize** | `/pmo:organize [SPEC-XXXX or spec-name] [--project <name>] [--dry-run]` | Retroactively group existing issues into tracker-native projects |
| **Enrich** | `/pmo:enrich [SPEC-XXXX or spec-name] [--branch-prefix <prefix>] [--dry-run]` | Add branch naming and PR conventions to existing issue bodies |
| **Work** | `/pmo:work [SPEC-XXXX \| issue numbers \| (empty = propose from backlog)] [--max-agents N] [--draft] [--dry-run] [--no-tests]` | Pick up tracker issues and implement them in parallel using git worktrees |
| **Review** | `/pmo:review [SPEC-XXXX or PR numbers] [--pairs N] [--no-merge] [--dry-run]` | Review and merge PRs using reviewer-responder agent pairs |
| **Status** | `/pmo:status [ID] [status]` | Change the status of an ADR or spec |

## Install

Add to your project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "claude-plugin-design": {
      "source": {
        "source": "github",
        "repo": "joestump/claude-plugin-design"
      }
    }
  },
  "enabledPlugins": {
    "design@claude-plugin-design": true
  }
}
```

Then restart Claude Code. The plugin's 15 skills will be available as `/pmo:init`, `/pmo:prime`, `/pmo:adr`, `/pmo:spec`, `/pmo:plan`, `/pmo:organize`, `/pmo:enrich`, `/pmo:work`, `/pmo:review`, `/pmo:check`, `/pmo:audit`, `/pmo:discover`, `/pmo:docs`, `/pmo:list`, and `/pmo:status`.

## Configuration

The `.claude-plugin-design.json` file is a persistent, project-level configuration file for the design plugin. It stores tracker preferences, project settings, branch conventions, and review configuration so you are not re-prompted on every invocation.

**This file should be committed to git** -- it contains shared team settings (tracker choice, branch naming conventions, project defaults) that benefit all contributors.

### Schema Reference

```json
{
  "tracker": "github",
  "tracker_config": {
    "owner": "your-org",
    "repo": "your-project"
  },
  "projects": {
    "default_mode": "per-epic",
    "project_ids": {},
    "views": ["All Work", "Board", "Roadmap"],
    "columns": ["Todo", "In Progress", "In Review", "Done"],
    "iteration_weeks": 2
  },
  "branches": {
    "enabled": true,
    "prefix": null,
    "epic_prefix": "epic",
    "slug_max_length": 50
  },
  "pr_conventions": {
    "enabled": true,
    "close_keyword": null,
    "ref_keyword": "Part of",
    "include_spec_reference": true
  },
  "worktrees": {
    "base_dir": null,
    "max_agents": 3,
    "auto_cleanup": false,
    "pr_mode": "ready"
  },
  "review": {
    "max_pairs": 2,
    "merge_strategy": "squash",
    "auto_cleanup": false
  }
}
```

All keys are optional. The file is created automatically when you first save a tracker preference via `/pmo:plan` or `/pmo:spec`. Skills merge their updates non-destructively -- existing keys are never overwritten.

### Sections

| Section | Written By | Read By | Purpose |
|---------|-----------|---------|---------|
| `tracker` | `/pmo:plan`, `/pmo:spec` | All planning/work/review skills | Which issue tracker to use (`github`, `gitea`, `gitlab`, `jira`, `linear`, `beads`) |
| `tracker_config` | `/pmo:plan`, `/pmo:spec` | All planning/work/review skills | Tracker-specific settings (owner/repo, project key, team ID) |
| `projects` | `/pmo:plan`, `/pmo:organize` | `/pmo:plan`, `/pmo:organize` | Project grouping defaults, cached project IDs, view/column/iteration config |
| `branches` | `/pmo:plan` | `/pmo:plan`, `/pmo:enrich` | Branch naming conventions (prefix, epic prefix, slug length) |
| `pr_conventions` | `/pmo:plan` | `/pmo:plan`, `/pmo:enrich` | PR close keyword and reference format |
| `worktrees` | Manual | `/pmo:work` | Worktree base directory, agent concurrency, cleanup, PR mode |
| `review` | Manual | `/pmo:review` | Reviewer pair count, merge strategy, cleanup |

### Key Reference

| Key | Default | Description |
|-----|---------|-------------|
| `tracker` | *(detected)* | Issue tracker name: `github`, `gitea`, `gitlab`, `jira`, `linear`, or `beads` |
| `tracker_config.owner` | *(prompted)* | Repository owner (GitHub/Gitea/GitLab) |
| `tracker_config.repo` | *(prompted)* | Repository name (GitHub/Gitea/GitLab) |
| `tracker_config.project_key` | *(prompted)* | Jira project key |
| `tracker_config.team_id` | *(prompted)* | Linear team ID |
| `projects.default_mode` | `"per-epic"` | Project grouping: `"per-epic"` or `"single"` |
| `projects.project_ids` | `{}` | Cached project IDs keyed by spec number (e.g., `{"SPEC-0007": "PVT_kwDOABC"}`) |
| `projects.views` | `["All Work", "Board", "Roadmap"]` | Named views for GitHub Projects V2 |
| `projects.columns` | `["Todo", "In Progress", "In Review", "Done"]` | Board columns for Gitea projects |
| `projects.iteration_weeks` | `2` | Sprint duration in weeks for GitHub iteration fields |
| `branches.enabled` | `true` | Whether to add `### Branch` sections to issue bodies |
| `branches.prefix` | `null` (uses `"feature"`) | Default branch prefix for task issues |
| `branches.epic_prefix` | `"epic"` | Branch prefix for epic issues |
| `branches.slug_max_length` | `50` | Maximum slug length in branch names |
| `pr_conventions.enabled` | `true` | Whether to add `### PR Convention` sections to issue bodies |
| `pr_conventions.close_keyword` | `null` (tracker default) | Custom close keyword (e.g., `"Fixes"` instead of `"Closes"`) |
| `pr_conventions.ref_keyword` | `"Part of"` | Keyword for referencing parent epic |
| `pr_conventions.include_spec_reference` | `true` | Include spec number in PR convention section |
| `worktrees.base_dir` | `null` (uses `.claude/worktrees/`) | Where worktrees are created |
| `worktrees.max_agents` | `3` | Default number of parallel worker agents |
| `worktrees.auto_cleanup` | `false` | Remove worktrees after successful PR creation |
| `worktrees.pr_mode` | `"ready"` | `"ready"` for regular PRs, `"draft"` for draft PRs |
| `review.max_pairs` | `2` | Default number of reviewer-responder pairs |
| `review.merge_strategy` | `"squash"` | Merge strategy: `"squash"`, `"merge"`, or `"rebase"` |
| `review.auto_cleanup` | `false` | Remove worktrees after review completion |

## Development

Clone the repo and run Claude Code from the project directory:

```bash
git clone https://github.com/joestump/claude-plugin-design.git
cd claude-plugin-design
claude
```

The `.claude/settings.json` in this repo registers the local directory as a marketplace and enables the plugin automatically. Any changes to skills or templates are picked up on the next Claude Code launch.

## What It Does

### `/pmo:adr` -- Architecture Decision Records

Creates ADRs using [MADR](https://adr.github.io/madr/) format:
- Sequential numbering: `ADR-0001`, `ADR-0002`, etc.
- Stored in `docs/adr/`
- Mermaid architecture diagrams included by default
- YAML frontmatter with status, date, decision-makers
- Single-agent by default; add `--review` for team-based drafting with architect review
- Offers to add an Architecture Context section to your CLAUDE.md on first use
- After writing, suggests formalizing the decision into a spec with `/pmo:spec`

### `/pmo:spec` -- Specifications

Creates paired spec.md + design.md using [OpenSpec](https://github.com/Fission-AI/OpenSpec):
- Spec numbering: `SPEC-0001`, `SPEC-0002`, etc.
- Requirements in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) format (MUST, SHALL, MAY, etc.)
- Scenarios with `####` headings and WHEN/THEN format
- Mermaid architecture diagrams required in design.md
- Stored in `docs/openspec/specs/{capability-name}/`
- Single-agent by default; add `--review` for team-based drafting with architect review
- After writing the spec, suggests running `/pmo:plan SPEC-XXXX` to break requirements into trackable issues

### `/pmo:plan` -- Sprint Planning

Breaks an existing specification into trackable work items in your issue tracker:
- Accepts a spec name or SPEC number (e.g., `/pmo:plan web-dashboard` or `/pmo:plan SPEC-0003`)
- Lists available specs interactively if no argument provided
- Detects available issue trackers:
  - [Beads](https://github.com/steveyegge/beads), GitHub (MCP or `gh` CLI), GitLab (MCP or `glab` CLI), Gitea (MCP or `tea` CLI), Jira (MCP), Linear (MCP)
  - Saves tracker preference to `.claude-plugin-design.json` so you're not re-prompted
- Groups requirements into 3-4 story-sized issues by functional area (targeting 200-500 line PRs) with task checklists for each requirement
- Creates an epic for the spec and stories as children with acceptance criteria referencing spec/requirement numbers
- Sets up dependency relationships between stories
- Project grouping: creates tracker-native projects for each epic (or a single combined project with `--project`). Projects are automatically linked to the repository so they appear in the repo's Projects tab. Skip with `--no-projects`.
- Workspace enrichment: GitHub Projects get descriptions, READMEs, Sprint iteration fields, and named views; Gitea gets milestones and board columns
- Branch naming: adds `### Branch` sections to issue bodies with `feature/{issue-number}-{slug}` naming convention. Customize prefix with `--branch-prefix`, skip with `--no-branches`.
- PR conventions: adds `### PR Convention` sections with tracker-specific close keywords (e.g., `Closes #N` for GitHub)
- Auto-creates labels with try-then-create pattern when missing
- Falls back to generating `tasks.md` when no tracker is available (per ADR-0007)
- Single-agent by default; add `--review` for team-based planning with reviewer

### `/pmo:organize` -- Organize and Enrich Project Workspaces

Retroactively organizes issues and enriches project workspaces with a three-tier intervention model:
- **Tier (a) Leave as-is**: Assess project state and report — no changes made
- **Tier (b) Restructure workspace**: Add/fix project structure (views, README, columns, iterations, milestones) without touching issues
- **Tier (c) Complete refactor**: All tier (b) changes plus re-group issues, fix labels, create dependency links, add branch/PR sections
- GitHub enrichment: project description, README, Sprint iteration field, named views (All Work, Board, Roadmap)
- Gitea enrichment: milestones for epics, board columns (Todo/In Progress/In Review/Done), native dependency links
- Auto-creates labels with try-then-create pattern when missing (epic=#6E40C9, story=#1D76DB, spec=#0E8A16)
- Graceful degradation: skips unsupported features and reports, never fails
- Use `--dry-run` to preview without modifying
- No `--review` support (utility skill)

### `/pmo:enrich` -- Enrich Issues with Workflow Conventions

Retroactively adds branch naming and PR convention sections to existing issue bodies:
- Finds issues referencing a spec in your tracker
- Appends `### Branch` sections with `feature/{issue-number}-{slug}` naming
- Appends `### PR Convention` sections with tracker-specific close keywords
- Skips issues that already have these sections (idempotent)
- Use `--dry-run` to preview without modifying
- Custom branch prefix via `--branch-prefix`
- No `--review` support (utility skill)

### `/pmo:work` -- Parallel Issue Implementation

Picks up tracker issues and implements them in parallel using git worktrees:
- **No spec required**: run `/pmo:work` with no arguments to analyze the backlog, get a proposed batch of issues (biased toward unblocking dependencies and feature work), and approve before starting
- Accepts a spec number (`SPEC-0003`) to work all open issues for that spec, or specific issue numbers (`42 43 47`)
- Reads spec.md, design.md, and referenced ADRs to give workers full architecture context when a spec is available; workers rely on issue body and codebase context alone when there is no spec
- Detects tracker using the same pattern as `/pmo:plan` (`.claude-plugin-design.json` preference, then auto-detection)
- Filters issues: skips epics and issues without `### Branch` sections (suggests `/pmo:enrich`)
- Extracts branch names and PR conventions from issue bodies
- Creates isolated git worktrees for each issue with deterministic branch names
- Spawns parallel worker agents (default 3, configurable with `--max-agents`)
- Workers implement changes, leave `// Governing: SPEC-XXXX REQ "..."` comments when spec context is available, run tests, commit, push, and create PRs
- Workers assess PR size before opening: comments-only or trivially small changes (<30 lines) are bundled with additional queued issues rather than opened as standalone PRs; the lead assigns more work to the same worktree until the PR is meaningful
- Regular (non-draft) PRs by default; use `--draft` for draft PRs
- `--dry-run` previews what would happen without doing anything
- `--no-tests` skips test execution in workers
- Failed issues preserve their worktrees for manual pickup
- Falls back to single-agent sequential mode if team creation fails
- Configurable via `.claude-plugin-design.json` `worktrees` section (base_dir, max_agents, auto_cleanup, pr_mode)

### `/pmo:review` -- PR Review and Merge

Reviews and merges PRs produced by `/pmo:work` using reviewer-responder agent pairs:
- Discovers open PRs by spec number or explicit PR numbers
- Organizes agents into reviewer-responder pairs (default 2 pairs, configurable with `--pairs`)
- Verifies all CI/CD status checks (GitHub Actions, Gitea Actions, GitLab CI) are green before reviewing — PRs with failing checks are skipped
- Reviewers check diffs against spec acceptance criteria and ADR compliance (not just style)
- Responders address feedback by pushing fix commits and replying to review comments
- Re-verifies CI after responder pushes fixes — never merges with failing checks
- Exactly one review-response round per PR to bound compute
- Approved PRs are merged automatically (squash by default); use `--no-merge` to skip
- Reuses existing worktrees from `/pmo:work` when available
- Adaptive pair count: reduces to 1 pair for small batches
- `--dry-run` previews which PRs would be reviewed without taking action
- Configurable via `.claude-plugin-design.json` `review` section (max_pairs, merge_strategy, auto_cleanup)
- Falls back to single-agent sequential mode if team creation fails

### `/pmo:init` -- Initialize Design Plugin

Sets up your project's `CLAUDE.md` with architecture context:
- Creates `CLAUDE.md` if it doesn't exist, or updates the existing one
- Adds an `## Architecture Context` section with references to `docs/adr/` and `docs/openspec/specs/`
- Includes a skills reference table and a note about `/pmo:prime`
- Idempotent -- safe to re-run without duplicating content

### `/pmo:prime` -- Prime Architecture Context

Loads existing ADRs and specs into the session for architecture-aware responses:
- Summarizes all ADRs (title, status, key decision) and specs (title, status, requirement counts)
- Optional topic argument for semantic filtering (e.g., `/pmo:prime security` surfaces auth, encryption, access control decisions)
- Suggests `/pmo:init` if CLAUDE.md hasn't been set up yet
- Read-only -- never modifies any files

### `/pmo:check` -- Quick Drift Check

Fast, focused drift check on a specific target:
- Target can be a file path, directory, `ADR-XXXX`, or `SPEC-XXXX`
- Checks 3 drift categories: code vs. spec, code vs. ADR, ADR vs. spec
- Produces a concise findings table with severity levels (critical, warning, info)
- Always single-agent (no `--review` support)
- Suggests `/pmo:audit` for deeper analysis when warranted

### `/pmo:audit` -- Comprehensive Design Audit

Deep audit of design artifact alignment across the project:
- Covers all 6 drift categories: code vs. spec, code vs. ADR, ADR vs. spec, coverage gaps, stale artifacts, policy violations
- Produces a structured report with categorized findings and summary matrix
- Prioritized recommended actions ordered by severity
- Single-agent by default; add `--review` for team-based auditing with auditor and reviewer agents

### `/pmo:discover` -- Codebase Discovery

Reverse-engineers implicit architectural decisions and spec-worthy subsystems from an existing codebase:
- Analyzes dependencies, architectural patterns, project structure, and infrastructure configuration
- Uses parallel exploration agents for fast analysis of large codebases
- Produces a suggestion report with confidence levels (High/Medium/Low) and evidence citations
- Includes ready-to-use `/pmo:adr` and `/pmo:spec` commands for each suggestion
- Reads existing ADRs and specs to avoid suggesting duplicates
- Optional scope argument to limit analysis to a subdirectory or domain
- Read-only -- never creates files; you choose what to formalize

### `/pmo:docs` -- Docusaurus Documentation Site

Transforms your ADRs and specs into a polished doc site with two modes:

**Scaffold mode** (default when no existing site): Creates a standalone `docs-site/` with its own Docusaurus installation.

**Integration mode** (when an existing Docusaurus site is detected): Generates a `sync-design-docs` build-time plugin into the existing site's `plugins/` directory, copies React components and CSS, and registers everything automatically. The plugin runs the same transforms at build time and watches for source changes during development.

**Upgrade lifecycle**: Re-running `/pmo:docs` on an already-configured project triggers a safe upgrade flow:
- A `.design-docs.json` manifest tracks plugin version, mode, site directory, and SHA-256 checksums of all managed files
- Unchanged files are updated silently to the latest template version
- Modified files prompt you with a diff and three choices: accept new version, keep yours, or opt out of future upgrades for that file
- Missing files are re-created from templates
- Files marked `managed: false` are permanently skipped

Features (both modes):
- RFC 2119 keyword highlighting (color-coded MUST/SHALL/MAY)
- Cross-reference linking (ADR-0001 and SPEC-NNN become clickable links)
- Mermaid diagram rendering
- Status/Date/Domain badge components
- Requirement box components with anchor links
- Consequence keyword highlighting (Good/Bad/Neutral)
- Dark mode support
- Auto-generated sidebars
- Separate spec/design pages with expandable sidebar categories
- Specs overview index with linked table of all specifications

### `/pmo:list` -- List Decisions and Specs

Lists all ADRs and specs with their status, date, and title. Filter by type with `adr`, `spec`, or `all`.

### `/pmo:status` -- Update Status

Changes the status of an ADR or spec. Valid statuses:
- **ADR**: proposed, accepted, deprecated, superseded
- **Spec**: draft, review, approved, implemented, deprecated

## Project Structure

### Scaffold mode (new docs site)

```
your-project/
├── .design-docs.json            # Upgrade manifest (version, checksums)
├── docs/
│   ├── adrs/                    # ADRs (created by /pmo:adr)
│   │   ├── ADR-0001-short-title.md
│   │   └── ADR-0002-short-title.md
│   └── openspec/specs/          # Specs (created by /pmo:spec)
│       └── capability-name/
│           ├── spec.md
│           └── design.md
├── docs-site/                   # Docusaurus site (created by /pmo:docs)
│   ├── package.json
│   ├── docusaurus.config.ts
│   ├── scripts/                 # Build-time transforms
│   └── src/                     # Components, CSS, data
└── docs-generated/              # Build artifact (generated by docs-site build)
    ├── index.mdx
    ├── decisions/               # Transformed ADRs
    └── specs/                   # Transformed specs
        ├── index.mdx            # Overview table with links
        ├── capability-name/     # Expandable sidebar category
        │   ├── _category_.json
        │   ├── spec.mdx
        │   └── design.mdx
        └── single-doc-spec.mdx  # Leaf item (no design.md)
```

### Integration mode (existing Docusaurus site)

```
your-project/
├── .design-docs.json            # Upgrade manifest (version, checksums)
├── docs/
│   ├── adrs/                    # ADRs (canonical source)
│   └── openspec/specs/          # Specs (canonical source)
└── website/                     # Your existing Docusaurus site
    ├── docusaurus.config.ts     # Plugin registered here
    ├── plugins/
    │   └── sync-design-docs/    # Generated by /pmo:docs
    │       ├── index.js         # Docusaurus plugin entry
    │       └── lib/             # Transform scripts
    ├── src/
    │   ├── components/
    │   │   └── design-docs/     # Badge and layout components
    │   ├── css/
    │   │   └── design-docs.css  # Design-specific styles
    │   └── theme/
    │       └── MDXComponents.tsx # Component registration (merged)
    └── docs/
        └── architecture/        # Generated at build time (gitignored)
            ├── index.mdx
            ├── decisions/       # Transformed ADRs
            └── specs/           # Transformed specs
                ├── index.mdx    # Overview table with links
                └── ...          # Same structure as scaffold
```

## Workflow

1. **Setup**: `/pmo:init` to configure CLAUDE.md with architecture context
2. **Discover**: `/pmo:discover` to find implicit decisions in an existing codebase
3. **Prime**: `/pmo:prime` at the start of each session (or `/pmo:prime security` for a focused topic)
4. **Decide**: `/pmo:adr We need to choose a web framework for the admin dashboard`
5. **Review**: `/pmo:list adr` to see all decisions, `/pmo:status ADR-0001 accepted` to approve
6. **Specify**: `/pmo:spec Convert ADR-0001 to a spec` — the agent writes requirements and offers to plan a sprint
7. **Plan**: `/pmo:plan SPEC-0001` — break the spec into epics, tasks, and sub-tasks in Beads, GitHub, GitLab, Gitea, Jira, or Linear with acceptance criteria referencing spec/requirement numbers
8. **Organize & Enrich** (retroactive): `/pmo:organize SPEC-0001` to group issues into projects, `/pmo:enrich SPEC-0001` to add branch and PR conventions
9. **Build**: `/pmo:work SPEC-0001` (spec-scoped) or `/pmo:work` (propose from backlog) to implement issues in parallel using git worktrees, or `/pmo:prime` then manually work through issues
10. **Review**: `/pmo:review SPEC-0001` to review and merge PRs with spec-aware feedback, or `--no-merge` for review-only
11. **Check**: `/pmo:check src/auth/` to quick-check for drift while coding
12. **Audit**: `/pmo:audit --review` for a comprehensive design review
13. **Document**: `/pmo:docs` to generate or upgrade the docs site

For thorough team review on critical decisions, add `--review`:
- `/pmo:adr Choose a database --review`
- `/pmo:spec authentication-service --review`
- `/pmo:audit --review`

## CLAUDE.md Integration

Run `/pmo:init` to set up your project's CLAUDE.md with architecture context. This adds references to `docs/adr/` and `docs/openspec/specs/`, a plugin skills table, and a note about `/pmo:prime`:

```markdown
## Architecture Context
- Architecture Decision Records are in `docs/adr/`
- Specifications are in `docs/openspec/specs/`
```

## License

MIT
