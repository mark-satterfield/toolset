# SDLC Workforce Agents

These agents implement the SDLC pipelines — PRD creation through deployment, plus cross-cutting documentation and governance — under separation-of-duties rules: every agent performs exactly one task category (plan, orchestrate, execute, approve, or test).

## Governance

| Agent | Category | Purpose |
| --- | --- | --- |
| sdlc-pipeline-orchestrator | orchestrate | Top-level workflow-only orchestrator for both SDLC pipelines |
| phase-gate-enforcer | approve | Referee for every phase gate in both workflows |
| constitutional-agent | approve | Appeals court for novel conflicts the Phase Gate Enforcer cannot resolve from existing rules |
| advantage-evaluator | approve | Evaluates competitive (non-constitutive) conflicts via speculative execution with rollback: lets the pipeline proceed under a flag, observes the outcome, then commits or reverts; rules every gate whose loops are spent — proceed with named residuals, or one directed revision. |
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

`prd-to-spec` reads what it takes from the PRD file with `depscore.py prd-parse`, assuming the PRD was
validated before its Epic was made ready, and dispatches none of these agents; the `prd-validation`
workflow runs on its own.

| Agent | Category | Purpose |
| --- | --- | --- |
| prd-validation-lead | orchestrate | Routes the PRD to all analysts concurrently, aggregates findings, and reports to Gate 1 |
| requirements-clarifier | plan | Identifies ambiguous, incomplete, or conflicting requirements |
| ambiguity-detector | test | Scans the PRD for vague quantifiers, missing boundary conditions, and unstated assumptions |
| requirements-conflict-detector | test | Identifies requirements that contradict each other |
| brd-traceability-auditor | test | Optional, informational only: maps PRD requirements to a supplied BRD's objectives; no verdict on the PRD |
| constraint-extractor | execute | Extracts technical constraints from the PRD |
| domain-boundary-validator | test | Confirms the PRD stays within a single bounded context |
| dependency-graph-extractor | execute | Produces the dependency manifest: services, APIs, events, data contracts |
| completeness-checker | test | Validates each requirement has an actor, an action, an observable outcome, and acceptance criteria. |
| nfr-analyst | plan | Extracts non-functional requirements |

## Architecture Analysis

The `architecture` workflow designs each Epic's change as a target and a delta version of the
architecture: the coordinator names each round's proposers, diagram authors, reviewers and cost
reviewers, the decider approves the target, the maintainer integrates it into the effective version
and the conformance reviewer checks the integration. `built-version` dispatches the maintainer and the
conformance reviewer again to correct the effective version from what a Story built.

| Agent | Category | Purpose |
| --- | --- | --- |
| architecture-decision-workflow-coordinator | orchestrate | Names, round by round, which proposers, reviewers, diagram authors and cost reviewers the architecture step dispatches next, sized to the PRD; the workflow script runs the dispatches. Process only: no design, review or approval authority. |
| integration-pattern-architect | plan | Analyzes integration options: event API patterns, API Gateway routes, sync vs |
| persistence-architecture-specialist | plan | Analyzes DynamoDB schema options, GSI/LSI strategies, single vs |
| security-architecture-designer | plan | Analyzes security approaches: IAM, Cognito flows, encryption, threat model |
| cdk-infrastructure-designer | plan | Analyzes CDK construct options, Lambda boundaries within the chassis, and layer packaging |
| event-schema-designer | execute | Designs event schemas within the event envelope the effective architecture describes |
| api-contract-designer | execute | Produces OpenAPI/GraphQL schema proposals. |
| cost-architecture-reviewer | plan | Estimates cost per architecture option and identifies cost cliffs |
| bounded-context-mapper | plan | Maps domain boundaries and identifies context relationships |
| domain-event-modeler | execute | Models domain events, event flows, and event contracts |
| ubiquitous-language-writer | execute | Captures the ubiquitous language for the bounded context: terms, definitions, and usage rules shared by the domain model and the code. |
| architecture-pattern-challenger | test | Generates a structurally different alternative for each proposal to force non-obvious paths |
| architecture-tradeoff-skeptic | test | Attacks trade-off ratings: hidden assumptions, optimistic estimates, unconsidered failure modes. |
| architecture-boundary-guardian | test | Validates that no proposal introduces cross-context coupling. |
| cost-impact-reviewer | test | Stress-tests cost estimates at 10x/100x/1000x scale |
| operational-readiness-reviewer | test | Evaluates operational burden of each proposal: monitoring, alerting, runbook complexity, on-call implications. |
| architecture-decider | approve | Decides, after the team has settled an Epic's draft target, whether it is approved, from the artifacts alone: approves the team's result, choosing where the team left competing solutions, or returns it to a named proposer with the missing due diligence. Generates no evidence of its own. |
| architecture-impact-analyst | test | Judges what an architecture change reaches: given the views an integration changed, created or deleted, finds every Epic, Story, Task and document citing those views or showing their elements, and rules each unaffected / not yet elaborated / elaborated-but-unbuilt / already-built. Read-only. No workflow currently dispatches it. |
| architecture-fitness-function-author | execute | Defines testable assertions from the owner's constraints and the patterns the effective architecture establishes, such as 'no service reads another service's table'. No workflow currently dispatches it. |
| architecture-diagram-author | execute | Draws architecture views of any type in the project's list of diagram and model types, at any scope, for the target or the effective version, from the design it is given. |
| c4-diagram-author | execute | Draws C4 views (Level 1 System Context, Level 2 Container, Level 3 Component) as Mermaid, for the target or the effective version of the architecture, from the design it is given. |
| uml-diagram-author | execute | Draws UML views (sequence, state, activity, class) as Mermaid, for the target or the effective version of the architecture, from the design it is given. |
| architecture-maintainer | execute | Keeps the effective version of the architecture current: integrates an approved target into the arc42 folders, and corrects the effective version from what was built, updating or deleting every view that shows a changed element, found through the catalog. Never writes section 2. |
| architecture-conformance-reviewer | test | Checks ONE integration of an approved target into the effective version and reports findings without fixing them: the target was applied exactly, every view the catalog lists for each changed element was updated, and no contradicting content was left. |
| graphql-schema-designer | execute | Designs GraphQL schema proposals for the AppSync track, parallel to the REST/API Gateway contract track |
| failure-mode-analyst | plan | Proactively models failure modes for each architecture proposal: DynamoDB throttling, duplicate event delivery, downstream unavailability, partial-batch failures, poison messages |

## TRD Authoring (Phase 2.5)

| Agent | Category | Purpose |
| --- | --- | --- |
| trd-authoring-lead | orchestrate | Routes TRD maker output to checkers and findings back to makers until checkers pass, invokes the decider on deadlock, then assembles the Gate 2b packet. No workflow currently dispatches it. |
| trd-author | execute | Authors the Technical Requirements Document — the CARRIER that takes the architecture's obligations (uptime, latency, maintainability, security, failover, DR, infrastructure/CDK, observability) into the build chain, alongside the PRD requirements needing technical elaboration. Cites the architecture rather than restating it, so a correct TRD is often very short. |
| trd-validator | test | Validates each TRD technical requirement is unambiguous, testable, and feasible within the owner's constraints and the effective architecture, flagging any requirement that contradicts the architecture. No workflow currently dispatches it. |
| prd-trd-traceability-verifier | test | Builds and checks the TRD's source traceability matrix: every TRD requirement anchored to a PRD requirement or an architecture view, every PRD requirement needing elaboration answered, genuine scope drift flagged. Not a 1:1 relation. No workflow currently dispatches it. |
| trd-decider | approve | Rules on competing TRD approaches, maker-checker deadlocks, and checker conflicts routed by trd-authoring-lead. No workflow currently dispatches it. |

## Spec Authoring

| Agent | Category | Purpose |
| --- | --- | --- |
| spec-authoring-lead | orchestrate | Routes maker output to checkers and checker findings back to makers until checkers pass, then routes to Gate 3 |
| acceptance-criteria-writer | execute | Writes testable acceptance criteria per requirement (given/when/then), specific enough for test agents to derive tests from. |
| definition-of-done-enforcer | execute | Writes the Definition of Done as independently verifiable statements, not checklists. |
| api-specification-author | execute | Produces the three interface contract artifacts from the contract drafts in one pass: the API specification (schemas, error codes, rate limits, examples), the event contracts (envelope format, publishing conditions, consumers, retry and DLQ behavior), and the error-handling specification (per failure mode, noting what the chassis handles). |
| data-model-specification-author | execute | Writes DynamoDB table specifications: keys, GSI/LSI, access patterns, capacity estimates. |
| prd-alignment-verifier | test | Verifies traceability: PRD requirement to spec section to acceptance criteria |
| acceptance-criteria-reviewer | test | Validates acceptance criteria are testable, complete, and unambiguous. |
| openapi-contract-reviewer | test | Validates API specifications match the architecture decisions and established contract patterns. |
| event-schema-reviewer | test | Validates event schemas conform to the event envelope the architecture describes. |
| dynamodb-schema-access-pattern-reviewer | test | Validates the specified access patterns are implementable and performant. |
| graphql-schema-reviewer | test | Validates GraphQL schemas match the architecture decisions and AppSync contract patterns. |
| spec-decider | approve | Rules on every spec artifact the independent reviewer rejects; the owning maker enacts a ruling that sends its artifact back |

## Task Decomposition

| Agent | Category | Purpose |
| --- | --- | --- |
| task-decomposition-lead | orchestrate | Routes the decomposition pipeline: decompose, size, map, sequence, score, validate. No workflow currently dispatches it. |
| task-decomposer | execute | Breaks the spec into tasks, each a coherent piece of the Story's work one agent can test and build in one session. |
| task-dependency-mapper | execute | Identifies inter-task dependencies |
| wsjf-scorer | execute | Judges the job size of Tasks on the WSJF rubric's Fibonacci scale — the one judged input; value and time criticality are inherited from the Epic and RR-OE is computed, so the WSJF itself is arithmetic. No workflow currently dispatches it; task-decomposer sizes the Tasks it decomposes. |
| wsjf-scoring-reviewer | test | Validates WSJF scores are consistent and defensible. No workflow currently dispatches it. |
| user-story-writer | execute | Writes user stories per task with acceptance criteria drawn from the spec. |
| user-story-reviewer | test | Validates stories are complete, testable, and properly scoped. |
| beads-format-validator | test | Validates Beads issue format: title, acceptance criteria, DoD, WSJF score, dependencies, spec link. No workflow currently dispatches it. |

## PRD Reconciliation

| Agent | Category | Purpose |
| --- | --- | --- |
| prd-reality-reconciler | test | Details an approved architecture delta for ONE repository: for each delta item placed there (one element the delta shows), compares what the delta makes it with the code on the repository's main and gives it one status — `add`, `modify`, `remove`, `done` or `planned-elsewhere` — each citing file:line (planned-elsewhere names the open bead that plans it), and reports upstream dependency changes. Also writes the architecture step's survey, and in built-version records each difference between a Story's code and the effective views in `built/<subject>/`. |

## Spec Freshness

| Agent | Category | Purpose |
| --- | --- | --- |
| spec-freshness-lead | orchestrate | Routes freshness checks to the validators and aggregates results for the gate. No workflow currently dispatches it. |
| spec-currency-validator | test | Validates the spec still matches current project reality before implementation begins. No workflow currently dispatches it. |
| dependency-change-detector | test | Detects dependency version or contract changes since the spec was written. No workflow currently dispatches it. |

## Workspace

The worktree every writing phase then operates in. One agent CREATES it; a SECOND, separately
dispatched one reports what git says about it, and `workflows/workspace.js` rules on the two
accounts. The verifier is told where to look and nothing about what was claimed — a checker
shown the answer is not a checker.

| Agent | Category | Purpose |
| --- | --- | --- |
| git-worktree-provisioner (role played by github-actions-pipeline-implementer) | execute | Fetches, fast-forwards, reuses an existing tree for the bead or cuts a new one on a feature branch. |
| worktree-independent-verifier | test | Independently reports the raw git facts about a path — git-dir, git-common-dir, branch, and the caller repo's common-dir and default branch — so the workspace script can compare two separately-obtained accounts. |

## Test Design

| Agent | Category | Purpose |
| --- | --- | --- |
| test-design-lead | orchestrate | Routes spec acceptance criteria to the right test writers, confirms Red (all new tests fail), and reports to Gate 2a. |
| tdd-unit-test-generator | test | Writes failing unit tests from spec acceptance criteria before implementation exists. |
| consumer-driven-contract-test-writer | test | Writes consumer-driven contract tests ensuring API consumers and providers agree. |
| security-test-case-designer | test | Designs security test cases from the threat model: abuse cases, negative paths, authorization matrices. |
| aws-integration-test-writer | test | Writes integration tests against AWS infrastructure covering the event delivery path the effective architecture describes, hop by hop. |
| playwright-e2e-web-test-writer | test | Writes Playwright end-to-end web tests for UI and API flows. |
| performance-benchmark-writer | test | Writes performance benchmarks with explicit budgets derived from the NFRs. |
| test-plan-strategy-reviewer | test | Reviews the test plan strategy: pyramid balance, risk coverage, environment needs. |
| test-coverage-gap-reviewer | test | Before Red authors anything, names which acceptance criteria existing tests already encode and which are gaps; when none is a gap, runs only those tests and rules red / already-satisfied / not-encoded. Dispatched by tdd-red. |
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
| implementation-lead | orchestrate | Selects the implementer(s) whose specialties cover a Task, in build order, from the Task's build contract; `tdd-green` dispatches them. |
| chassis-extension-implementer | execute | Implements Lambda handlers as chassis superclass extensions for API endpoints and event consumers. |
| api-gateway-cdk-implementer | execute | Implements API Gateway resources, methods, and authorizers in CDK. |
| event-api-client-implementer | execute | Implements clients publishing events through the publishing path and envelope the effective architecture describes |
| dynamodb-access-layer-implementer | execute | Implements DynamoDB access patterns from the data model specification: single-table patterns, GSI queries, conditional writes. |
| event-driven-consumer-implementer | execute | Implements event consumers on the delivery path the effective architecture describes |
| power-tools-configuration-implementer | execute | Configures Lambda Power Tools: structured logging, tracing, metrics, idempotency, validation |
| cognito-lambda-trigger-implementer | execute | Implements Cognito Lambda triggers for authentication flows. |
| nextjs-component-implementer | execute | Implements the non-visual React/Next.js work (state, data fetching, routing); visual UI goes to cds:cds-ui-author. |
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
| appsync-cdk-implementer | execute | Implements AppSync GraphQL APIs in CDK: schema wiring, resolvers, data sources, authorization. |
| payments-integration-implementer | execute | Implements payment features against Stripe: checkout sessions, webhook handlers, subscription lifecycle, refunds, and idempotent payment operations |
| email-notification-implementer | execute | Implements transactional and notification email features: responsive email templates, rendering pipelines, delivery via AWS messaging services, bounce and complaint handling. |
| mcp-server-implementer | execute | Implements MCP servers hosted on AWS, including AgentCore Gateway-fronted deployments: tool definitions and schemas, authorization, transport configuration, and the CDK wiring to deploy them. |

## Code Quality

| Agent | Category | Purpose |
| --- | --- | --- |
| code-quality-lead | orchestrate | Routes refactor work, verifies tests stay green after every change, and reports to Gate 2c. No workflow currently dispatches it: tdd-refactor takes the optimizer selection from complexity-analyzer. |
| complexity-analyzer | plan | Analyzes complexity and duplication, and names the fewest optimizer specialties the change calls for, in run order |
| code-refactoring-specialist | execute | Restructures existing code for clarity and cohesion without changing behavior. |
| lambda-performance-optimizer | execute | Optimizes Lambda cold start, memory sizing, and hot paths without breaking tests. |
| dynamodb-cost-optimizer | execute | Optimizes DynamoDB capacity, access patterns, and cost without changing behavior. |
| code-style-and-linting-enforcer | execute | Runs the project linters and applies formatting and style fixes. |
| code-correctness-reviewer | test | Reviews refactored code for correctness regressions and behavioral drift. |
| frontend-performance-optimizer | execute | Optimizes frontend performance without breaking tests: bundle size, rendering paths, Core Web Vitals. |
| accessibility-validator | test | Validates UI changes against WCAG 2.2 Level A and AA: automated scans plus heuristics for contrast, keyboard navigation, ARIA semantics, focus management, and screen-reader flows. No workflow currently dispatches it; it reports and never edits, so it is not a refactor optimizer |

## Integration Testing

| Agent | Category | Purpose |
| --- | --- | --- |
| integration-testing-lead | orchestrate | Routes test runs, aggregates results, reports to Gate 3, and routes escalations to the target the Root Cause Analyst identifies. |
| aws-integration-test-runner | test | Runs the AWS integration test suites and reports structured results. |
| event-flow-tester | test | Tests event flows end-to-end through every hop of the event delivery path the effective architecture describes. |
| data-consistency-checker | test | Verifies data consistency across services and stores after test runs. |
| cross-service-contract-tester | test | Runs contract tests across service and repository boundaries. |
| test-environment-orchestrator | execute | Provisions and resets the integration test environments. |
| root-cause-analyst | plan | Diagnoses a bug bead read-only — reproduction, root cause, enumerated defects, affected files, blast radius, touched surfaces, repository. Dispatched by bug-triage as its diagnosis step; integration no longer dispatches it. |
| flaky-test-detector | test | Identifies intermittent test failures and their root causes. No workflow currently dispatches it. |
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
| cdk-infrastructure-drift-detector | test | Detects drift between deployed infrastructure and the CDK stacks. |
| slo-error-budget-designer | plan | Designs SLOs and error budgets for the deployed feature. No workflow currently dispatches it. |
| smoke-test-author | test | Writes post-deployment smoke tests. |
| production-readiness-review-facilitator | orchestrate | Coordinates the production readiness review: collects required artifacts, routes them to reviewers, and assembles the readiness packet |
| finops-analyst | plan | Analyzes the cost posture of the feature before deployment: unit economics, scaling cost curves, budget impact. No workflow currently dispatches it. |
| incident-response-runbook-designer | execute | Produces operational runbooks for the deployed feature: incident response, rollback steps, disaster recovery. No workflow currently dispatches it. |
| deployment-strategy-decider | approve | Receives deployment analyses — rollout strategies, risk assessments, FinOps recommendations — routed by deployment-lead. No workflow currently dispatches it. |

## Documentation

| Agent | Category | Purpose |
| --- | --- | --- |
| workflow-command-runner | execute | Runs one checked workflow command and relays its compact receipt without interpreting payloads. |
| filing-clerk | execute | Searches for the canonical documentation home before filing; placement-only workflow requests return a path without writing. |
| documentation-lead | orchestrate | Routes documentation work triggered by shipped changes, tracks which artifacts lack current documentation, and reports documentation currency to the production readiness review |
| api-documentation-writer | execute | Generates human-readable API documentation from OpenAPI and GraphQL specs: endpoint guides, examples, SDK snippets. |
| readme-writer | execute | Writes and maintains README files for repositories and directories: setup instructions, usage, onboarding flows. |
| changelog-writer | execute | Generates changelog entries from merged work: conventional commit parsing, semantic version notes. |
| user-guide-writer | execute | Writes user-facing feature documentation and guides from specs and shipped behavior. |
| documentation-currency-auditor | test | Audits that documentation was updated when code shipped, and names the roster writer that owns each stale doc |
| documentation-accuracy-reviewer | test | Reviews produced documentation against actual shipped behavior for accuracy and completeness. No workflow currently dispatches it. |

## Standalone

- `polyrepo-steward` — caretaker and librarian of the project's repositories: answers count/ownership/structure/status questions from live facts it checks against the repositories and GitHub, and performs all repository work — create, deprecate, archive, rebase, search, `AGENTS.md` propagation, template upkeep. Reached via the `polyrepo-router` skill or the `/polyrepo-steward` command.

## Named workflow helpers

- **test-command-resolver** — Resolves the applicable test command from repository instructions and configuration without running tests.
- **test-failure-parser** — Extracts concrete failing test identifiers and errors from a saved test log without rerunning tests.
- **prd-validation-analyst** — Independently checks a PRD against the caller supplied requirement lenses, with no authoring authority.
- **cds-finding-reviewer** — Independently classifies findings from the CDS audit against the configured design system.
- **cds-ui-implementer** — Implements assigned UI using the CDS plugin and its existing design system, supplied bundle and review contracts.

## Cumulative regression assurance

| Agent | Category | Purpose |
| --- | --- | --- |
| regression-impact-assessor | plan | Maps affected components and current requirements across PRDs to retained tests and executable evidence |
| regression-coverage-reviewer | test | Independently checks discovery, layer coverage, preservation and source-backed supersession |
