# SDLC Workforce Agents

These agents implement the SDLC pipelines — PRD creation through deployment, plus cross-cutting documentation and governance — under separation-of-duties rules: every agent performs exactly one task category (plan, orchestrate, execute, approve, or test).

## Governance

| Agent | Category | Purpose |
| --- | --- | --- |
| sdlc-pipeline-orchestrator | orchestrate | Top-level workflow-only orchestrator for both SDLC pipelines |
| phase-gate-enforcer | approve | Referee for every phase gate in both workflows |
| constitutional-agent | approve | Appeals court for novel conflicts the Phase Gate Enforcer cannot resolve from existing rules |
| advantage-evaluator | approve | Evaluates competitive (non-constitutive) conflicts via speculative execution with rollback: lets the pipeline proceed under a flag, observes the outcome, then commits or reverts |
| context-curator | execute | Owns context integrity across the workforce: assembles role-specific context packets per the least-context principle, and guarantees constitutive constraints survive context compaction verbatim — they are never summarized away |

## PRD Creation

| Agent | Category | Purpose |
| --- | --- | --- |
| prd-creation-lead | orchestrate | Routes stakeholder requests through intake, persona, OKR, and PRD drafting work, then hands the draft PRD to prd-validation-lead |
| stakeholder-request-intake-writer | execute | Converts raw stakeholder requests into a structured intake brief: requestor, problem, desired outcome, constraints, urgency. |
| prd-writer | execute | Produces the full PRD from the intake brief, persona profiles, and OKR cascade: feature scope, requirements, success metrics, competitive context. |
| persona-profile-writer | execute | Generates data-driven persona profiles from research inputs: behavioral segments, jobs-to-be-done, empathy maps. |
| okr-writer | execute | Derives the OKR cascade from strategy documents and the intake brief: objectives, measurable key results, leading versus lagging indicators. |

## PRD Validation

| Agent | Category | Purpose |
| --- | --- | --- |
| prd-validation-lead | orchestrate | Routes the PRD to all analysts concurrently, aggregates findings, and reports to Gate 1 |
| requirements-clarifier | plan | Identifies ambiguous, incomplete, or conflicting requirements |
| ambiguity-detector | test | Scans the PRD for vague quantifiers, missing boundary conditions, and unstated assumptions |
| requirements-conflict-detector | test | Identifies requirements that contradict each other or the BRD |
| brd-traceability-auditor | test | Validates that every PRD requirement traces to a BRD objective |
| constraint-extractor | execute | Extracts technical constraints from the PRD |
| domain-boundary-validator | test | Confirms the PRD stays within a single bounded context |
| dependency-graph-extractor | execute | Produces the dependency manifest: services, APIs, events, data contracts |
| completeness-checker | test | Validates each requirement has an actor, an action, an observable outcome, and acceptance criteria. |
| nfr-analyst | plan | Extracts non-functional requirements |

## Architecture Analysis

| Agent | Category | Purpose |
| --- | --- | --- |
| architecture-decision-workflow-coordinator | orchestrate | Routes analysis tasks to the proposals sub-team, routes proposals to the challenge sub-team, collects all outputs, and routes them to the Architecture Decider |
| integration-pattern-architect | plan | Analyzes integration options: event API patterns, API Gateway routes, sync vs |
| persistence-architecture-specialist | plan | Analyzes DynamoDB schema options, GSI/LSI strategies, single vs |
| security-architecture-designer | plan | Analyzes security approaches: IAM, Cognito flows, encryption, threat model |
| cdk-infrastructure-designer | plan | Analyzes CDK construct options, Lambda boundaries within the chassis, and layer packaging |
| event-schema-designer | execute | Designs event schemas within the event API envelope format |
| api-contract-designer | execute | Produces OpenAPI/GraphQL schema proposals |
| cost-architecture-reviewer | plan | Estimates cost per architecture option and identifies cost cliffs |
| bounded-context-mapper | plan | Maps domain boundaries and identifies context relationships |
| domain-event-modeler | execute | Models domain events, event flows, and event contracts |
| ubiquitous-language-writer | execute | Captures the ubiquitous language for the bounded context: terms, definitions, and usage rules shared by the domain model and the code. |
| architecture-pattern-challenger | test | Generates a structurally different alternative for each proposal to force non-obvious paths |
| architecture-tradeoff-skeptic | test | Attacks trade-off ratings: hidden assumptions, optimistic estimates, unconsidered failure modes. |
| architecture-boundary-guardian | test | Validates that no proposal introduces cross-context coupling. |
| adr-completeness-reviewer | test | Cross-references proposals against existing ADRs |
| cost-impact-reviewer | test | Stress-tests cost estimates at 10x/100x/1000x scale |
| operational-readiness-reviewer | test | Evaluates operational burden of each proposal: monitoring, alerting, runbook complexity, on-call implications. |
| architecture-decider | approve | Receives all analyses, challenges, and cost data |
| adr-writer | execute | Produces ADR drafts from the Decider's decisions: context, decision, consequences, status. |
| architecture-fitness-function-author | execute | Defines testable assertions from architecture decisions, such as 'all events publish through the event API' and 'all Lambdas extend the chassis'. |
| architecture-diagram-author | execute | Produces architecture diagrams from the decided design in the project's standard diagram format. |
| c4-diagram-author | execute | Renders the decided design as C4 Mermaid diagrams (Level 1 Context, Level 2 Container, Level 3 Component) for the SAD. |
| uml-diagram-author | execute | Renders the decided behaviours and structures as UML Mermaid diagrams (sequence, class, state) for the SAD. |
| sad-maintainer | execute | Consolidates the decided constraints, solution strategy, cross-cutting concepts, and accepted ADRs into the single living arc42 Software Architecture Document, updating current state in place. |
| sad-source-extractor | execute | Extracts the SAD's section-2/4/8/9 source feed — Constraints, Solution Strategy, Cross-cutting Concepts, Architecture Decisions — into one typed, stably-identified packet for TRD and spec authoring. |
| sad-conformance-reviewer | test | Verifies the living SAD against the arc42 section model and reports conformance findings without fixing them. |
| graphql-schema-designer | execute | Designs GraphQL schema proposals for the AppSync track, parallel to the REST/API Gateway contract track |
| failure-mode-analyst | plan | Proactively models failure modes for each architecture proposal: DynamoDB throttling, duplicate event delivery, downstream unavailability, partial-batch failures, poison messages |

## TRD Authoring (Phase 2.5)

| Agent | Category | Purpose |
| --- | --- | --- |
| trd-authoring-lead | orchestrate | Routes TRD maker output to checkers and findings back to makers until checkers pass, invokes the decider on deadlock, then assembles the Gate 2b packet |
| trd-author | execute | Authors the Technical Requirements Document that translates the source PRD into technical requirements, NFR derivations, and interface and data obligations bounded by the SAD extract. |
| trd-validator | test | Validates each TRD technical requirement is unambiguous, testable, and feasible within the SAD constraints and decisions, flagging any requirement that contradicts the architecture. |
| prd-trd-traceability-verifier | test | Builds and checks the PRD-to-TRD traceability matrix proving a 1:1 relation, flagging orphans on either side and scope drift. |
| trd-decider | approve | Rules on competing TRD approaches, maker-checker deadlocks, and checker conflicts routed by trd-authoring-lead |

## Spec Authoring

| Agent | Category | Purpose |
| --- | --- | --- |
| spec-authoring-lead | orchestrate | Routes maker output to checkers and checker findings back to makers until checkers pass, then routes to Gate 3 |
| acceptance-criteria-writer | execute | Writes testable acceptance criteria per requirement (given/when/then), specific enough for test agents to derive tests from. |
| definition-of-done-enforcer | execute | Writes the Definition of Done as independently verifiable statements, not checklists. |
| api-specification-author | execute | Produces detailed API specifications from contract drafts: schemas, error codes, rate limits, examples. |
| event-contract-author | execute | Writes event schemas within the event API envelope format: publishing conditions, consumers, retry and DLQ behavior. |
| data-model-specification-author | execute | Writes DynamoDB table specifications: keys, GSI/LSI, access patterns, capacity estimates. |
| error-handling-specification-author | execute | Specifies error handling per failure mode, noting which behavior is chassis-handled and which is custom. |
| prd-alignment-verifier | test | Verifies traceability: PRD requirement to spec section to acceptance criteria |
| acceptance-criteria-reviewer | test | Validates acceptance criteria are testable, complete, and unambiguous. |
| openapi-contract-reviewer | test | Validates API specifications match the architecture decisions and established contract patterns. |
| event-schema-reviewer | test | Validates event schemas conform to the event API envelope format. |
| dynamodb-schema-access-pattern-reviewer | test | Validates the specified access patterns are implementable and performant. |
| graphql-schema-reviewer | test | Validates GraphQL schemas match the architecture decisions and AppSync contract patterns. |
| spec-decider | approve | Receives competing spec approaches, maker-checker deadlocks, and checker conflict reports routed by spec-authoring-lead |

## Task Decomposition

| Agent | Category | Purpose |
| --- | --- | --- |
| task-decomposition-lead | orchestrate | Routes the decomposition pipeline: decompose, size, map, sequence, score, validate |
| task-decomposer | execute | Breaks the spec into tasks: one chassis extension, one endpoint, or one event handler per task. |
| task-dependency-mapper | execute | Identifies inter-task dependencies |
| wsjf-scorer | execute | Scores each task: (value + time criticality + risk reduction) divided by size. |
| wsjf-scoring-reviewer | test | Validates WSJF scores are consistent and defensible. |
| user-story-writer | execute | Writes user stories per task with acceptance criteria drawn from the spec. |
| user-story-reviewer | test | Validates stories are complete, testable, and properly scoped. |
| beads-format-validator | test | Validates Beads issue format: title, acceptance criteria, DoD, WSJF score, dependencies, spec link. |

## Spec Freshness

| Agent | Category | Purpose |
| --- | --- | --- |
| spec-freshness-lead | orchestrate | Routes freshness checks to the validators and aggregates results for the gate. |
| spec-currency-validator | test | Validates the spec still matches current project reality before implementation begins. |
| dependency-change-detector | test | Detects dependency version or contract changes since the spec was written. |
| adr-currency-checker | test | Checks that the ADRs the spec relies on are still current and unsuperseded. |

## Test Design

| Agent | Category | Purpose |
| --- | --- | --- |
| test-design-lead | orchestrate | Routes spec acceptance criteria to the right test writers, confirms Red (all new tests fail), and reports to Gate 2a. |
| tdd-unit-test-generator | test | Writes failing unit tests from spec acceptance criteria before implementation exists. |
| consumer-driven-contract-test-writer | test | Writes consumer-driven contract tests ensuring API consumers and providers agree. |
| security-test-case-designer | test | Designs security test cases from the threat model: abuse cases, negative paths, authorization matrices. |
| aws-integration-test-writer | test | Writes integration tests against AWS infrastructure covering the event API to EventBridge to SQS to Lambda chain. |
| playwright-e2e-web-test-writer | test | Writes Playwright end-to-end web tests for UI and API flows. |
| performance-benchmark-writer | test | Writes performance benchmarks with explicit budgets derived from the NFRs. |
| test-plan-strategy-reviewer | test | Reviews the test plan strategy: pyramid balance, risk coverage, environment needs. |
| test-coverage-gap-reviewer | test | Reviews planned tests against spec acceptance criteria and flags coverage gaps. |
| xcuitest-writer | test | Writes failing XCUITest suites for iOS features from spec acceptance criteria. |
| espresso-test-writer | test | Writes failing Espresso test suites for Android features from spec acceptance criteria. |
| mobile-e2e-test-writer | test | Writes failing Detox and Maestro end-to-end tests for React Native and cross-platform mobile flows. |
| ml-evaluation-tester | test | Writes and runs evaluation suites for ML components: matching quality, recommendation relevance, embedding drift, regression thresholds. |
| data-pipeline-test-writer | test | Writes failing tests for data pipelines: ETL correctness, CDC ordering, data quality assertions, replay safety. |
| test-isolation-specialist | test | Validates test independence: no shared mutable state, order-independent execution, isolated fixtures |
| test-strategy-decider | approve | Receives test strategy analyses and reviewer findings routed by test-design-lead |

## Implementation

| Agent | Category | Purpose |
| --- | --- | --- |
| implementation-lead | orchestrate | Routes Beads tasks to the implementer sub-teams the feature requires, enforces hard constraints before any file is written, and reports to Gate 2b. |
| chassis-extension-implementer | execute | Implements Lambda handlers as chassis superclass extensions for API endpoints and event consumers. |
| api-gateway-cdk-implementer | execute | Implements API Gateway resources, methods, and authorizers in CDK Python. |
| event-api-client-implementer | execute | Implements clients that publish through the central event API endpoint using the standardized envelope |
| dynamodb-access-layer-implementer | execute | Implements DynamoDB access patterns from the data model specification: single-table patterns, GSI queries, conditional writes. |
| event-driven-consumer-implementer | execute | Implements event consumers that receive from SQS via the EventBridge-rule-to-SQS-to-Lambda chain |
| power-tools-configuration-implementer | execute | Configures Lambda Power Tools: structured logging, tracing, metrics, idempotency, validation |
| cognito-lambda-trigger-implementer | execute | Implements Cognito Lambda triggers for authentication flows. |
| nextjs-component-implementer | execute | Implements React/Next.js components for web UI features. |
| appsync-client-subscription-implementer | execute | Implements AppSync client subscriptions for real-time web features. |
| matching-algorithm-implementer | execute | Implements matching and recommendation algorithm components for ML features. |
| vector-search-embeddings-implementer | execute | Implements vector search and embeddings components for ML features. |
| ios-swiftui-implementer | execute | Implements iOS features in SwiftUI — including StoreKit, CoreML, and WebAuthn integration — to make failing XCUITest suites pass. |
| android-compose-implementer | execute | Implements Android features in Kotlin and Jetpack Compose — including ML Kit integration — to make failing Espresso suites pass. |
| react-native-implementer | execute | Implements React Native features for cross-platform mobile flows to make failing Detox and Maestro tests pass. |
| recommendation-engine-implementer | execute | Implements recommendation engine components for ML features. |
| bedrock-integration-implementer | execute | Implements Bedrock foundation-model integrations: model invocation, prompt assembly, embeddings generation. |
| behavioral-signals-implementer | execute | Implements behavioral signal capture and the feature pipelines that feed matching and recommendation models. |
| llm-observability-implementer | execute | Implements LLM observability: prompt and response logging, token and cost metrics, quality signals, drift alerts. |
| glue-etl-implementer | execute | Implements Glue ETL jobs for batch data processing. |
| kinesis-stream-implementer | execute | Implements Kinesis stream producers and consumers for streaming data. |
| dynamodb-streams-cdc-implementer | execute | Implements change data capture from DynamoDB Streams. |
| s3-data-lake-implementer | execute | Implements S3 data lake layout, partitioning, and lifecycle policies. |
| athena-redshift-analytics-implementer | execute | Implements Athena queries and Redshift analytics models over the data lake. |
| webauthn-implementer | execute | Implements WebAuthn passkey flows across web clients and the Cognito-backed auth stack. |
| appsync-cdk-implementer | execute | Implements AppSync GraphQL APIs in CDK Python: schema wiring, resolvers, data sources, authorization. |
| payments-integration-implementer | execute | Implements payment features against Stripe: checkout sessions, webhook handlers, subscription lifecycle, refunds, and idempotent payment operations |
| email-notification-implementer | execute | Implements transactional and notification email features: responsive email templates, rendering pipelines, delivery via AWS messaging services, bounce and complaint handling. |
| mcp-server-implementer | execute | Implements MCP servers hosted on AWS, including AgentCore Gateway-fronted deployments: tool definitions and schemas, authorization, transport configuration, and the CDK wiring to deploy them. |

## Code Quality

| Agent | Category | Purpose |
| --- | --- | --- |
| code-quality-lead | orchestrate | Routes refactor work, verifies tests stay green after every change, and reports to Gate 2c. |
| complexity-analyzer | plan | Analyzes complexity and duplication |
| code-refactoring-specialist | execute | Restructures existing code for clarity and cohesion without changing behavior. |
| lambda-performance-optimizer | execute | Optimizes Lambda cold start, memory sizing, and hot paths without breaking tests. |
| dynamodb-cost-optimizer | execute | Optimizes DynamoDB capacity, access patterns, and cost without changing behavior. |
| code-style-and-linting-enforcer | execute | Runs the project linters and applies formatting and style fixes. |
| code-correctness-reviewer | test | Reviews refactored code for correctness regressions and behavioral drift. |
| frontend-performance-optimizer | execute | Optimizes frontend performance without breaking tests: bundle size, rendering paths, Core Web Vitals. |
| accessibility-validator | test | Validates UI changes against WCAG 2.2 Level A and AA: automated scans plus heuristics for contrast, keyboard navigation, ARIA semantics, focus management, and screen-reader flows |

## Integration Testing

| Agent | Category | Purpose |
| --- | --- | --- |
| integration-testing-lead | orchestrate | Routes test runs, aggregates results, reports to Gate 3, and routes escalations to the target the Root Cause Analyst identifies. |
| aws-integration-test-runner | test | Runs the AWS integration test suites and reports structured results. |
| event-flow-tester | test | Tests event flows end-to-end through the event API to EventBridge to SQS to Lambda chain. |
| data-consistency-checker | test | Verifies data consistency across services and stores after test runs. |
| cross-service-contract-tester | test | Runs contract tests across service and repository boundaries. |
| test-environment-orchestrator | execute | Provisions and resets the integration test environments. |
| root-cause-analyst | plan | Determines whether a failure is code, test, environment, or architecture — and therefore which team the finding escalates to |
| flaky-test-detector | test | Identifies intermittent test failures and their root causes |
| cross-repo-integration-test-coordinator | orchestrate | Coordinates integration testing across repository boundaries: sequences cross-repo test runs over the event chain, aligns environment state between repos, and routes results back to integration-testing-lead |

## Adversarial Validation

| Agent | Category | Purpose |
| --- | --- | --- |
| adversarial-review-loop-supervisor | orchestrate | Sequences the adversarial loop — testers attack, the Adjudicator rules, valid findings route back to implementation — until the Adjudicator passes or the loop limit triggers escalation. |
| injection-attack-tester | test | Probes the project's own endpoints for injection paths (SQL, NoSQL, command, template) |
| auth-bypass-tester | test | Attempts authentication bypass against the project's own auth flows in test environments |
| permission-escalation-tester | test | Attempts privilege and permission escalation within the project's own IAM and authorization model |
| race-condition-tester | test | Probes concurrent flows for race conditions and idempotency gaps |
| contract-violation-tester | test | Sends contract-violating inputs across the project's own service boundaries |
| dependency-cve-auditor | test | Audits Python and Node dependencies for known CVEs and scores severity. |
| dos-resilience-tester | test | Evaluates resilience to load and resource-exhaustion patterns within designated test environments only |
| data-exposure-scanner | test | Scans the project's own responses, logs, and storage for unintended data exposure. |
| infrastructure-security-scanner | test | Scans IaC and deployed test infrastructure for security misconfigurations. |
| adversarial-critique-adjudicator | approve | Decides the severity of each adversarial finding and whether it is constitutive (hard stop) or competitive (plays advantage) |

## Deployment

| Agent | Category | Purpose |
| --- | --- | --- |
| deployment-lead | orchestrate | Routes the deployment sequence, validates preconditions at each step, and reports to Gate 5. |
| cdk-stack-author | execute | Authors AWS CDK stacks in Python for the feature's infrastructure. |
| github-actions-pipeline-implementer | execute | Implements GitHub Actions workflows: OIDC auth, caching, build, test, and deploy stages. |
| wave-deployment-sequencer | execute | Executes wave-based deployments in the approved cross-repo order with precondition checks per wave. |
| cdk-infrastructure-drift-detector | test | Detects drift between deployed infrastructure and the CDK stacks. |
| slo-error-budget-designer | plan | Designs SLOs and error budgets for the deployed feature. |
| smoke-test-author | test | Writes post-deployment smoke tests. |
| production-readiness-review-facilitator | orchestrate | Coordinates the production readiness review: collects required artifacts, routes them to reviewers, and assembles the readiness packet |
| finops-analyst | plan | Analyzes the cost posture of the feature before deployment: unit economics, scaling cost curves, budget impact |
| incident-response-runbook-designer | execute | Produces operational runbooks for the deployed feature: incident response, rollback steps, disaster recovery. |
| deployment-strategy-decider | approve | Receives deployment analyses — wave order options, rollout strategies, risk assessments, FinOps recommendations — routed by deployment-lead |

## Documentation

| Agent | Category | Purpose |
| --- | --- | --- |
| documentation-lead | orchestrate | Routes documentation work triggered by shipped changes, tracks which artifacts lack current documentation, and reports documentation currency to the production readiness review |
| api-documentation-writer | execute | Generates human-readable API documentation from OpenAPI and GraphQL specs: endpoint guides, examples, SDK snippets. |
| readme-writer | execute | Writes and maintains README files for repositories and directories: setup instructions, usage, onboarding flows. |
| changelog-writer | execute | Generates changelog entries from merged work: conventional commit parsing, semantic version notes. |
| user-guide-writer | execute | Writes user-facing feature documentation and guides from specs and shipped behavior. |
| documentation-currency-auditor | test | Audits that documentation was updated when code shipped |
| documentation-accuracy-reviewer | test | Reviews produced documentation against actual shipped behavior for accuracy and completeness. |

## Standalone

- `polyrepo-steward` — caretaker and librarian of the project's repositories: reads and maintains the polyrepo manifest and knowledge store, answers count/ownership/structure questions, and performs all repository create/update/deprecate/list/search work. Reached via the `polyrepo-router` skill or the `/polyrepo-steward` command.
