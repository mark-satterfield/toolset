# SkillSpoke Skill Audit
Generated: 2026-04-27

## Tech Stack Summary
- **Languages:** Python (Lambda, CDK, MCP servers), TypeScript (Next.js, React Native)
- **IaC:** AWS CDK only (not Terraform/Pulumi)
- **Primary DB:** DynamoDB (exploring PostgreSQL/pgvector)
- **Caching:** ElastiCache (Valkey/Redis)
- **AI:** Bedrock (production), Ollama + ChromaDB (local/GraphRAG)
- **Compute:** Lambda (serverless-first; Docker only for test infra)
- **Frontend:** Next.js (web), React Native (mobile iOS/Android)
- **Testing:** pytest (Python), Playwright (E2E via pip), Vitest (TS)
- **Task runner:** go-task (Taskfile)
- **MCP servers:** 9 custom project servers + GraphRAG MCP server (FastMCP 2.0+)
- **Repos:** 64 (polyrepo, GitHub org: satteritsik)

---

## Remove (wrong stack / zero overlap)

| Skill | Reason |
|---|---|
| `ec2` | Serverless; no EC2 in production |
| `ecs` | Docker only for test infra (Mailpit); no container runtime |
| `eks` | Kubernetes not used anywhere |
| `senior-devops` | Assumes Docker/K8s/Ansible/Terraform — SkillSpoke uses CDK + go-task |
| `senior-data-engineer` | Spark/Airflow/Kafka — no data pipeline infrastructure |
| `senior-data-scientist` | scikit-learn/PyTorch model training — uses Bedrock, not custom training |
| `senior-computer-vision` | OpenCV/CNN — not part of the product |
| `senior-ml-engineer` | ML training/MLOps — replaced by Bedrock managed inference |
| `stripe-integration-expert` | No payment service in the repo catalog |

---

## Keep, but trim / retarget

| Skill | What to fix |
|---|---|
| `observability-designer` | Strip Prometheus/Grafana/Elasticsearch/Jaeger; keep CloudWatch (actual stack) |
| `database-schema-designer` | Strip Prisma/Drizzle/TypeORM; refocus on DynamoDB single-table + PostgreSQL/pgvector (exploratory) |
| `api-test-suite-builder` | Strip Express/Django/Supertest; refocus on pytest + httpx for Lambda, Playwright for E2E |
| `tdd-guide` | Strip JUnit/Mocha/Go test; keep pytest and Vitest only |
| `senior-backend` | Strip Express/Django; target Python Lambda handlers + chassis/handler superclass pattern |
| `dependency-auditor` | Strip Go/Rust/Ruby/Maven/PHP/C#; keep npm + pip/poetry only |
| `aws-solution-architect` | Strip Terraform/Pulumi; CDK-only |
| `code-reviewer` | Strip Go/Swift/Kotlin; Python + TypeScript only |
| `senior-fullstack` | Narrow to Next.js + Python Lambda (not generic Node/Express) |
| `rag-architect` | Add FastMCP + Bedrock Knowledge Bases as target deployment paths alongside ChromaDB |
| `rds` | Mark as exploratory/future; add pgvector as candidate alongside standard RDS patterns |

---

## Keep as-is (strong fit)

`lambda`, `dynamodb`, `api-gateway`, `cognito`, `eventbridge`, `sqs`, `sns`, `s3`, `iam`,
`secrets-manager`, `step-functions`, `cloudformation`, `cloudwatch`, `aws-cdk-development`,
`aws-serverless-eda`, `aws-agentic-ai`, `bedrock`, `aws-mcp-setup`, `aws-cost-operations`,
`mcp-server-builder`, `a11y-audit`, `senior-frontend`, `senior-architect`, `senior-qa`,
`senior-secops`, `senior-security`, `senior-prompt-engineer`, `changelog-generator`,
`code-reviewer`, `api-design-reviewer`, `polyrepo-steward`, `tech-debt-tracker`,
`agent-orchestration`, `orchestrator-discipline`, `product-analytics`, `product-discovery`,
`product-strategist`, `roadmap-communicator`

---

## Gaps — new skills to add

| Skill | Why needed |
|---|---|
| `react-native` | Mobile frontend (iOS/Android) — `senior-frontend` is Next.js only |
| `elasticache-valkey` | Session caching + idempotency layer — not covered anywhere |
| `fastmcp-server` | They build MCP servers with FastMCP 2.0+; `mcp-server-builder` is protocol-level, not FastMCP-specific |
| `bedrock-knowledge-bases` | AWS-native RAG path (vs local ChromaDB) — likely the production RAG target |
| `cloudfront-waf` | Edge infra repo, CloudFront distributions + WAF rules — used for all public endpoints |
| `cdk-constructs` | L2/L3 construct patterns, factory patterns (bootstrap-common has Lambda factory construct) |
| `dynamodb-single-table` | Deep single-table design — SkillSpoke-repository base pattern; high-value skill |
| `webauthn-passkeys` | webAuth-service implements FIDO2/WebAuthn — specialized enough for dedicated coverage |
| `python-lambda-chassis` | chassis shared package with routing/DI/idempotency/rate-limiting is project-specific |
| `taskfile` | All repos use go-task for install/deploy/test/lint/fmt — agents need this |

---

## AWS MCPs to add

| MCP | Priority | Why |
|---|---|---|
| AWS CDK MCP | High | 13 infra repos, CDK is primary IaC tool |
| AWS Lambda MCP | High | Primary compute layer |
| AWS DynamoDB MCP | High | Primary database |
| AWS CloudWatch MCP | High | Primary observability |
| AWS Bedrock MCP | High | AI chat service, model invocation |
| AWS IAM MCP | Medium | Permission management across all services |
| AWS S3 MCP | Medium | Document storage (resume uploads, generated docs) |
| AWS EventBridge MCP | Medium | Event routing (events-infra, events-service) |
| AWS Secrets Manager MCP | Medium | secretsRotation-service, secrets-infra |
| AWS Cost Explorer MCP | Low-Medium | Monitoring costs across 64-repo infra |

---

## Proposed execution order

1. **Remove 9 skills** — clean deletions, no tailoring needed
2. **Trim 10 skills** — in-place edits to strip wrong-tech assumptions
3. **Add 10 new skills** — gap fills, can be scaffolded and filled iteratively
4. **Add AWS MCPs** — install and wire, then update `aws-mcp-setup` skill
