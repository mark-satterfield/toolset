# Categories

A taxonomy of things that have known directory or naming conventions.
This file is a reminder of what categories exist — not the conventions themselves.
When you encounter something from a category, fetch current standards if your knowledge
is uncertain, version-specific, or the domain is outside typical software development.

---

## Code projects — by architecture pattern

- Layered / Technical-Slice (controllers, services, repositories, models)
- Feature-Based / Vertical-Slice (co-located by business capability)
- Domain-Driven / Hexagonal / Clean Architecture
- Package-by-Module (library or SDK centered on public API)
- CLI / Tooling (entry points, commands, internal logic, helpers)
- Conventional Web App (src, public, tests, config, scripts)

## Code projects — by language or framework

**Languages:** Python, JavaScript, TypeScript, Java, Go, Rust, Ruby, PHP, C#/.NET,
Kotlin/Android, Swift/Xcode, C/C++, Elixir/Phoenix, Dart/Flutter, Scala

**Frameworks:** Next.js (App Router vs Pages Router), React, Angular, Vue, Nuxt,
Django, FastAPI, Flask, Rails, Spring Boot, Laravel, ASP.NET, Phoenix

**Build tools with mandated layouts:** Maven, Gradle, Cargo, CMake, Bazel, Mix

## Deployment and infrastructure

- Terraform (modules, environments, live, stacks)
- AWS CDK / Pulumi / Bicep (lib, bin, constructs, stacks, functions)
- Kubernetes / GitOps (base, overlays, charts, clusters, apps)
- Helm (Chart.yaml, values.yaml, templates, charts, crds)
- Kustomize (base, overlays, kustomization.yaml)
- Docker Compose project layout
- Serverless Framework

## Repository and tooling conventions

- GitHub repo root (.github, workflows, issue templates, CODEOWNERS)
- GitHub Actions workflow layout
- GitLab CI layout
- Dev Container (.devcontainer)
- Pre-commit hook layout (.pre-commit-config.yaml)
- Monorepo tooling (Turborepo, Nx, Lerna, pnpm workspaces, uv workspaces)
- Service-Per-Repo / Polyrepo governance

## Documentation systems

- MkDocs (mkdocs.yml, docs/, material theme conventions)
- Sphinx (conf.py, index.rst, _static, _templates, MyST-Parser)
- Docusaurus
- ADR collections (Architecture Decision Records — status frontmatter, naming patterns)
- RFC collections
- Runbook collections
- Architecture documentation (arc42, C4 model docs)
- Docs-as-product (docs/architecture, docs/standards, docs/runbooks as governed artifacts)

## Business and operational file systems

- Department-Based (Finance, HR, Legal, Marketing, Sales)
- Project-Based (initiatives, clients, engagements)
- Client / Customer / Matter-Based (contracts, comms, deliverables, billing)
- Time-Based / Chronological (year/quarter/month archives)
- Document-Type Based (Contracts, Invoices, Policies, Templates)
- Process / Workflow-Based (Intake, In Progress, Review, Approved, Published)
- Product / Service-Based (organized by offering or capability)
- Audience-Based (Internal, Customers, Partners, Executives, Board)
- Knowledge-Base / Topic-Based (Benefits, Security, Architecture, Onboarding)
- Location-Based (regions, offices, sites, facilities)

## Compliance and records management

- Record-Retention / Compliance-Based (retention codes, legal holds, active vs archived)
- Records Series Layout (classification codes, date-based rules, retention buckets)
- Case / Matter-Based (legal, compliance, investigations, support)
- SharePoint Document Library Convention (content types, metadata columns, naming rules)
- Controlled document systems (ISO, SOC 2, HIPAA, FedRAMP governed artifacts)

## Naming systems beyond code conventions

- Retention codes and classification schemes
- Matter / case identifiers (legal, compliance)
- Date-prefixed records (ISO 8601: YYYY-MM-DD)
- Version-prefixed artifacts (v1_, v2_, semantic versioning in filenames)
- Locale / language suffixes (_en, _fr, _es)
- Environment suffixes (.dev, .staging, .prod)
- Sequential identifiers (ADR-001, RFC-0042, INC-2024-003)
