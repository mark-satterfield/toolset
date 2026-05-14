# New Skills Analysis
_Generated 2026-04-28. Sources: `plugins/agent-teams-workforce/skills/` (62 existing), `to_review/skills/` (~56 to-review). All skills read from file content — not filenames or frontmatter alone._

---

## Table 1: Union Skills Inventory

### Existing Skills

| Skill | What it actually covers | Recommendation |
|-------|--------------------------|----------------|
| `a11y-audit` | WCAG 2.1/3.0, axe-core, Lighthouse CI, color contrast, keyboard navigation | Keep as-is |
| `agent-orchestration` | Claude Code multi-agent delegation, subagent spawning patterns | Keep as-is |
| `api-design-reviewer` | REST/GraphQL API design, OpenAPI 3.x principles, DRY, versioning | Keep as-is |
| `api-gateway` | AWS API Gateway REST v1 CDK constructs, Lambda proxy, custom authorizers | Keep as-is |
| `api-test-suite-builder` | API testing, OWASP API Top 10 | Retarget: add SkillSpoke API Gateway + AppSync patterns |
| `aws-agentic-ai` | Bedrock Agents, Knowledge Bases, multi-agent patterns on AWS | Keep as-is |
| `aws-cdk-development` | CDK TypeScript/Python, stacks, constructs, synthesis patterns | Keep as-is |
| `aws-cost-operations` | AWS cost analysis, rightsizing, Reserved Instances, Savings Plans, Budgets | Keep as-is |
| `aws-mcp-setup` | Claude Code MCP server configuration, AWS MCP plugin wiring | Keep as-is |
| `aws-serverless-eda` | Event-driven architecture with Lambda, EventBridge, SQS/SNS | Keep as-is |
| `aws-solution-architect` | AWS architecture breadth: service selection, multi-tier design, well-architected | Merge: fold as front-door dispatcher into specialist skills; significant overlap with aws-cdk-development, aws-serverless-eda, aws-agentic-ai |
| `bedrock` | AWS Bedrock model invocation | Retarget: update model IDs (claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5-20251001); add Converse API, streaming, model routing |
| `changelog-generator` | CHANGELOG.md generation from git history, Conventional Commits | Keep as-is |
| `cloudformation` | CloudFormation templates, CDK synth output, nested stacks | Keep as-is |
| `cloudwatch` | CloudWatch alarms, dashboards, Log Insights queries, metric filters | Keep as-is |
| `code-reviewer` | PR review, defect detection, CDK and Python code quality | Keep as-is |
| `cognito` | AWS Cognito user pools | Retarget: add Lambda triggers, social IdP (Google/Apple), Cognito Advanced Security, MFA enforcement |
| `cove-prompt-design` | Prompt engineering, Claude prompt design patterns (cove = SkillSpoke internal) | Keep as-is |
| `database-schema-designer` | Database schema design (PostgreSQL-heavy) | Retarget: shift primary focus to DynamoDB single-table design; keep PostgreSQL as secondary for RDS |
| `delegate` | Agent delegation discipline, when/how to delegate | Keep as-is |
| `dependency-auditor` | pip-audit, npm audit, CVE tracking, semantic versioning | Keep as-is |
| `dynamodb` | DynamoDB data modeling, single-table design, GSI patterns, boto3 | Keep as-is |
| `email-template-builder` | Email template generation (TypeScript-only) | Retarget: add Python/boto3 SES patterns |
| `eventbridge` | EventBridge rules, event buses, DLQs, cross-account events | Keep as-is |
| `external-pattern-integrator` | Toolset maintenance (for this repo only) | Exclude: not for SkillSpoke sessions |
| `find-cause` | Root cause analysis, debugging methodology, hypothesis-driven diagnosis | Keep as-is |
| `how-to-delegate` | Orchestrator-level delegation protocols, role boundaries | Keep as-is |
| `iam` | AWS IAM policies, least privilege, role design, SCPs | Keep as-is |
| `lambda` | AWS Lambda Python handlers | Retarget: add CDK PythonFunction construct, aws-lambda-powertools v3, streaming response patterns |
| `mcp-server-builder` | MCP server building at protocol level, stdio/SSE transports | Keep as-is |
| `observability-designer` | Observability architecture (Prometheus/Grafana-heavy) | Retarget: replace with CloudWatch/X-Ray/aws-lambda-powertools structured logging; add Lambda Insights |
| `orchestrator-discipline` | Orchestrator behavior constraints, no-write rules, loop control | Keep as-is |
| `polyrepo-steward` | Polyrepo topology discovery, manifest management, greenfield setup | Keep as-is |
| `product-analytics` | Product analytics event tracking, dashboards, funnel analysis | Keep as-is |
| `product-discovery` | Product discovery, user research, problem framing | Keep as-is |
| `product-strategist` | Product strategy, positioning, competitive analysis | Keep as-is |
| `rag-architect` | RAG architecture, vector search | Retarget: add Bedrock Knowledge Bases, Bedrock Embeddings (Titan), Bedrock Converse API for RAG; include candidate-job matching via embeddings |
| `rds` | AWS RDS PostgreSQL | Retarget: add RDS Proxy, Aurora Serverless v2 auto-pause, IAM database auth; remove deprecated instance classes |
| `roadmap-communicator` | Product roadmap communication, stakeholder alignment | Keep as-is |
| `s3` | S3 bucket design, access patterns, lifecycle rules, versioning | Keep as-is |
| `secrets-manager` | AWS Secrets Manager patterns, rotation, Lambda integration | Keep as-is |
| `senior-architect` | System architecture, ADRs, trade-off analysis, microservice patterns | Keep as-is |
| `senior-backend` | Backend development (Node.js/Express/PostgreSQL) | Retarget: replace with Python Lambda + DynamoDB focus; Node.js only for Next.js API routes |
| `senior-computer-vision` | GPU/PyTorch/CUDA, computer vision models | Exclude: zero overlap with SkillSpoke product domain |
| `senior-data-engineer` | Data engineering (Airflow/Spark) | Retarget: replace Airflow/Spark with AWS Glue, Kinesis Data Streams, DynamoDB Streams, EventBridge Pipes, S3 data lake, Athena |
| `senior-data-scientist` | Data science (reference files are broken boilerplate — all 3 identical) | Fix broken references + Retarget: candidate-job matching models, behavioral signal analysis, feature engineering on SkillSpoke feedback data, Bedrock fine-tuning |
| `senior-devops` | DevOps/infrastructure (Terraform-only) | Retarget: replace Terraform with AWS CDK; add go-task (Taskfile); add GitHub Actions OIDC for AWS; retain container/ECS/EKS knowledge as secondary-path for model self-hosting |
| `senior-frontend` | React/Next.js frontend development, TypeScript, Tailwind | Keep as-is |
| `senior-fullstack` | Full-stack development (broad) | Retarget: collapse — redirect to senior-frontend (Next.js/React) + senior-backend (Python Lambda); eliminate the overlap |
| `senior-ml-engineer` | ML engineering (K8s inference-heavy) | Retarget: primary = Bedrock, SageMaker, Lambda inference; secondary = ECS/EKS/GPU containers for self-hosted model scenarios (data residency, cost, latency) |
| `senior-prompt-engineer` | Prompt engineering, LLM optimization, Claude-specific techniques | Keep as-is |
| `senior-qa` | QA engineering, test strategy, coverage analysis | Keep as-is |
| `senior-secops` | Security operations | Retarget: add AWS IAM/GuardDuty/SecurityHub/Secrets Manager specifics |
| `senior-security` | Security architecture, STRIDE threat modeling, OWASP | Keep as-is |
| `sns` | AWS SNS topics, subscriptions, fan-out patterns | Keep as-is |
| `sqs` | AWS SQS queues, DLQs, visibility timeout, message deduplication | Keep as-is |
| `step-functions` | AWS Step Functions workflows, state machine design, error handling | Keep as-is |
| `stripe-integration-expert` | Stripe payments, webhooks, subscription management | Keep as-is |
| `subagent-contract` | Subagent behavioral contract (behavioral governance trio) | Keep as-is |
| `tech-debt-tracker` | Tech debt inventory, scoring, tracking, triage | Keep as-is |
| `test-failure-mindset` | Test-first mindset, TDD discipline (behavioral governance trio) | Keep as-is |
| `validation-protocol` | Input validation, assertion patterns (behavioral governance trio) | Keep as-is |

### to_review Skills

| Skill | What it actually covers | Recommendation |
|-------|--------------------------|----------------|
| `accessibility-expert` | WCAG 2.1/2.2, screen readers, keyboard navigation, axe/WAVE/Lighthouse | Keep as-is |
| `adr-writer` | ADR lifecycle, MADR format, decision documentation | Keep as-is |
| `algorithm-design` | Algorithm selection, complexity analysis, optimization trade-offs | Keep as-is |
| `android-native` | Jetpack Compose, Android SDK, coroutines, Room, Hilt | Keep + Relocate from `relational-databases/` — confirmed Android surface |
| `api-implementation` | API implementation patterns, RESTful design, error handling | Keep as-is |
| `api-testing` | API test strategy, Postman, contract tests | Keep as-is |
| `app-store-deployment` | App Store Connect, Google Play deployment, code signing, metadata | Keep + Relocate from `relational-databases/` |
| `auth-implementation` | Authentication implementation, WebAuthn/FIDO2, session management | Keep as-is |
| `aws-architect` | AWS architecture patterns, service selection, multi-tier design | Keep as-is; clarify scope vs aws-expert (to_review) — merge if too close |
| `aws-dynamodb` | DynamoDB single-table design, GSI/LSI strategy, TypeScript SDK v3, composite keys | Retarget: fix non-standard frontmatter; excellent content — wire into SkillSpoke template |
| `aws-expert` | AWS operational configuration, CLI, live environment inspection | Retarget: clarify scope vs aws-architect — merge if too close |
| `azure-architect` | Azure-only architecture | Exclude: SkillSpoke makes no considerations for Azure |
| `background-jobs` | Background job patterns, queues, schedulers | Retarget: add SQS/Lambda consumer patterns; add EventBridge Scheduler for ML batch jobs |
| `backup-recovery` | Backup strategies, RTO/RPO, disaster recovery | Retarget: add DynamoDB PITR, Aurora backup/restore, S3 cross-region replication |
| `caching-strategies` | Caching patterns (cache-aside, write-through), TTL, invalidation | Keep as-is |
| `capacity-planning` | Capacity planning, load estimation, auto-scaling | Retarget: add DynamoDB WCU/RCU planning, Lambda concurrency limits, Kinesis shard planning |
| `ci-test-integration` | CI pipeline test integration, GitHub Actions test gates | Keep as-is |
| `columnar-databases` | Cassandra/ScyllaDB/HBase | Exclude: AWS-native alternatives (DynamoDB, Redshift) cover all SkillSpoke use cases |
| `computational-complexity` | Big-O analysis, space/time trade-offs, algorithm complexity | Keep as-is |
| `connection-management` | Connection pooling, timeout patterns, retry logic; also contains incident-response sub-skill | Split: extract `incident-response` to own skill; retain `connection-management` for pooling + retry |
| `cost-modeling` | Cloud cost modeling, TCO analysis, cost attribution | Keep as-is |
| `cost-optimization` | Cost reduction patterns, right-sizing, reserved capacity | Keep as-is |
| `css-architecture` | CSS architecture (BEM, utility-first, CSS-in-JS), design tokens | Keep as-is |
| `data-modeling` | Data modeling patterns, entity design, normalization | Keep as-is |
| `data-structures` | Data structures: arrays, trees, hash maps, graphs | Keep as-is |
| `data-validation` | Input validation, schema validation, sanitization | Keep as-is |
| `data-warehouse-olap` | Snowflake/BigQuery/Databricks/Redshift/DuckDB DW patterns | Retarget: focus on AWS-native analytics (Redshift Serverless, Athena + S3 data lake, Glue Data Catalog, QuickSight); de-emphasize Snowflake/BigQuery |
| `database-devops` | Kubernetes operators + Terraform IaC for databases | Exclude: Kubernetes primary-path excluded; Terraform excluded |
| `database-implementation` | ORM patterns across 8 language ecosystems | Retarget: extract Python/SQLAlchemy + TypeScript/Prisma sections; add DynamoDB-Toolbox/ElectroDB |
| `database-migration` | 11 migration tools, expand-and-contract, online DDL, CDC | Retarget: focus on Alembic/Prisma Migrate/Atlas zero-downtime; de-emphasize Kubernetes/Debezium CDC |
| `database-monitoring` | PostgreSQL/MySQL/MongoDB/Redis monitoring | Retarget: add DynamoDB CloudWatch metrics (consumed RCU/WCU, throttle events, SuccessfulRequestLatency) |
| `database-security` | PostgreSQL RBAC, RLS, pgAudit, column encryption | Retarget: add DynamoDB IAM fine-grained access control, VPC endpoint patterns, attribute-level encryption |
| `document-databases` | MongoDB deep + Elasticsearch/OpenSearch ILM, mapping, query DSL | Retarget: focus on Amazon OpenSearch Service section; de-emphasize MongoDB |
| `dynamic-programming` | Knapsack, LCS, bitmask DP, sequence alignment, optimal substructure | Keep as-is — directly applicable to candidate-job matching and scheduling optimization |
| `e2e-testing` | Playwright (core), Cypress, Selenium, visual regression, accessibility E2E | Keep as-is |
| `embedded-databases` | SQLite, RocksDB, LMDB, BoltDB, Realm, ObjectBox | Keep with reconsideration: SQLite + Realm relevant for React Native offline caching |
| `flutter-expert` | Flutter SDK, Dart 3, Riverpod 2, GoRouter | Keep + Relocate from `relational-databases/` — architecture team may consider Flutter for Android |
| `frontend-performance` | Core Web Vitals, Next.js optimization, RSC, bundle splitting | Keep as-is |
| `gcp-architect` | GCP-only architecture | Exclude: SkillSpoke makes no considerations for GCP |
| `graph-algorithms` | BFS/DFS, shortest path, topological sort, bipartite matching, MST | Keep as-is — bipartite matching for candidate-job fit; skill adjacency graphs |
| `graph-databases` | Neo4j/Neptune/Tigergraph | Exclude: SkillSpoke's graph problems (skill adjacency, matching) solvable with DynamoDB graph patterns + graph-algorithms skill |
| `ios-native` | SwiftUI, UIKit, Swift concurrency, StoreKit 2 | Keep + Relocate from `relational-databases/` — confirmed iOS surface |
| `key-value-stores` | Redis/ElastiCache (caching, streams, pub/sub), DynamoDB as KV | Keep as-is |
| `mathematical-optimization` | Linear programming, convex optimization, gradient descent, solver patterns | Keep as-is — match scoring optimization, ranking model calibration |
| `message-queues` | SQS patterns (DLQ, idempotency, ordering), async messaging | Keep as-is |
| `microservices` | Saga, event-driven, circuit breaker, service discovery | Retarget: emphasize resilience patterns for Lambda-based microservices; note K8s service discovery as secondary-path |
| `migration-planner` | Migration strategy, expand-and-contract, blue-green, feature flags | Keep as-is |
| `mobile-performance` | 60fps rendering, startup time, battery efficiency, profiling | Keep + Relocate from `relational-databases/` |
| `mobile-security` | Certificate pinning, Secure Enclave, biometric auth, OWASP Mobile | Keep + Relocate from `relational-databases/` |
| `mobile-testing` | Detox (React Native E2E), Appium, AWS Device Farm, gesture testing | Keep as-is |
| `monitoring-setup` | Prometheus/Grafana, CloudWatch basics, Kubernetes monitors | Retarget: add Lambda/serverless monitoring — CloudWatch Lambda Insights, X-Ray, CDK alarm constructs |
| `multi-model-databases` | Cosmos DB/FaunaDB/SurrealDB | Exclude: AWS-native; DynamoDB covers multi-model use case |
| `newsql-distributed` | CockroachDB/Spanner/TiDB | Exclude: DynamoDB covers distributed use case; Aurora DSQL for serverless distributed SQL |
| `numerical-methods` | Numerical algorithms + cryptographic-foundations section (JWT, hashing, API auth) | Split: extract `security-primitives` (cryptographic-foundations) to own skill; retain numerical-methods for ML/optimization |
| `offline-first` | Offline sync, conflict resolution, optimistic updates, CRDT | Keep + Relocate from `relational-databases/` — candidates may use mobile on-the-go |
| `react-expert` | React state management, Concurrent Mode, RSC, hooks patterns | Keep as-is |
| `react-native-expert` | Expo SDK 52+, New Architecture (Fabric/TurboModules/JSI), EAS Build/Submit, NativeWind v4, Reanimated 3, Detox+Maestro E2E | Keep + Relocate from `relational-databases/` |

---

## Table 2: Recommended Skill Library (Greenfield Design)

_Blank-slate design for SkillSpoke's agent skill library. Organized by expertise domain. These are expertise areas agents draw from — not necessarily one-to-one with SKILL.md files, but the knowledge the workforce collectively needs._

### Agent Governance

| Skill | Expertise it covers |
|-------|---------------------|
| **Orchestrator Protocol** | Delegation discipline, no-write/no-bash rules for leads, phase sequencing logic, loop control mechanics, phase gate enforcement, parallel subagent coordination |
| **Subagent Contract** | DONE/BLOCKED output protocol, input/output contract design, scope boundary enforcement, behavioral governance trio (with test-failure-mindset and validation-protocol) |
| **Adversarial Review Discipline** | Critic protocol, rubric design, structured findings format (severity + category), arbitration criteria, adversarial loop convergence, how to challenge assumptions without proposing fixes |
| **Delegation Mastery** | When and how to delegate, subagent sizing, parallel vs sequential work decomposition, delegation handoff format, monitoring delegated work without micromanaging |

### Product & Strategy

| Skill | Expertise it covers |
|-------|---------------------|
| **Product Strategy** | OKR definition and measurement, product roadmap communication, competitive positioning, feature scoping, success metrics, leading vs lagging indicator distinction |
| **User Research** | Data-driven persona development, JTBD framework, behavioral segmentation, empathy mapping; treating platform usage data (candidate interactions, match outcomes) as user research signal |
| **Story Craft** | INVEST user story writing, Given/When/Then acceptance criteria (BDD), Definition of Done validation, epic decomposition, edge case enumeration, negative path coverage |
| **WSJF Prioritization** | Cost of delay analysis, relative sizing, backlog sequencing, WSJF scoring mechanics, beads issue priority management |

### System Architecture

| Skill | Expertise it covers |
|-------|---------------------|
| **ADR Governance** | ADR lifecycle (proposed → accepted → deprecated → superseded), MADR format, SkillSpoke numbering convention, two-way vs one-way door decision framework, fitness functions as automated architectural tests |
| **Domain-Driven Design** | Bounded context design, aggregate root identification, anti-corruption layers, event storming facilitation, context map output formats, ubiquitous language enforcement |
| **Agentic Systems Architecture** | Tool boundary design, idempotent tool call patterns, circuit breakers for agent workflows, observation/action loop design, multi-agent coordination topology, agent failure mode handling |
| **Microservice & EDA Patterns** | Saga pattern (choreography vs orchestration), event-driven microservice design, resilience patterns for Lambda-based services (retry, circuit breaker, bulkhead), service boundary enforcement |

### AWS Platform — Core

| Skill | Expertise it covers |
|-------|---------------------|
| **Lambda Python Mastery** | aws-lambda-powertools v3 (tracing, structured logging, metrics, idempotency, validation), event parsing per source (API Gateway, SQS, EventBridge, DynamoDB Streams), cold start optimization, streaming response, middleware pattern, response normalization |
| **CDK Engineering** | AWS CDK Python: L2/L3 construct authoring, CDK Pipelines, aspects, custom resources, escape hatches, cdk synth validation, synthesis output interpretation, CDK Pipelines for multi-stage deployment |
| **API Gateway Patterns** | REST v1 CDK constructs, Lambda proxy integration, custom authorizers, usage plans, request/response mapping; explicit REST v1 vs HTTP API v2 distinction and when each applies |
| **DynamoDB Single-Table Design** | Access pattern modeling (entity, PK, SK, GSI1PK, GSI1SK), composite key design, GSI/LSI strategy, sparse indexes, adjacency list pattern, overloaded indexes, versioned items, NoSQL Workbench export format |
| **DynamoDB Implementation** | boto3 implementation of approved access patterns, conditional writes, DynamoDB Transactions, PartiQL for batch operations, DynamoDB Local testing, connection reuse across Lambda invocations |
| **EventBridge & SQS** | EventBridge rules, event buses, EventBridge Pipes for stream-to-Lambda wiring; SQS (DLQ, idempotency tokens, visibility timeout, FIFO ordering, exactly-once semantics), outbox pattern, poison-pill handling |
| **AppSync & GraphQL** | AppSync schema definition language, Lambda and DynamoDB direct resolvers, WebSocket subscription design for real-time features (chat, live updates), authorization modes (Cognito/IAM/API key/OIDC), caching, subscription filtering, CDK AppSync constructs |
| **S3 Platform Patterns** | Bucket design, prefix strategy for data lake partitioning, lifecycle rules, versioning, OAC for CloudFront, cross-region replication, S3 as data lake landing zone |

### AWS Platform — Extended

| Skill | Expertise it covers |
|-------|---------------------|
| **CloudFront & WAF** | CloudFront distribution design, behavior and cache policy configuration, custom origins (API Gateway, S3, ALB); WAF v2 (rate limiting, geo-restriction, managed rule groups, bot control), CDK constructs for both |
| **Cognito & Identity** | Cognito user pools, identity pools, Lambda triggers (pre-signup, post-confirmation, pre-token generation), social IdP integration (Google/Apple Sign-In), Cognito Advanced Security, MFA enforcement, Hosted UI customization |
| **WebAuthn & Passkeys** | FIDO2/WebAuthn server-side attestation and assertion flows, credential storage design in DynamoDB, browser WebAuthn API client integration, React Native WebAuthn, Swift PassKit/AuthenticationServices integration, passkey UX patterns |
| **ElastiCache & Valkey** | Redis patterns for Lambda: session caching, idempotency token store, rate limiting, match result caching; Valkey fork compatibility; CDK ElastiCache construct; Lambda VPC connection reuse patterns; cluster vs serverless mode |
| **OpenSearch Service** | Amazon OpenSearch Service cluster sizing, index design, query DSL, relevance tuning (BM25, custom similarity); k-NN vector search for semantic job/candidate matching; CDK constructs; IAM fine-grained access control; as complement to DynamoDB for full-text search |
| **CloudWatch Observability** | CloudWatch alarms, dashboards, Log Insights query patterns, metric filters; Lambda Insights for cold start and memory analysis; X-Ray tracing and service map interpretation; CDK alarm constructs; aws-lambda-powertools structured logging integration |
| **IAM & Secrets Management** | IAM policy design (least privilege, condition keys), SCPs, IAM role chaining; Secrets Manager rotation patterns, Lambda secret retrieval caching; DynamoDB attribute-level fine-grained access; VPC endpoint policies |
| **AWS Cost Optimization** | DynamoDB on-demand vs provisioned capacity analysis, Lambda concurrency cost modeling, Reserved Instance and Savings Plan strategy, CloudWatch cost anomaly detection, Budgets and alerts, FinOps maturity model |
| **Step Functions** | State machine design (Standard vs Express workflows), error handling and retry strategies, distributed saga implementation, parallel state design, callback patterns with Lambda |

### Matching & ML (SkillSpoke Core)

| Skill | Expertise it covers |
|-------|---------------------|
| **Candidate-Job Matching Algorithms** | Bipartite matching (Hungarian algorithm), collaborative filtering (user-based and item-based), content-based filtering, embedding-based cosine similarity (Bedrock Titan), ranking model design, match score calibration, A/B experimentation on match quality, match explanation generation, AWS Personalize evaluation as managed option |
| **Recommendation Systems** | Matrix factorization, real-time vs batch recommendation tradeoffs, cold start problem handling, diversity vs relevance balance, multi-armed bandit for exploration, recommendation freshness |
| **Behavioral Signal Instrumentation** | Designing every candidate interaction as a labeled training data point: signal taxonomy (application, view, feedback, match outcome, skip, rejection), DynamoDB Streams → Kinesis → S3 pipeline; training data schema design; signal quality validation; avoiding label leakage |
| **ML Data Pipeline** | AWS Glue (ETL jobs, crawlers, Data Catalog), Kinesis Data Streams (shard design, Lambda consumer patterns), DynamoDB Streams CDC, EventBridge Pipes, S3 data lake (prefix design, Hive-style partitioning, lifecycle), Athena query optimization, Redshift Serverless for analytical workloads |
| **Bedrock & SageMaker** | Bedrock Converse API, model routing and fallback chains, Bedrock fine-tuning pipeline design, SageMaker training jobs, model evaluation and registry, SageMaker Feature Store, Lambda inference for lightweight models; LLM observability (token budget, latency, cost per invocation) |
| **Vector Search & Embeddings** | Bedrock Titan embedding model, pgvector (HNSW vs IVFFlat index tradeoffs), Qdrant, Amazon OpenSearch k-NN; embedding model selection criteria; RAG pipeline debugging; semantic similarity scoring; hybrid search (BM25 + vector) |
| **FastMCP Development** | FastMCP 2.0+ Python server development: tool definitions, resource handlers, context management, streaming responses, auth patterns, multi-server coordination, testing patterns; SkillSpoke's 9 custom MCP servers as reference implementations |
| **Algorithm Design & Complexity** | Algorithm selection methodology, Big-O analysis, dynamic programming (sequence alignment for skill matching, knapsack for constraint satisfaction), graph algorithms (BFS/DFS, bipartite matching, topological sort), mathematical optimization (linear programming, gradient descent for ranking models) |

### Frontend — Web

| Skill | Expertise it covers |
|-------|---------------------|
| **Next.js Engineering** | App Router, React Server Components, streaming, TypeScript, Tailwind CSS, bundle optimization, Core Web Vitals (LCP, CLS, INP), image optimization, layout patterns |
| **React Mastery** | State management patterns (Zustand, Jotai, Context), Concurrent Mode, hooks patterns, component architecture, memoization, performance profiling |
| **AppSync Client Integration** | Amplify client patterns, real-time subscription lifecycle management, WebSocket reconnection handling, GraphQL query/mutation patterns, optimistic updates |

### Frontend — Mobile

| Skill | Expertise it covers |
|-------|---------------------|
| **Swift/SwiftUI Mastery** | iOS 26 SwiftUI, Liquid Glass (GlassEffect/GlassEffectContainer via SwiftUI material compositor), declarative UI patterns, Swift concurrency (async/await, actors), StoreKit 2 (subscriptions, in-app purchases, entitlements), App Store guidelines and Apple HIG |
| **Core ML & On-Device AI** | Core ML model deployment, TFLite/LiteRT for cross-platform on-device inference, model quantization, ONNX conversion, on-device inference for SkillSpoke features (candidate skill assessment, offline recommendations) |
| **Android Native** | Kotlin coroutines, Jetpack Compose (Material You, Scaffold, navigation), Room, Hilt, Google Play Billing, lifecycle-aware components, Android-specific accessibility |
| **React Native (New Architecture)** | Expo SDK 52+, Fabric renderer/TurboModules/JSI, EAS Build/Submit, NativeWind v4, Reanimated 3, MMKV, Skia, Detox E2E testing, StoreKit + Google Play Billing integration, offline-first sync |
| **Mobile Security** | Certificate pinning, Secure Enclave usage, biometric authentication, OWASP Mobile Top 10, secure local storage patterns (Keychain/Keystore), jailbreak/root detection |
| **App Store Deployment** | App Store Connect (metadata, screenshots, review submissions), Google Play Console (staged rollouts, track management), code signing, provisioning profiles, TestFlight, Firebase App Distribution |
| **Mobile Performance** | 60fps rendering profiling (Instruments, Android Profiler), startup time optimization, battery efficiency, memory leak detection, Core Web Vitals equivalent for React Native |

### Quality Engineering

| Skill | Expertise it covers |
|-------|---------------------|
| **TDD Discipline** | London School mock-first approach, red-green-refactor cycle, test doubles taxonomy (mock vs stub vs spy vs fake), pytest parametrize and fixture design, test boundary identification |
| **Integration Testing Patterns** | LocalStack for AWS service mocking, DynamoDB Local, pytest fixtures for AWS resource setup/teardown, real infrastructure testing vs mocked infrastructure tradeoffs, container-based test dependencies |
| **Playwright Mastery** | TypeScript, page object model, smoke test strategy, network request mocking, visual regression baseline management, cross-browser matrix (Chrome/Safari/Firefox), `npx playwright test` patterns |
| **Contract Testing** | Pact consumer-driven contracts (consumer-side test writing, provider-side verification), schemathesis for OpenAPI spec conformance, spec drift detection, when Pact vs schemathesis is appropriate |
| **Chaos Engineering** | Failure injection taxonomy (Lambda timeout, DynamoDB throttle, API Gateway 5xx, AppSync subscription drop, SQS poison-pill), Toxiproxy for network-level failure simulation, LocalStack chaos injection, DORA metrics (deployment frequency, lead time, MTTR, change failure rate), blameless postmortem facilitation |
| **Accessibility Testing** | WCAG 2.1/2.2, axe-core, playwright-axe integration, keyboard navigation testing, screen reader compatibility (NVDA, VoiceOver, TalkBack), color contrast validation, focus management testing |
| **Mobile Testing** | Detox (React Native E2E with real device simulation), Maestro (script-based UI testing), Appium, AWS Device Farm for real device testing, gesture testing, platform-specific edge cases |

### Security

| Skill | Expertise it covers |
|-------|---------------------|
| **SAST & Secret Scanning** | bandit (Python static analysis), semgrep (multi-language SAST with custom rules), gitleaks (secrets in staged changes), trufflehog (git history entropy scanning), pip-audit + npm audit (dependency CVE), severity classification and triage |
| **IAM Auditing** | Least-privilege analysis via cdk synth + yq, privilege escalation path detection, CDK IAM construct correctness, VPC endpoint policy analysis, DynamoDB attribute-level access control pattern verification, cross-account role analysis |
| **Security Architecture Skills** | STRIDE threat modeling applied to SkillSpoke's stack (Lambda/API Gateway/AppSync/DynamoDB), OWASP Top 10 for serverless, secrets management strategy, zero-trust network design, security control implementation planning |

### DevOps & Reliability

| Skill | Expertise it covers |
|-------|---------------------|
| **GitHub Actions Mastery** | OIDC auth for AWS (no long-lived credentials), caching strategy (pip/npm/CDK asset cache), Lambda deployment pipelines, matrix builds for multi-repo validation, act --dry-run local validation, secret management patterns |
| **Wave Deployment** | Deployment sequencing (dev → QA → production), pre-condition validation at each wave (spec green, tests passing, drift-free), smoke test orchestration, rollback trigger criteria, blue-green and canary patterns for Lambda |
| **SRE Practices** | SLO definition (availability, latency, error rate), CloudWatch error budget burn alarm design, Production Readiness Review facilitation, toil identification and automation, Operational Readiness Reviews, incident management |
| **FinOps** | AWS cost attribution by team and feature, Infracost in CI for CDK cost previews, crawl/walk/run maturity model, Reserved Instance and Savings Plan analysis, cost anomaly detection setup |
| **CDK Drift Detection** | cdk diff interpretation, deployed infrastructure vs CDK definition reconciliation, S3 bucket standards compliance checks, AWS Config integration, drift classification (intentional vs unintentional) |
| **Runbook Design** | Operational runbook structure (trigger, severity, diagnostic steps, resolution, escalation), incident response playbook design, disaster recovery procedure documentation, runbook testing methodology |

### Code Quality

| Skill | Expertise it covers |
|-------|---------------------|
| **Python Code Quality** | ruff (formatting and linting), mypy (type checking, strict mode), radon (cyclomatic complexity, maintainability index), Python idiomatic patterns, code smell taxonomy |
| **Technical Debt Analysis** | scc (code volume and language breakdown), radon (complexity metrics), pip-audit + npm audit (dependency risk scoring), tech debt scoring models, debt-to-feature ratio tracking |
| **Semantic Code Review** | difftastic for structure-aware diff analysis, PR review methodology, CDK construct correctness patterns, security anti-pattern library, architecture boundary enforcement in review |

### Codebase Intelligence

| Skill | Expertise it covers |
|-------|---------------------|
| **GitNexus & Code Exploration** | GitNexus query/context/impact/detect_changes CLI, GraphRAG semantic code search, execution flow tracing, symbol context analysis, polyrepo navigation across 64 satteritsik repos |
| **Impact Analysis** | Dependency graph traversal methodology, blast radius classification (low/medium/high/critical), pre-change safety gate design, gitnexus impact interpretation, risk-informed change sequencing |
| **Research Methodology** | Web + GitHub research techniques, release note and issue thread analysis, citation discipline, technology comparative evaluation framework, open-source intelligence via gh CLI |

### Data & Analytics

| Skill | Expertise it covers |
|-------|---------------------|
| **Analytics Pipeline** | Redshift Serverless (SkillSpoke behavioral analytics warehouse), Athena + S3 data lake (ad-hoc query patterns), Glue Data Catalog (schema discovery and evolution), QuickSight dashboard design for match quality and engagement metrics |
| **Data Migration Patterns** | DynamoDB single-table schema evolution (expand-and-contract, dual-write, backfill), zero-downtime migration design, Python Lambda runtime upgrade strategy, rollback planning |

### Tooling

| Skill | Expertise it covers |
|-------|---------------------|
| **Taskfile (go-task)** | Taskfile.yml task definition, variable scoping, file includes, task dependency chains, watch mode, cross-repo task coordination; SkillSpoke per-repo conventions (install, deploy, test, lint, fmt, synth tasks) |

| Skill | Action | Notes |
|-------|--------|-------|
| `a11y-audit` | Keep | — |
| `agent-orchestration` | Keep | — |
| `api-design-reviewer` | Keep | — |
| `api-gateway` | Keep | — |
| `api-test-suite-builder` | Retarget | Add AppSync patterns |
| `aws-agentic-ai` | Keep | — |
| `aws-cdk-development` | Keep | — |
| `aws-cost-operations` | Keep | — |
| `aws-mcp-setup` | Keep | — |
| `aws-serverless-eda` | Keep | — |
| `aws-solution-architect` | Merge | Fold as front-door dispatcher into specialist skills |
| `bedrock` | Retarget | Update model IDs; add Converse API, streaming |
| `changelog-generator` | Keep | — |
| `cloudformation` | Keep | — |
| `cloudwatch` | Keep | — |
| `code-reviewer` | Keep | — |
| `cognito` | Retarget | Add Lambda triggers, social IdP, Advanced Security, MFA |
| `cove-prompt-design` | Keep | — |
| `database-schema-designer` | Retarget | Shift primary to DynamoDB single-table; PostgreSQL secondary |
| `delegate` | Keep | — |
| `dependency-auditor` | Keep | — |
| `dynamodb` | Keep | — |
| `email-template-builder` | Retarget | Add Python/boto3 SES patterns |
| `eventbridge` | Keep | — |
| `external-pattern-integrator` | Exclude | Toolset maintenance only |
| `find-cause` | Keep | — |
| `how-to-delegate` | Keep | — |
| `iam` | Keep | — |
| `lambda` | Retarget | Add CDK PythonFunction, powertools v3, streaming |
| `mcp-server-builder` | Keep | — |
| `observability-designer` | Retarget | Replace Prometheus/Grafana content with CloudWatch/X-Ray/Lambda Insights |
| `orchestrator-discipline` | Keep | — |
| `polyrepo-steward` | Keep | — |
| `product-analytics` | Keep | — |
| `product-discovery` | Keep | — |
| `product-strategist` | Keep | — |
| `rag-architect` | Retarget | Add Bedrock Knowledge Bases, Titan embeddings, candidate-job matching |
| `rds` | Retarget | Add RDS Proxy, Aurora Serverless v2 auto-pause, IAM database auth |
| `roadmap-communicator` | Keep | — |
| `s3` | Keep | — |
| `secrets-manager` | Keep | — |
| `senior-architect` | Keep | — |
| `senior-backend` | Retarget | Python Lambda + DynamoDB focus; Node.js only for Next.js API routes |
| `senior-computer-vision` | Exclude | Zero overlap with SkillSpoke |
| `senior-data-engineer` | Retarget | Replace Airflow/Spark with Glue, Kinesis, DynamoDB Streams, Athena |
| `senior-data-scientist` | Fix + Retarget | Fix broken reference files; retarget to candidate-job matching + Bedrock fine-tuning |
| `senior-devops` | Retarget | Replace Terraform with CDK; add Taskfile, GitHub Actions OIDC; retain container knowledge |
| `senior-frontend` | Keep | — |
| `senior-fullstack` | Retarget | Collapse into senior-frontend + senior-backend overlap elimination |
| `senior-ml-engineer` | Retarget | Primary: Bedrock/SageMaker/Lambda; secondary: ECS/EKS/GPU for self-hosted models |
| `senior-prompt-engineer` | Keep | — |
| `senior-qa` | Keep | — |
| `senior-secops` | Retarget | Add GuardDuty, SecurityHub, Secrets Manager specifics |
| `senior-security` | Keep | — |
| `sns` | Keep | — |
| `sqs` | Keep | — |
| `step-functions` | Keep | — |
| `stripe-integration-expert` | Keep | — |
| `subagent-contract` | Keep | — |
| `tech-debt-tracker` | Keep | — |
| `test-failure-mindset` | Keep | — |
| `validation-protocol` | Keep | — |
| `accessibility-expert` | Adopt | From to_review |
| `adr-writer` | Adopt | From to_review |
| `algorithm-design` | Adopt | From to_review |
| `android-native` | Adopt + Relocate | From to_review/relational-databases/; confirmed Android surface |
| `api-implementation` | Adopt | From to_review |
| `api-testing` | Adopt | From to_review |
| `app-store-deployment` | Adopt + Relocate | From to_review/relational-databases/ |
| `auth-implementation` | Adopt | From to_review |
| `aws-architect` | Adopt | From to_review; clarify scope vs aws-expert |
| `aws-dynamodb` | Adopt + Retarget | Fix frontmatter; wire into SkillSpoke template |
| `aws-expert` | Adopt + Retarget | Clarify scope vs aws-architect; merge if too close |
| `azure-architect` | Exclude | Azure only |
| `background-jobs` | Adopt + Retarget | Add SQS/Lambda consumer + EventBridge Scheduler |
| `backup-recovery` | Adopt + Retarget | Add DynamoDB PITR, Aurora backup, S3 cross-region replication |
| `caching-strategies` | Adopt | From to_review |
| `capacity-planning` | Adopt + Retarget | Add DynamoDB WCU/RCU, Lambda concurrency, Kinesis shard planning |
| `ci-test-integration` | Adopt | From to_review |
| `columnar-databases` | Exclude | DynamoDB + Redshift cover all SkillSpoke use cases |
| `computational-complexity` | Adopt | From to_review |
| `connection-management` | Adopt + Split | Extract incident-response to own skill |
| `cost-modeling` | Adopt | From to_review |
| `cost-optimization` | Adopt | From to_review |
| `css-architecture` | Adopt | From to_review |
| `data-modeling` | Adopt | From to_review |
| `data-structures` | Adopt | From to_review |
| `data-validation` | Adopt | From to_review |
| `data-warehouse-olap` | Adopt + Retarget | Focus on Redshift Serverless, Athena, Glue; de-emphasize Snowflake/BigQuery |
| `database-devops` | Exclude | Kubernetes + Terraform; both excluded |
| `database-implementation` | Adopt + Retarget | Extract Python/SQLAlchemy + TypeScript/Prisma; add DynamoDB-Toolbox |
| `database-migration` | Adopt + Retarget | Focus on Alembic/Prisma Migrate/Atlas; de-emphasize Kubernetes/Debezium |
| `database-monitoring` | Adopt + Retarget | Add DynamoDB CloudWatch metrics |
| `database-security` | Adopt + Retarget | Add DynamoDB IAM fine-grained access, VPC endpoints |
| `document-databases` | Adopt + Retarget | Focus on Amazon OpenSearch Service section; de-emphasize MongoDB |
| `dynamic-programming` | Adopt | From to_review — core for candidate-job matching |
| `e2e-testing` | Adopt | From to_review |
| `embedded-databases` | Adopt (conditional) | SQLite + Realm for React Native offline; evaluate with offline-first scope |
| `flutter-expert` | Adopt + Relocate | From to_review/relational-databases/; keep for Android architecture evaluation |
| `frontend-performance` | Adopt | From to_review |
| `gcp-architect` | Exclude | GCP only |
| `graph-algorithms` | Adopt | From to_review — bipartite matching for candidate-job fit |
| `graph-databases` | Exclude | DynamoDB graph patterns + graph-algorithms skill covers SkillSpoke graph needs |
| `ios-native` | Adopt + Relocate | From to_review/relational-databases/; confirmed iOS surface |
| `key-value-stores` | Adopt | From to_review |
| `mathematical-optimization` | Adopt | From to_review — match scoring + ranking calibration |
| `message-queues` | Adopt | From to_review |
| `microservices` | Adopt + Retarget | Emphasize Lambda-based microservices; K8s service discovery secondary-path |
| `migration-planner` | Adopt | From to_review |
| `mobile-performance` | Adopt + Relocate | From to_review/relational-databases/ |
| `mobile-security` | Adopt + Relocate | From to_review/relational-databases/ |
| `mobile-testing` | Adopt | From to_review |
| `monitoring-setup` | Adopt + Retarget | Add CloudWatch Lambda Insights, X-Ray, CDK alarm constructs |
| `multi-model-databases` | Exclude | DynamoDB covers multi-model |
| `newsql-distributed` | Exclude | DynamoDB + Aurora DSQL cover distributed SQL |
| `numerical-methods` | Adopt + Split | Extract security-primitives; retain for ML/optimization |
| `offline-first` | Adopt + Relocate | From to_review/relational-databases/ |
| `react-expert` | Adopt | From to_review |
| `react-native-expert` | Adopt + Relocate | From to_review/relational-databases/; pending Android architecture decision |
| `appsync` | Create new | GraphQL + async chat requirement |
| `async-api` | Create new | Chat feature + LLM streaming response |
| `graphql` | Create new | GraphQL where appropriate; AppSync-specific patterns |
| `dynamodb-single-table` | Create new | Deep single-table methodology beyond existing dynamodb skill |
| `elasticache-valkey` | Create new | Lambda + ElastiCache CDK integration; Valkey fork compatibility |
| `fastmcp-server` | Create new | FastMCP 2.0+ Python server development — not covered by mcp-server-builder |
| `bedrock-knowledge-bases` | Create new | Bedrock Knowledge Bases CDK/API; not covered by rag-architect |
| `cloudfront-waf` | Create new | CloudFront + WAF v2 CDK constructs |
| `cdk-constructs` | Create new | Advanced CDK: L2/L3 authoring, aspects, custom resources, CDK Pipelines |
| `webauthn-passkeys` | Create new | FIDO2/WebAuthn server + client (browser + React Native + Swift) |
| `python-lambda-chassis` | Create new | SkillSpoke shared Lambda chassis patterns |
| `taskfile` | Create new | go-task (Taskfile.yml) — SkillSpoke's build system |
| `incident-response` | Create new | Extracted from connection-management to_review skill |
| `security-primitives` | Create new | Extracted from numerical-methods to_review skill (JWT, hashing, API auth) |
| `react-native` | Create new | SkillSpoke-specific React Native; relocated from misparented location |
| `recommendation-systems` | Create new | Candidate-job matching: collaborative filtering, bipartite matching, Bedrock Titan embeddings |
| `opensearch` | Create new | Amazon OpenSearch Service: index design, k-NN vector search, CDK constructs |

| Category | Count |
|----------|-------|
| Keep as-is (existing) | 43 |
| Keep as-is (to_review, adopt) | 27 |
| Relocate (mobile skills from relational-databases/) | 8 |
| Retarget (existing) | 16 |
| Retarget (to_review) | 11 |
| Conditional / partial retarget | 2 |
| Create new | 18 |
| Fix + Retarget | 1 (senior-data-scientist) |
| Merge | 1 (aws-solution-architect) |
| Split | 2 (connection-management, numerical-methods) |
| Exclude (existing) | 2 |
| Exclude (to_review) | 7 |
| **Final target skill count** | **~127** |
