# New Agent Analysis
_Generated 2026-04-28. Updated with confirmed platform surfaces, guardrail corrections, and product scope clarifications._

## Product Context (Informs All Recommendations)
SkillSpoke is an AI-powered job-readiness platform using realistic fake job listings. Core product features include candidate-job matching, recommendations, trend detection, and structured feedback — all generating behavioral data that feeds ML pipelines. The agent workforce must support all four confirmed surfaces: web desktop, web mobile, iOS (Swift/SwiftUI), and Android (architecture team decision pending on Kotlin vs React Native).

## Guardrail Priority Order
1. AWS backend — no GCP, no Azure
2. Serverless first, AWS native first, AWS services first
3. AWS-managed 3rd-party services second
4. EDA and microservices
5. Prefer AWS AI architecture
6. Choose right over quick or easy; build for long-term
7. Containers/EC2/ECS/EKS are **secondary-path** capabilities (not excluded) — present when serverless constraints are hit or model self-hosting is required

## Methodology
Eight parallel reader agents read every file's actual content. This report synthesizes all findings into a complete union inventory of the agent workforce and a recommended final agent list.

**Sources:**
- `plugins/agent-teams-workforce/agents/` — 74 existing agents (ss-* workers + polyrepo-cartographer)
- `to_review/agents/` — 7 senior-* general-purpose agents
- `to_review/commands/` — 7 slash command wrappers

## Critical Structural Finding (Applies to All 74 ss-* Agents)

Every ss-* agent file follows an **identical 5-step workflow template** with the same STATUS: DONE | BLOCKED output format. The files are clean but thin — they wrap the CSV roster in a standard shell without adding any SkillSpoke domain knowledge. What the files **do** add beyond the CSV:
- `color` field in frontmatter (UI aesthetic only)
- Explicit BLOCKED escalation mechanic and output schema
- "No delegation expected" statement for workers

What the files **do not** add:
- No SkillSpoke domain context (no stack details, no repo references, no ADR content)
- No example inputs or outputs
- No agent-specific decision logic or heuristics
- No templates (no ADR template, no DoD checklist, no BDD template)
- No failure mode handling beyond generic BLOCKED status

Every "strengthen" recommendation below means: add domain context, not change behavior.

---

## Part 1: Existing Agent Inventory (ss-* agents)

### Keep As-Is (Well-Scoped, Correct Tool List, No Critical Gaps)

| Agent | Role type | Model | What it actually does | Overlap notes |
|-------|-----------|-------|----------------------|---------------|
| `ss-acceptance-criteria-specialist` | worker | sonnet | Writes Given/When/Then acceptance criteria from user stories; updates beads via `bd update`; hard no-scope-expansion rule | Upstream: ss-user-story-writer; downstream: ss-tdd-test-generator |
| `ss-api-doc-writer` | worker | sonnet | Generates human-readable API docs from OpenAPI specs using redoc-cli; produces Markdown + SDK snippets | Clean; no overlaps |
| `ss-api-gateway-developer` | worker | sonnet | Implements API Gateway REST v1 CDK constructs, Lambda proxy, custom authorizers; validates via `cdk synth`; prohibits HTTP API v2 | Tightly coupled with ss-lambda-developer |
| `ss-architecture-lead` | team-lead | opus | Routes architecture tasks; validates ADR format + spec readiness; blocks upstream-to-development pipeline; delegates to 7 workers | Clean team-lead pattern |
| `ss-beads-coordinator` | coordinator | sonnet | Owns full beads issue lifecycle (create/claim/close/track); Bash-only (`bd` commands); dependency-aware sprint sequencing | Bash-only is intentional and correct |
| `ss-cdk-developer` | worker | sonnet | Writes AWS CDK infrastructure in Python; validates via `cdk synth` + `ruff`; cannot deploy | Clean CDK specialization |
| `ss-changelog-writer` | worker | haiku | Generates CHANGELOG entries from git log; Conventional Commits + semver; haiku model (mechanical task) | Minimal and well-scoped |
| `ss-cicd-specialist` | worker | sonnet | Designs GitHub Actions workflows; OIDC auth, caching, Lambda deployment pipelines; validates via `act --dry-run`; no secrets in workflow files | OIDC specialization is SkillSpoke-correct |
| `ss-claude-md-maintainer` | worker | sonnet | Audits and updates CLAUDE.md files across all repos; evaluates agent instruction quality | Strengthen with CLAUDE.md standard |
| `ss-code-quality-lead` | team-lead | sonnet | Routes quality issues; delegates to 7 workers; cannot run tools itself (No Bash) | Clean team-lead pattern |
| `ss-code-reviewer` | expert/advisory | opus | Reviews PRs; uses git diff + difftastic (semantic diff); CDK patterns in scope alongside Python; read-only | difftastic is a differentiating capability |
| `ss-codebase-explorer` | advisory | sonnet | Maps code via GitNexus (`gitnexus query/context`); semantic code search; execution flow tracing; read-only | Complement to ss-impact-analyst |
| `ss-content-writer` | worker | sonnet | Landing pages, blog posts, launch copy, feature docs; partners with ss-persona-analyst for audience-aware copy | Clean scope; no tech stack dependency |
| `ss-coverage-analyst` | advisory | haiku | Runs `pytest --cov`; produces risk-weighted gap list; hands back to ss-qa-lead | Haiku model correct for mechanical analysis |
| `ss-deep-researcher` | worker/expert | opus | Web/GitHub research with cited sources; WebFetch + WebSearch + `gh CLI` read-only; can write research reports only | Opus justified for research quality |
| `ss-dependency-auditor` | advisory | haiku | pip-audit + npm audit + safety; CVE scoring + severity; dual Python/Node ecosystem coverage | Haiku correct for scanning task |
| `ss-deployment-coordinator` | coordinator | opus | Sequences wave-based deployments; validates pre-conditions; runs smoke tests; no cdk deploy or production promotion without human approval | Approval gate mechanic is critical safety control |
| `ss-development-lead` | team-lead | sonnet | Routes development tasks; enforces hard constraints before any file is written; delegates to 10 workers; no write/bash | Dependency ordering and parallel delegation are explicit specializations |
| `ss-devops-lead` | team-lead | sonnet | Coordinates CI/CD + deployment + infrastructure workers; DevSecOps specialization; no deploy authority | Clean team-lead pattern |
| `ss-docs-lead` | team-lead | haiku | Routes documentation work; ensures docs updated when code ships; delegates to 8 workers | Haiku may struggle with cross-artifact consistency at scale — watch for upgrade need |
| `ss-dynamodb-developer` | worker | sonnet | Implements DynamoDB access patterns via boto3; conditional writes; single-table; validates with pytest | Strictly downstream of ss-dynamodb-schema-designer |
| `ss-e2e-test-writer` | worker | sonnet | Playwright E2E tests in TypeScript; page object model; smoke tests; validates via `npx playwright test` | TypeScript aligns with SkillSpoke Next.js frontend |
| `ss-event-schema-designer` | worker | sonnet | Designs domain event envelope schemas; produces AsyncAPI + JSON Schema; uses `yq` for schema manipulation | Fills specific gap no other agent covers |
| `ss-frontend-developer` | worker | sonnet | React/Next.js UI components; TypeScript + Tailwind; validates via `npm run build` + lint; partners with ss-ai-llm-expert for LLM-aware UI | Clean; no overlaps |
| `ss-iam-auditor` | advisory | sonnet | Audits IAM policies via `cdk synth` + `yq`; least-privilege violations; produces IAM audit report | Clear separation from ss-security-auditor |
| `ss-impact-analyst` | advisory | opus | Assesses blast radius before any symbol change via `gitnexus impact` + `detect_changes`; pre-change safety gate for any agent | Opus justified for high-stakes pre-change analysis |
| `ss-infrastructure-auditor` | advisory | sonnet | Detects CDK stack drift via `cdk diff` + read-only AWS CLI; no cdk deploy; produces drift report | Clean separation from ss-iam-auditor |
| `ss-infrastructure-designer` | worker/expert | sonnet | Designs CDK stack architecture + infrastructure patterns; produces design docs (not code); bridges architect → CDK developer | Design-only vs implementation-only boundary enforces review-before-build |
| `ss-integration-test-writer` | worker | sonnet | Writes integration tests against real infrastructure; LocalStack + DynamoDB Local; pytest fixtures; Docker via Bash | LocalStack/DynamoDB Local specialization is SkillSpoke-correct |
| `ss-ios-developer` | worker/expert | sonnet | SwiftUI, StoreKit (subscriptions/in-app purchases), App Store compliance; validates via xcodebuild; partners with ss-ai-llm-expert | Confirmed Swift/SwiftUI; Liquid Glass requires SwiftUI |
| `ss-iteration-supervisor` | coordinator | sonnet | Manages adversarial review loops: worker → ss-adversarial-reviewer → ss-adjudicator → worker until adjudicator passes; escalation on loop limit | Unique loop management pattern not found elsewhere |
| `ss-lambda-developer` | worker | sonnet | Python Lambda handlers with aws-lambda-powertools; validates via ruff + mypy + pytest triple gate; no deploy | Core worker for SkillSpoke Python Lambda backend |
| `ss-librarian` | coordinator | sonnet | Session archive, searchable project history via `bd memories` + `bd remember`; knowledge infrastructure agent | Only functions in Beads-enabled projects |
| `ss-linter-enforcer` | worker | haiku | Runs ruff/shellcheck/eslint/yamllint; auto-fixes in-place; haiku model (mechanical linting) | Covers all four language linters for SkillSpoke's mixed stack |
| `ss-master-orchestrator` | orchestrator | opus | Single entry point for entire SDLC; receives from human; delegates to all team leads; never writes | No-write restriction is the key governance mechanism; opus justified |
| `ss-migration-specialist` | worker/expert | opus | DynamoDB schema evolution; Python runtime upgrades; zero-downtime migration patterns; no deploy without approval | Opus for high-stakes migration work; approval gate is correct |
| `ss-monitoring-specialist` | worker | sonnet | CloudWatch dashboards + alarms + X-Ray tracing as CDK constructs; structured logging; no direct console changes | CDK-only constraint enforces infrastructure-as-code discipline |
| `ss-okr-writer` | worker | sonnet | Derives OKRs from strategy docs; leading vs lagging indicator distinction; produces OKR documents | Clean; no overlaps |
| `ss-openapi-spec-writer` | worker | sonnet | Writes OpenAPI 3.x YAML before any handler code exists (spec-first); validates via yamllint + spectral | Spec-first mandate is critical discipline |
| `ss-patrol-agent` | coordinator | haiku | Polls `bd mol ready --gated`; dispatches resume signals to blocked agents; continuous background monitor | Only agent designed for continuous/background operation; haiku correct |
| `ss-performance-optimizer` | worker/expert | sonnet | Profiles Lambda cold start + DynamoDB cost + Next.js bundle; uses hyperfine; no production file writes | Lambda/DynamoDB/bundle triple covers SkillSpoke's three performance-sensitive components |
| `ss-persona-analyst` | worker | sonnet | Data-driven user personas; JTBD framework; mines codebase via Glob/Grep as persona data source | Codebase-as-research-signal is a sophisticated capability |
| `ss-prd-writer` | worker | sonnet | Full PRDs from feature briefs; Glob/Grep codebase for context; hands off to ss-user-story-writer | Clean product skill |
| `ss-qa-lead` | team-lead | sonnet | Test strategy selection; test pyramid enforcement; coverage gate decisions (pass/fail); delegates to 6 workers | Coverage gate management is an explicit function |
| `ss-readme-writer` | worker | sonnet | README files for repos/directories; setup instructions, onboarding flows | Lightweight toolset correct for docs-only work |
| `ss-refactoring-specialist` | worker | sonnet | Structural code refactoring via ast-grep + comby + difftastic + pytest; behavior-preserving constraint | AST-aware toolchain makes this substantially more capable than a generic editor |
| `ss-repository-manager` | coordinator/expert | sonnet | Cross-repo hygiene via read-only git + `gh CLI`; branch status, PR state, repo health reports; no push/merge | Complement to polyrepo-cartographer (live git vs manifest) |
| `ss-requirements-lead` | team-lead | opus | Routes + sequences requirements-phase work; 7-agent fan-out; requirements completeness gate before architecture | Largest delegation fan-out in the roster |
| `ss-runbook-writer` | worker | sonnet | Operational runbooks; incident response; disaster recovery; partners with ss-devops-lead + ss-monitoring-specialist | MonitoringSpecialist partnership grounds runbooks in real CloudWatch alarm context |
| `ss-secret-scanner` | advisory | haiku | Scans for accidentally committed secrets via gitleaks + trufflehog; Bash-only; haiku (mechanical scanning) | Minimal footprint; correct cost optimization |
| `ss-security-architect` | worker/expert | opus | Designs IAM policies, security controls, threat models; OWASP threat modeling applied to Lambda/API Gateway/DynamoDB; can be invoked from two leads | Design-vs-audit separation from auditors |
| `ss-security-auditor` | expert/advisory | sonnet | bandit (Python) + gitleaks (secrets) + semgrep (SAST); RLS misconfiguration in specializations (implies PostgreSQL or Supabase component) | RLS specialization worth investigating — may indicate unreported stack component |
| `ss-security-lead` | team-lead | opus | Security posture across all SDLC phases; PR-blocking authority; delegates to 4 workers | PR-blocking authority gives governance power to halt releases |
| `ss-sprint-health-analyst` | advisory | haiku | Beads velocity, cycle time, blocked-rate via `bd list/stats/stale`; WSJF velocity metric | Only functions in Beads-enabled projects |
| `ss-system-architect` | worker/expert | opus | Authors ADRs; ADR lifecycle management; trade-off analysis; microservice patterns | Opus for ADR authorship — ADRs are irreversible decisions |
| `ss-tdd-test-generator` | worker | sonnet | Writes failing unit tests before implementation (Red TDD phase); London School (mock-first); hands off TO ss-lambda-developer | Reversed handoff is the TDD enforcement mechanism |
| `ss-tech-debt-analyst` | advisory | sonnet | Tech debt inventory via scc + radon + pip-audit; creates Beads issues as output | Bridges analysis to actionable tracking |
| `ss-test-plan-writer` | worker | sonnet | Risk-based test plans; environment matrix; sits upstream of test code | Correct upstream position relative to ss-tdd-test-generator |
| `ss-user-story-writer` | worker | sonnet | Converts PRD sections to INVEST user stories; `bd create` integration (stories → Beads issues automatically) | `bd create` integration makes stories immediately trackable |
| `ss-wsjf-scorer` | expert/advisory | haiku | WSJF-ranked backlog via `bd list` + `bd update`; cannot create issues | `bd update` write-back makes output directly actionable |
| `polyrepo-cartographer` | advisory | inherit | Read-only polyrepo manifest specialist; answers structural questions from manifest; refuses to modify | Complement to ss-repository-manager |

### Strengthen (Agent Exists but Has Critical Gaps)

| Agent | Critical gap | What to add |
|-------|-------------|-------------|
| `ss-adjudicator` | Escalation criteria listed as specialization but never defined | Define: what constitutes a "valid" critique, how many loop iterations trigger escalation, who receives it |
| `ss-adr-doc-writer` | No ADR template or numbering convention defined | Add SkillSpoke ADR template (required sections, numbering like ADR-014); clarify author-vs-scribe distinction vs ss-system-architect |
| `ss-adversarial-reviewer` | No rubric format or findings structure defined | Specify: valid rubric input format, findings structure (severity + category), how assumption-challenging differs from bug-finding |
| `ss-ai-llm-expert` | Zero SkillSpoke-specific content despite Bedrock + FastMCP being core | Add Bedrock model IDs, FastMCP server patterns, SkillSpoke's specific LLM stack; add candidate-job embedding patterns using Bedrock Titan |
| `ss-api-contract-validator` | Tool overlap with ss-contract-test-writer (both use schemathesis) unexplained | Clarify: contract-validator = live validation against running API; contract-test-writer = writes test artifacts. Make explicit in both files. |
| `ss-architecture-guardian` | "Runs proactively" stated but no trigger mechanism defined | Define trigger: cron-style hook, session-start signal, or scheduled invocation pattern |
| `ss-aws-expert` | Zero SkillSpoke-specific content | Add approved service set, cost constraints, ADR-compliant patterns; include AppSync and OpenSearch as SkillSpoke-relevant services |
| `ss-bounded-context-mapper` | No context map output format defined | Define output: Mermaid diagram? Custom table with bounded contexts + integration patterns? |
| `ss-contract-test-writer` | Pact vs schemathesis distinction not defined; Pact broker dependency not addressed | Clarify when to use each; specify if SkillSpoke runs a Pact broker |
| `ss-dod-enforcer` | Definition of Done referenced but never defined | Embed the SkillSpoke DoD checklist; without it the agent has no enforcement criteria |
| `ss-dynamodb-schema-designer` | Output format not specified | Define: Markdown table? NoSQL Workbench export? Standardize the access pattern table format (entity, PK, SK, GSI1PK, GSI1SK) |

### Fix (Bug in Agent File)

| Agent | Bug |
|-------|-----|
| `ss-debugger` | Tool list has Read, Glob, Grep, Bash (pytest -k) but **no Write/Edit**. The deliverable explicitly includes a "bug fix" (code changes). Add Write + Edit to the tool list, or change the deliverable to "fix recommendation" only. |

### Merge Candidate (Substantially Overlapping Mandates)

| Agents | Overlap | Recommended resolution |
|--------|---------|----------------------|
| `ss-architecture-guardian` + `ss-compliance-auditor` | Both enforce ADR-014; both flag cross-service boundary violations; both file beads bugs; both run Read/Glob/Grep — near-identical mandates | Merge into one agent with two distinct modes: **guardian mode** = import-graph-level analysis (Python import violations, cross-module dependencies); **compliance mode** = infrastructure/config-level analysis (CloudFormation resources, S3 settings, CDK construct configurations). Retain the proactive trigger capability from guardian. |
| `ss-api-contract-validator` + `ss-contract-test-writer` | Both use schemathesis; both test API contract conformance | Do **not** merge — they serve different phases (validator = runtime validation, test-writer = artifact creation). Clarify the boundary; do not leave both files ambiguous. |

---

## Part 2: to_review Agents Inventory

**Universal blocker:** Every to_review agent references `plugins/billy-milligan/scripts/skill-gaps.sh` — a path that does not exist in this toolset. Every to_review command references `plugins/roles/<role>/agents/<file>.md` — paths that also do not exist. All adoption requires path surgery first.

| Agent | What it actually does | SkillSpoke gap it fills | Recommendation |
|-------|----------------------|------------------------|----------------|
| `senior-algorithms-engineer` | Algorithms with time/space complexity documentation; competitive programming techniques (segment trees, rerooting, CHT); distributed systems algorithms (consistent hashing, Raft); ML algorithm foundations; differential + property-based testing; confidence signaling | Algorithm complexity analysis absent from ss-roster; candidate-job matching algorithm design; DynamoDB access pattern complexity documentation | **retarget-for-ss**: Strip billy-milligan refs; scope to Python + TypeScript; emphasize bipartite matching, collaborative filtering, embedding similarity, DynamoDB query complexity; set model to `sonnet` or `opus` for complex algorithm design |
| `senior-aqa-engineer` | Testing trophy model; chaos engineering (Chaos Monkey, Gremlin, Toxiproxy); accessibility testing (playwright-axe, Lighthouse CI, Pa11y); visual regression (Percy, Chromatic, Applitools, BackstopJS); Pact consumer-driven contract testing; AI-assisted test generation; DORA metrics; Playwright MCP | Chaos engineering, visual regression, full Pact consumer-driven contracts, accessibility testing — none present in existing ss-* QA team | **extract-specialization**: Create `ss-chaos-engineer` containing chaos engineering (Lambda timeouts, DynamoDB throttling, API Gateway failures, AppSync subscription failures as chaos targets) + visual regression + accessibility test automation |
| `senior-architect` | MADR ADRs; C4 model; data architectures (Data Mesh, Lakehouse); ML/AI system architecture (feature stores, RAG pipelines, agentic systems with tool boundaries/observation/action loops); fitness functions as automated architectural tests; two-way/one-way door decision framework | Agentic systems architecture (tool boundaries, idempotent tool calls, circuit breakers) — directly applicable to SkillSpoke's agent workforce; fitness functions; reversibility framework; Data Mesh for SkillSpoke's analytics pipeline | **retarget-for-ss**: Strip multi-cloud/Kubernetes; add AWS CDK+Lambda+DynamoDB+AppSync context; keep agentic systems design section; add S3 data lake + Athena + Redshift Serverless for data architecture; deploy as `ss-solution-architect` |
| `senior-backend-developer` | Node.js/Go/Rust/Java/.NET/Ruby/Elixir ecosystems; AI/ML backends (prompt injection prevention, token budget management, vector DB integration, model fallback chains, LLM observability); event-driven (outbox pattern, exactly-once, schema registry, DLQ); OpenTelemetry observability | AI/ML backend patterns; event-driven outbox + exactly-once semantics; OpenTelemetry observability for Lambda — all absent from ss-lambda-developer | **extract-specialization**: Create `ss-backend-ai-specialist` from AI/ML backends + event-driven + OpenTelemetry sections; scope to Python Lambda + Next.js API routes only; strip Go/Rust/Java/Ruby/Elixir |
| `senior-database-engineer` | 230+ databases; deep DynamoDB (single-table, GSI/LSI, DAX, Streams CDC, Global Tables, PartiQL); vector databases (Pinecone, Weaviate, Milvus, Qdrant, ChromaDB, pgvector with HNSW/IVFFlat); Kafka deep expertise | Vector database selection + tuning for Bedrock RAG and candidate-job semantic matching; DynamoDB Global Tables + Streams CDC; Kafka/Kinesis streaming design — all absent from ss-roster | **extract-specialization**: Create `ss-vector-db-expert` from vector DB section (Pinecone, Qdrant, pgvector tuning for Bedrock RAG); keep DynamoDB note; adapt streaming section to Kinesis/EventBridge for SkillSpoke |
| `senior-devops-engineer` | IaC (Terraform, OpenTofu, Pulumi, CDK, Helm, Kustomize); GitOps (ArgoCD, Flux); SRE (SLI/SLO/error budget, toil reduction, PRRs, ORRs); FinOps (Infracost CI, CloudHealth, crawl/walk/run maturity); ML/AI infrastructure (GPU clusters, Ray/KubeFlow, Triton/vLLM) | SRE practices (SLO/error budget management adapted for CloudWatch); FinOps program (AWS cost attribution, Infracost in CI); Production Readiness Reviews — none present in ss-DevOps agents | **extract-specialization**: Create `ss-sre-specialist` from SRE + FinOps sections (CloudWatch-adapted); **retain** container/ECS/EKS/GPU knowledge from ML/AI infrastructure section (secondary-path for model self-hosting); strip Terraform/GitOps (ArgoCD/Flux) |
| `senior-mobile-developer` | React Native (New Architecture, Expo SDK 52+, EAS, Reanimated 3, MMKV, Skia); Flutter; KMP/KMM; on-device AI (Core ML, ML Kit, TFLite/LiteRT, ONNX, MediaPipe); fintech mobile (certificate pinning, Secure Enclave, PCI-DSS) | On-device AI inference (Core ML, TFLite for on-device ML features); React Native New Architecture; multi-platform mobile expertise beyond ss-ios-developer's current scope | **Resolved by confirmed surfaces**: iOS = Swift/SwiftUI (`ss-ios-developer` confirmed). Android platform decision pending. Keep both `ss-android-developer` (Kotlin) and `ss-rn-developer` (React Native) as candidate agents until architecture team decides. On-device AI section merges into `ss-ios-developer` regardless of Android path. |

---

## Part 3: to_review Commands Inventory

All 7 commands follow the same pattern: a slash command that loads an agent from a path that does not exist in this toolset. All share two blockers: broken path + wrong naming convention.

These represent a **valuable pattern** — user-invocable direct access to expert agents outside the orchestrated SDLC workflow. The ss-* workforce currently requires going through ss-master-orchestrator for everything; these commands provide on-demand expert access for ad-hoc queries.

| Command | SkillSpoke value | Action |
|---------|-----------------|--------|
| `senior-algorithms-engineer` | On-demand algorithm complexity advice; matching algorithm design | **retarget**: Fix path; rename to `ss:algorithms` |
| `senior-aqa-engineer` | On-demand chaos/accessibility/visual regression testing advice | **retarget**: Fix path; rename to `ss:chaos-testing` after agent extraction |
| `senior-architect` | On-demand broad architectural reasoning, agentic systems design, data architecture | **retarget**: Fix path to ss-solution-architect; rename to `ss:architect` |
| `senior-backend-developer` | On-demand Lambda backend + AI/ML backend + async API patterns | **retarget**: Fix path to ss-backend-ai-specialist; rename to `ss:lambda-backend` |
| `senior-database-engineer` | On-demand DynamoDB deep expertise + vector DB selection for RAG/matching | **retarget**: Fix path to ss-vector-db-expert; rename to `ss:database` |
| `senior-devops-engineer` | On-demand SRE/FinOps/CDK deployment advice; container secondary-path guidance | **retarget**: Fix path to ss-sre-specialist; rename to `ss:sre` |
| `senior-mobile-developer` | On-demand iOS (SwiftUI/StoreKit) + Android architecture + on-device AI advice | **retarget**: Fix path to ss-ios-developer or ss-android-developer; rename to `ss:mobile` |

---

## Part 4: New Agents to Create

| New Agent | What it should do | Source / Rationale |
|-----------|------------------|-------------------|
| `ss-appsync-developer` | Designs and implements AWS AppSync GraphQL APIs: schema definition, Lambda + DynamoDB resolvers, real-time subscriptions (WebSocket) for chat feature, authorization modes (Cognito/IAM/API key), CDK AppSync constructs, caching, subscription filtering | New gap: GraphQL + async chat requirement |
| `ss-android-developer` | Kotlin/Jetpack Compose Android development: Material You, coroutines, Room, Hilt, Google Play Billing, App Store deployment, Google Play compliance | Confirmed Android surface; activate if architecture team chooses native Kotlin path |
| `ss-rn-developer` | React Native (New Architecture, Expo SDK 52+, EAS Build/Submit, NativeWind v4, Reanimated 3, MMKV, Skia, Detox); SkillSpoke API client patterns; StoreKit + Google Play Billing integration; offline sync | Confirmed Android surface; activate if architecture team chooses React Native path |
| `ss-solution-architect` | Broader than ss-system-architect: agentic systems architecture (tool boundaries, idempotent tool calls, circuit breakers); SkillSpoke data mesh / S3 data lake + Athena + Redshift Serverless; fitness functions as automated architectural tests; two-way/one-way door reversibility framework | Retargeted from `senior-architect`; handles cross-cutting architectural decisions above CDK-level |
| `ss-chaos-engineer` | Lambda timeout + DynamoDB throttle + API Gateway failure + AppSync subscription failure chaos scenarios; Toxiproxy; LocalStack chaos injection; chaos game days; blameless postmortems; DORA metrics | Extracted from `senior-aqa-engineer` chaos engineering section |
| `ss-sre-specialist` | SLO/error budget management (adapted for CloudWatch SLO alarms); Production Readiness Reviews; FinOps program (Infracost in CI, AWS cost attribution, crawl/walk/run maturity); toil reduction; Operational Readiness Reviews | Extracted from `senior-devops-engineer` SRE + FinOps sections; container/GPU knowledge retained for model self-hosting |
| `ss-backend-ai-specialist` | AI/ML backend patterns (prompt injection prevention, token budget management, model fallback chains, LLM observability); event-driven (outbox pattern, exactly-once semantics, DLQ patterns); OpenTelemetry for Lambda; async streaming responses to AppSync/WebSocket | Extracted from `senior-backend-developer` AI/ML backends + event-driven + OpenTelemetry sections |
| `ss-vector-db-expert` | Vector database selection + tuning for Bedrock RAG and candidate-job semantic matching: pgvector, Pinecone, Qdrant (HNSW vs IVFFlat trade-offs); Amazon OpenSearch k-NN; Bedrock Knowledge Bases integration; embedding model selection; RAG pipeline debugging | Extracted from `senior-database-engineer` vector DB section |
| `ss-data-engineer` | AWS Glue (ETL jobs, crawlers, Data Catalog), Kinesis Data Streams (shard design, consumer Lambda), DynamoDB Streams CDC, EventBridge Pipes, S3 data lake (prefix design, partitioning, lifecycle), Athena (query optimization, partitioning), Redshift Serverless (data warehouse for SkillSpoke analytics) | Gap: SkillSpoke generates behavioral data for ML; Glue/Kinesis pipeline is the AWS-native path |
| `ss-ml-engineer` | Primary: Bedrock (fine-tuning, model evaluation, custom models), SageMaker (training jobs, feature store, model registry), Lambda inference (lightweight models); Secondary: ECS/EKS + GPU for self-hosted model scenarios (data residency, cost, latency constraints); candidate-job matching model development | Gap: core SkillSpoke product feature; self-hosted model path is secondary but must exist |
| `ss-matching-engineer` | Candidate-job matching system design and implementation: bipartite matching (Hungarian algorithm), collaborative filtering, content-based filtering, embedding-based similarity (Bedrock Titan cosine similarity), ranking model calibration, A/B testing match quality, AWS Personalize as managed option; match explanation generation | Gap: core SkillSpoke product feature; no existing agent covers matching/recommendation as a primary mandate |

---

## Recommended Final Agent List

### Tier 1: Keep As-Is (74 existing — core behavior correct)

**Command Team (1):** ss-master-orchestrator

**Product Team (7):** ss-requirements-lead, ss-prd-writer, ss-user-story-writer, ss-acceptance-criteria-specialist, ss-persona-analyst, ss-okr-writer, ss-wsjf-scorer

**Architecture Team (7):** ss-architecture-lead, ss-system-architect, ss-infrastructure-designer, ss-bounded-context-mapper, ss-openapi-spec-writer, ss-event-schema-designer, ss-dynamodb-schema-designer

**Engineering Team (10):** ss-development-lead, ss-lambda-developer, ss-cdk-developer, ss-api-gateway-developer, ss-dynamodb-developer, ss-frontend-developer, ss-ios-developer, ss-migration-specialist, ss-performance-optimizer, ss-refactoring-specialist

**QA Team (6):** ss-qa-lead, ss-tdd-test-generator, ss-integration-test-writer, ss-e2e-test-writer, ss-contract-test-writer, ss-coverage-analyst

**Code Quality Team (6):** ss-code-quality-lead, ss-code-reviewer, ss-linter-enforcer, ss-tech-debt-analyst, ss-dependency-auditor, ss-secret-scanner

**Documentation Team (7):** ss-docs-lead, ss-api-doc-writer, ss-adr-doc-writer, ss-runbook-writer, ss-changelog-writer, ss-claude-md-maintainer, ss-readme-writer

**DevOps Team (4):** ss-devops-lead, ss-cicd-specialist, ss-deployment-coordinator, ss-monitoring-specialist

**Security Team (4):** ss-security-lead, ss-security-architect, ss-security-auditor, ss-iam-auditor

**Intelligence Team (2):** ss-deep-researcher, ss-codebase-explorer

**Coordination/Advisory (10):** ss-beads-coordinator, ss-iteration-supervisor, ss-patrol-agent, ss-librarian, ss-sprint-health-analyst, ss-adjudicator, ss-adversarial-reviewer, ss-ai-llm-expert, ss-aws-expert, ss-impact-analyst

**Cross-cutting (4):** ss-architecture-guardian, ss-compliance-auditor, ss-infrastructure-auditor, ss-repository-manager

**External (1):** polyrepo-cartographer

### Tier 2: Apply Targeted Fixes (Before Next Use)

| Agent | Fix |
|-------|-----|
| `ss-debugger` | Add Write + Edit to tool list (required for bug fix deliverable) |
| `ss-dod-enforcer` | Embed SkillSpoke DoD checklist |
| `ss-adjudicator` | Define escalation criteria (loop limit, escalation target) |
| `ss-architecture-guardian` | Define trigger mechanism for "proactive" behavior |
| `ss-dynamodb-schema-designer` | Define standardized output format (access pattern table schema) |

### Tier 3: Strengthen (Next Development Iteration)

- `ss-adr-doc-writer` — add ADR template + numbering convention
- `ss-adversarial-reviewer` — add rubric format + findings structure
- `ss-ai-llm-expert` — add Bedrock/FastMCP specifics + Bedrock Titan embedding patterns for matching
- `ss-api-contract-validator` — clarify vs ss-contract-test-writer
- `ss-aws-expert` — add SkillSpoke approved service set including AppSync, OpenSearch
- `ss-bounded-context-mapper` — add context map output format

### Tier 4: Merge (Resolve Mandate Overlap)

| Primary | Absorb | Outcome |
|---------|--------|---------|
| `ss-compliance-auditor` | `ss-architecture-guardian` | One agent with two modes: import-graph analysis + infrastructure/config analysis |

### Tier 5: Create New Agents

Activate in priority order:

| Priority | Agent | When |
|----------|-------|------|
| 1 | `ss-appsync-developer` | When chat / GraphQL feature begins |
| 1 | `ss-matching-engineer` | When matching/recommendation feature begins |
| 2 | `ss-android-developer` OR `ss-rn-developer` | After architecture team decides Android path |
| 2 | `ss-solution-architect` | When data architecture / agentic system design work begins |
| 3 | `ss-data-engineer` | When analytics pipeline / ML training data pipeline begins |
| 3 | `ss-ml-engineer` | When matching model training begins |
| 3 | `ss-backend-ai-specialist` | When LLM observability / streaming responses / event-driven patterns need dedicated focus |
| 4 | `ss-chaos-engineer` | When SRE/reliability program begins |
| 4 | `ss-sre-specialist` | When SLO/FinOps program begins |
| 4 | `ss-vector-db-expert` | When semantic search / RAG pipeline for matching begins |
| 5 | `ss-algorithms-engineer` | When matching algorithm complexity becomes a bottleneck |

### Tier 6: Retarget from to_review (After Path Surgery)

Fix broken paths + rename to `ss:` convention for all 7 commands after their corresponding agents are created.

---

## Summary Counts

| Category | Count |
|----------|-------|
| Keep as-is (existing ss-*) | 74 |
| Fix critical bugs (existing) | 5 |
| Strengthen with domain context | 6 |
| Merge (existing) | 2 → 1 |
| New agents to create | 11 |
| Mobile decision pending | 1 (ss-android-developer OR ss-rn-developer) |
| Retarget commands | 7 |
| **Final target agent count (all surfaces, all features)** | **~91** |

_Note: Android path decision resolves to either ss-android-developer or ss-rn-developer — one activates, not both. Final count is 90 if Kotlin, 90 if React Native (same count, different agent). Both agent definitions should be written and kept; only one is activated after architecture team decision._
