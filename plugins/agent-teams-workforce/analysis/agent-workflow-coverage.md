# Agent → Workflow Coverage (agent-teams-workforce)

Source: `plugins/agent-teams-workforce/workflows/*.js` (26 workflow scripts) and `agents/*.md` (173 SDLC agents, excluding `README.md` and `agents-file.md`).

## How invocation was determined

Workflows are JavaScript scripts that spawn agents through `agent(prompt, { agentType: 'agent-teams-workforce:<name>' })`. Two dispatch shapes exist:

- **Static** — a literal `agentType: 'agent-teams-workforce:foo'`.
- **Dynamic (selected)** — `agentType: \`agent-teams-workforce:${x}\`` where `x` is drawn at runtime from a candidate roster hard-coded in the script (a read-only "lead" agent picks the fewest specialists whose surface the change touches). For these, the table lists every roster candidate the workflow **can** dispatch, marked *(roster)*. Which actually run is decided per-run by the lead — captured as candidates rather than forced precision.

Composite workflows (`bug-fix`, `task-to-deploy`, `prd-to-spec`, `infra-change`) do not spawn specialists directly (except `run-ledger-writer`); they call the leaf/shared minis via `workflow(...)`. Agents are therefore attributed to the mini that dispatches them; the composite that drives that mini is noted where relevant.

Two substring false positives and comment-only mentions were excluded: `trd-author` matched inside `'trd-authoring'` in `prd-to-spec` (not a dispatch); `chassis-extension-implementer` in `task-to-deploy` is a doc comment; `spec-decider` in `prd-to-spec` is a log-message string; `wave-deployment-sequencer` in `deploy` appears only in a comment stating it is deliberately **not** invoked.

---

## PART A — Coverage Table

| Agent | Workflow | Phase / Node | Purpose / Touchpoint |
| --- | --- | --- | --- |
| acceptance-criteria-reviewer | spec-authoring | authoring/review | Independent review of spec acceptance criteria |
| acceptance-criteria-writer | bug-triage | triage | Writes expected-behavior acceptance criteria for the fix contract |
| acceptance-criteria-writer | spec-authoring | authoring | Authors testable given/when/then criteria per requirement |
| accessibility-validator | tdd-refactor | Refactor *(optimizer roster)* | WCAG 2.2 A/AA validation when change touches UI |
| advantage-evaluator | gate-enforce | gate (post-pass) | Applies advantage principle to competitive flags |
| adversarial-critique-adjudicator | adversarial | Adjudicate | Referees finding severity; constitutive vs competitive |
| ambiguity-detector | prd-validation | fan-out analysts | Detects ambiguous PRD requirements |
| ambiguity-detector | route-build, route-elaboration | classification | Read-only tie-breaker when routing table can't decide |
| android-compose-implementer | tdd-green | Green *(implementer roster)* | Android/Compose production code to pass tests |
| api-contract-designer | architecture | Update SAD *(design roster: restApi)* | OpenAPI contract draft for decided REST surface |
| api-documentation-writer | documentation | Documentation *(writer roster)* | API reference docs for shipped APIs |
| api-gateway-cdk-implementer | tdd-green | Green *(implementer roster)* | API Gateway CDK implementation |
| api-specification-author | spec-authoring | authoring | API spec from TRD interface requirements |
| appsync-cdk-implementer | tdd-green | Green *(implementer roster)* | AppSync CDK implementation |
| appsync-client-subscription-implementer | tdd-green | Green *(implementer roster)* | AppSync client subscription implementation |
| architecture-boundary-guardian | architecture | Challenge | Guards bounded-context boundaries |
| architecture-decider | architecture | Decide + Update-SAD deadlock | Rules the unified architecture decision |
| architecture-decider | infra-intent | deadlock escalation | Breaks maker-checker deadlock on infra intent |
| architecture-decision-workflow-coordinator | architecture | Proposals | Frames/fans-out the proposal sub-team |
| architecture-diagram-author | architecture | Update SAD | Mermaid architecture diagrams from ruling |
| architecture-fitness-function-author | architecture | Update SAD | Testable fitness functions from ruling |
| architecture-pattern-challenger | architecture | Challenge | Stress-tests proposed patterns |
| architecture-tradeoff-skeptic | architecture | Challenge | Stress-tests tradeoffs |
| athena-redshift-analytics-implementer | tdd-green | Green *(implementer roster)* | Analytics SQL/warehouse implementation |
| auth-bypass-tester | adversarial | Attack *(access lane)* | Auth-bypass attacks in test env |
| aws-integration-test-runner | integration | Integration *(suite roster)* | Runs event API→EventBridge→SQS→Lambda suite |
| aws-integration-test-writer | tdd-red | Red *(writer roster)* | Writes failing integration tests for event chain |
| beads-format-validator | task-decomposition | validate | Validates Beads issue structural completeness |
| bedrock-integration-implementer | tdd-green | Green *(implementer roster)* | Bedrock model integration code |
| behavioral-signals-implementer | tdd-green | Green *(implementer roster)* | Behavioral signal capture/feature pipeline code |
| bounded-context-mapper | architecture | Proposals | Produces context map |
| brd-traceability-auditor | prd-validation | fan-out analysts | Traces PRD requirements to BRD objectives |
| cdk-infrastructure-designer | architecture | Proposals | CDK construct/Lambda packaging tradeoffs |
| cdk-infrastructure-designer | infra-intent | maker | **Maker**: produces CDK-expressible provisioning intent |
| cdk-infrastructure-drift-detector | deploy | Deploy-readiness | CDK synth + drift validation (read-only) |
| cdk-stack-author | infra-change | (pins tdd-green implementer) | infra-change pins Green's implementer to cdk-stack-author |
| cdk-stack-author | tdd-green | Green *(implementer roster + infra pin)* | Authors CDK stacks as the Green implementer on infra path |
| changelog-writer | documentation | Documentation *(writer roster)* | Changelog entries from commits |
| chassis-extension-implementer | tdd-green | Green *(implementer roster, default)* | Default Lambda-chassis production code |
| code-correctness-reviewer | tdd-refactor | Refactor | Independent no-regression review |
| code-quality-lead | tdd-refactor | Refactor | Read-only router: selects optimizers |
| code-refactoring-specialist | tdd-refactor | Refactor | Behavior-preserving refactor (maker) |
| code-style-and-linting-enforcer | tdd-refactor | Refactor *(optimizer roster)* | Lint/format/style cleanup |
| cognito-lambda-trigger-implementer | tdd-green | Green *(implementer roster)* | Cognito Lambda trigger code |
| completeness-checker | prd-validation | fan-out analysts | Each requirement has actor/action/outcome/criteria |
| complexity-analyzer | tdd-refactor | Refactor | Read-only complexity/duplication advisor |
| constitutional-agent | gate-constitutional | gate escalation | Binding ruling on novel constitutive conflicts |
| constraint-extractor | prd-validation | fan-out analysts | Builds constraint manifest |
| consumer-driven-contract-test-writer | tdd-red | Red *(writer roster)* | Failing consumer-driven contract tests |
| contract-violation-tester | adversarial | Attack *(access lane)* | Contract-violating inputs across boundaries |
| cost-architecture-reviewer | architecture | Proposals | Per-option cost estimation |
| cost-impact-reviewer | architecture | Challenge | Cost stress-test at 10x/100x/1000x |
| cost-impact-reviewer | infra-intent | checker | Cost impact review of infra intent |
| cross-service-contract-tester | integration | Integration *(suite roster)* | Cross-service/repo contract tests |
| data-consistency-checker | integration | Integration *(suite roster)* | Cross-store consistency checks |
| data-exposure-scanner | adversarial | Attack *(infra lane)* | Scans for leaked secrets/PII/over-return |
| data-exposure-scanner | infra-change | Adversarial *(trimmed lane)* | Infra-path data-exposure scan |
| data-model-specification-author | spec-authoring | authoring | DynamoDB table specs |
| data-pipeline-test-writer | tdd-red | Red *(writer roster)* | Failing data-pipeline tests |
| definition-of-done-enforcer | spec-authoring | authoring | Authors the Definition of Done |
| dependency-change-detector | infra-intent | freshness check | Detects dependency contract changes |
| dependency-change-detector | spec-freshness | parallel checkers | Detects dependency drift since spec authored |
| dependency-cve-auditor | adversarial | Attack *(infra lane)* | CVE/supply-chain audit |
| dependency-cve-auditor | infra-change | Adversarial *(trimmed lane)* | Infra-path CVE audit |
| dependency-graph-extractor | prd-validation | fan-out analysts | Builds dependency manifest |
| deployment-lead | deploy | Deploy-readiness | Read-only router: selects readiness artifacts |
| deployment-strategy-decider | deploy | Deploy-readiness | Rules rollout strategy (no execution) |
| documentation-accuracy-reviewer | documentation | Documentation | Independent accuracy review vs shipped behavior |
| documentation-currency-auditor | documentation | Documentation | Read-only staleness audit |
| documentation-lead | documentation | Documentation | Read-only router: assigns stale docs to writers |
| domain-boundary-validator | prd-validation | fan-out analysts | Confirms single bounded context |
| domain-event-modeler | architecture | Update SAD *(design roster: events)* | Models domain events/flows/contracts |
| dos-resilience-tester | adversarial | Attack *(infra lane)* | Load/resource-exhaustion probing |
| dynamodb-access-layer-implementer | tdd-green | Green *(implementer roster)* | DynamoDB access-pattern code |
| dynamodb-cost-optimizer | tdd-refactor | Refactor *(optimizer roster)* | DynamoDB capacity/cost optimization |
| dynamodb-schema-access-pattern-reviewer | spec-authoring | authoring/review | Validates DynamoDB access patterns in spec |
| dynamodb-streams-cdc-implementer | tdd-green | Green *(implementer roster)* | DynamoDB Streams CDC code |
| email-notification-implementer | tdd-green | Green *(implementer roster)* | Transactional/notification email code |
| error-handling-specification-author | spec-authoring | authoring | Error-handling spec per failure mode |
| espresso-test-writer | tdd-red | Red *(writer roster)* | Failing Android Espresso suites |
| event-api-client-implementer | tdd-green | Green *(implementer roster)* | Event API publishing clients |
| event-contract-author | spec-authoring | authoring | Authors event contracts |
| event-driven-consumer-implementer | tdd-green | Green *(implementer roster)* | Event consumer code |
| event-flow-tester | integration | Integration *(suite roster)* | EventBridge/SQS/Lambda flow tests |
| event-schema-designer | architecture | Update SAD *(design roster: events)* | Drafts event schemas in envelope format |
| event-schema-reviewer | spec-authoring | authoring/review | Reviews event schemas in spec |
| failure-mode-analyst | architecture | Proposals | Models failure modes per proposal |
| finops-analyst | deploy | Deploy-readiness *(artifact roster: finops)* | Pre-deploy cost posture |
| flaky-test-detector | integration | Integration | Verifies intermittent failures via reruns |
| frontend-performance-optimizer | tdd-refactor | Refactor *(optimizer roster)* | Frontend perf optimization |
| github-actions-pipeline-implementer | deploy | Deploy-readiness *(artifact roster: pipeline)* | CI/CD deploy pipeline |
| glue-etl-implementer | tdd-green | Green *(implementer roster)* | Glue ETL job code |
| graphql-schema-designer | architecture | Update SAD *(design roster: graphql)* | GraphQL schema draft |
| implementation-lead | tdd-green | Green | Read-only router: selects implementers |
| incident-response-runbook-designer | deploy | Deploy-readiness *(artifact roster: runbook)* | Incident-response/rollback runbook |
| infrastructure-security-scanner | adversarial | Attack *(infra lane)* | IaC/cloud misconfig scan |
| infrastructure-security-scanner | infra-change | Adversarial *(trimmed lane)* | Infra-path security scan |
| infrastructure-security-scanner | infra-intent | checker | Security scan of provisioning intent |
| injection-attack-tester | adversarial | Attack *(access lane)* | SQL/NoSQL/command/template injection |
| integration-pattern-architect | architecture | Proposals | Integration/routing tradeoffs |
| integration-testing-lead | integration | Integration | Read-only router: selects test suites |
| ios-swiftui-implementer | tdd-green | Green *(implementer roster)* | iOS SwiftUI production code |
| kinesis-stream-implementer | tdd-green | Green *(implementer roster)* | Kinesis producer/consumer code |
| lambda-performance-optimizer | tdd-refactor | Refactor *(optimizer roster)* | Lambda cold-start/memory optimization |
| llm-observability-implementer | tdd-green | Green *(implementer roster)* | LLM telemetry/drift-alert code |
| matching-algorithm-implementer | tdd-green | Green *(implementer roster)* | Matching/recommendation algorithm code |
| mcp-server-implementer | tdd-green | Green *(implementer roster)* | MCP server implementation |
| ml-evaluation-tester | tdd-red | Red *(writer roster)* | Failing ML evaluation suites |
| mobile-e2e-test-writer | tdd-red | Red *(writer roster)* | Failing Detox/Maestro E2E tests |
| nextjs-component-implementer | tdd-green | Green *(implementer roster)* | React/Next.js component code |
| nfr-analyst | prd-validation | fan-out analysts | Extracts/validates NFRs |
| okr-writer | prd-creation | OKR (parallel) | Derives OKR cascade |
| openapi-contract-reviewer | spec-authoring | authoring/review | Reviews OpenAPI contract in spec |
| operational-readiness-reviewer | architecture | Challenge | Operational burden per proposal |
| payments-integration-implementer | tdd-green | Green *(implementer roster)* | Stripe payment integration code |
| performance-benchmark-writer | tdd-red | Red *(writer roster)* | Failing performance benchmarks |
| permission-escalation-tester | adversarial | Attack *(access lane)* | Privilege-escalation probing |
| persistence-architecture-specialist | architecture | Proposals | DynamoDB schema/index tradeoffs |
| persona-profile-writer | prd-creation | persona (parallel) | Data-driven persona profiles |
| phase-gate-enforcer | gate-constitutional | gate | Constitutional gate: hard-stop enforcement |
| phase-gate-enforcer | gate-enforce | gate | Reusable phase gate: pass/loop/escalate |
| playwright-e2e-web-test-writer | tdd-red | Red *(writer roster)* | Failing Playwright web E2E tests |
| power-tools-configuration-implementer | tdd-green | Green *(implementer roster)* | Lambda Power Tools config |
| prd-alignment-verifier | prd-creation | verify | Traceability: requirement→spec→criteria |
| prd-creation-lead | prd-creation | orchestration | Sequences intake/persona/OKR/draft |
| prd-trd-traceability-verifier | trd-authoring | check | Bidirectional PRD↔TRD traceability |
| prd-validation-lead | prd-validation | orchestration | Fans PRD to analysts; aggregates |
| prd-writer | prd-creation | draft | Drafts the PRD (maker) |
| production-readiness-review-facilitator | deploy | Deploy-readiness | Aggregates evidence → go/no-go |
| race-condition-tester | adversarial | Attack *(access lane)* | Race/idempotency probing |
| react-native-implementer | tdd-green | Green *(implementer roster)* | React Native code |
| readme-writer | documentation | Documentation *(writer roster + fallback)* | README/setup/onboarding docs |
| recommendation-engine-implementer | tdd-green | Green *(implementer roster)* | Recommendation engine code |
| requirements-clarifier | prd-validation | fan-out analysts | Structured clarification requests |
| requirements-conflict-detector | prd-validation | fan-out analysts | Detects conflicting requirements |
| root-cause-analyst | bug-triage | triage | Determines bug root cause |
| root-cause-analyst | integration | Integration | Classifies integration failure + escalation target |
| run-ledger-writer | bug-fix | ledger (final) | Persists run decision ledger (JSONL) |
| run-ledger-writer | infra-change | ledger (final) | Persists run decision ledger |
| run-ledger-writer | prd-to-spec | ledger (final) | Persists run decision ledger |
| run-ledger-writer | task-to-deploy | ledger (final) | Persists run decision ledger |
| s3-data-lake-implementer | tdd-green | Green *(implementer roster)* | S3 data-lake layout code |
| sad-conformance-reviewer | architecture | Update SAD | Independent conformance check of SAD edit |
| sad-maintainer | architecture | Update SAD | Consolidates ruling into arc42 SAD (maker) |
| sad-source-extractor | trd-authoring | extract | Extracts SAD §2/4/8 source feed |
| security-architecture-designer | architecture | Proposals | Threat model / IAM / encryption options |
| security-test-case-designer | tdd-red | Red *(writer roster)* | Failing security test cases |
| slo-error-budget-designer | deploy | Deploy-readiness *(artifact roster: slo)* | SLOs / error budgets |
| smoke-test-author | deploy | Deploy-readiness | Post-deploy smoke tests |
| spec-currency-validator | spec-freshness | parallel checkers | Spec-vs-codebase drift |
| spec-decider | prd-creation | draft deadlock | Rules PRD maker-checker deadlock |
| spec-decider | spec-authoring | authoring deadlock | Rules spec maker-checker deadlock |
| spec-freshness-lead | spec-freshness | aggregation | Aggregates freshness verdicts |
| stakeholder-request-intake-writer | prd-creation | intake | Captures raw stakeholder request |
| task-decomposer | task-decomposition | decompose | Breaks spec into atomic tasks |
| task-dependency-mapper | task-decomposition | sequence | Builds dependency DAG |
| tdd-unit-test-generator | tdd-red | Red *(writer roster, always)* | Failing unit tests (always included) |
| test-coverage-gap-reviewer | tdd-red | Red | Independent coverage review vs acceptance criteria |
| test-design-lead | tdd-red | Red | Read-only router: selects test writers |
| test-environment-orchestrator | integration | Integration | Provisions/resets test env (only executor) |
| test-strategy-decider | tdd-red | Red | Rules test strategy (pyramid/coverage/env) |
| trd-author | trd-authoring | author | Authors the TRD (maker) |
| trd-decider | trd-authoring | deadlock | Rules TRD maker-checker deadlock |
| trd-validator | trd-authoring | check | Testability/feasibility/SAD-conflict check |
| ubiquitous-language-writer | architecture | Update SAD *(design roster: newDomain)* | Captures ubiquitous language |
| user-guide-writer | documentation | Documentation *(writer roster)* | User-facing feature guides |
| vector-search-embeddings-implementer | tdd-green | Green *(implementer roster)* | Vector search / embeddings code |
| webauthn-implementer | tdd-green | Green *(implementer roster)* | WebAuthn passkey code |
| wsjf-scorer | task-decomposition | score | WSJF scores every task |
| wsjf-scoring-reviewer | task-decomposition | score review | Independent WSJF score review |
| xcuitest-writer | tdd-red | Red *(writer roster)* | Failing iOS XCUITest suites |

---

## PART B — Coverage Findings

### Headline counts

- **173** agents defined in `agents/` (excluding `README.md`, `agents-file.md`).
- **157** are referenced by at least one workflow (static dispatch or dynamic-selection roster).
- **16** are orphans (no workflow references them).
- Of the 157 referenced: **142 appear in exactly one workflow (≈90%)**; only **15 appear in two or more**.

**The user's suspicion is confirmed: the overwhelming majority of agents (90% of those used, 142/157) appear in exactly one workflow.** Reuse is the rare exception.

### (i) ORPHANS — defined but referenced by no workflow (16)

| Orphan agent | Why it's likely orphaned |
| --- | --- |
| `spec-authoring-lead` | Routing role absorbed into `spec-authoring.js` script control flow |
| `task-decomposition-lead` | Routing role absorbed into `task-decomposition.js` |
| `trd-authoring-lead` | Routing role absorbed into `trd-authoring.js` |
| `sdlc-pipeline-orchestrator` | Phase sequencing now done by the composite `.js` scripts |
| `adversarial-review-loop-supervisor` | Loop control now in `adversarial.js` / gate scripts |
| `cross-repo-integration-test-coordinator` | Cross-repo sequencing not wired into `integration.js` |
| `wave-deployment-sequencer` | Explicitly **not** invoked by `deploy.js` (prod rollout is human-gated) |
| `context-curator` | Governance agent; no workflow node instantiates it |
| `polyrepo-cartographer` | Standalone specialist, invoked ad hoc, not by a workflow |
| `user-story-writer` | Not wired into `task-decomposition.js` (see reuse gap b) |
| `user-story-reviewer` | Not wired into `task-decomposition.js` (see reuse gap b) |
| `test-plan-strategy-reviewer` | Not wired into `tdd-red.js` (strategy handled by `test-strategy-decider`) |
| `test-isolation-specialist` | No workflow node dispatches it |
| `graphql-schema-reviewer` | GraphQL drafted in `architecture` but never reviewed downstream |
| `c4-diagram-author` | Diagramming folded into `architecture-diagram-author` |
| `uml-diagram-author` | Diagramming folded into `architecture-diagram-author` |

Two orphan clusters dominate: **(1) `*-lead` / orchestrator / coordinator agents** whose routing job was moved into the workflow scripts, and **(2) reviewer/author agents whose competence was consolidated into a sibling** (diagram authors, story writer/reviewer, graphql reviewer).

### (ii) SINGLETONS vs. reused

- **Singletons (1 workflow): 142.**
- **Reused (2+ workflows): 15**, listed with count:

| Reused agent | # | Workflows |
| --- | --- | --- |
| run-ledger-writer | 4 | bug-fix, infra-change, prd-to-spec, task-to-deploy |
| infrastructure-security-scanner | 3 | adversarial, infra-change, infra-intent |
| spec-decider | 2 | prd-creation, spec-authoring |
| architecture-decider | 2 | architecture, infra-intent |
| cdk-infrastructure-designer | 2 | architecture, infra-intent |
| cost-impact-reviewer | 2 | architecture, infra-intent |
| dependency-change-detector | 2 | infra-intent, spec-freshness |
| dependency-cve-auditor | 2 | adversarial, infra-change |
| data-exposure-scanner | 2 | adversarial, infra-change |
| root-cause-analyst | 2 | bug-triage, integration |
| phase-gate-enforcer | 2 | gate-constitutional, gate-enforce |
| acceptance-criteria-writer | 2 | bug-triage, spec-authoring |
| ambiguity-detector | 3 | prd-validation, route-build, route-elaboration |
| cdk-stack-author | 2 | tdd-green (roster) + infra-change (pins it as Green implementer) |

Most reuse is genuine cross-cutting infrastructure: `run-ledger-writer` (telemetry), the gate enforcer, and the architecture/infra overlap (infra-intent deliberately reuses the architecture team's decider, designer, and cost reviewer). This is healthy reuse, not accidental duplication.

### (iii) REUSE GAPS

#### Hypothesis (a): "TDD Green agents should largely be the same as TDD Red agents." — REFUTED (by design)

Red and Green use **completely disjoint** agent sets — **zero overlap**:

- **`tdd-red.js` roster** (test writers): `tdd-unit-test-generator` (always), `consumer-driven-contract-test-writer`, `aws-integration-test-writer`, `security-test-case-designer`, `performance-benchmark-writer`, `playwright-e2e-web-test-writer`, `xcuitest-writer`, `espresso-test-writer`, `mobile-e2e-test-writer`, `ml-evaluation-tester`, `data-pipeline-test-writer` — plus `test-design-lead`, `test-strategy-decider`, `test-coverage-gap-reviewer`.
- **`tdd-green.js` roster** (implementers): `chassis-extension-implementer` (default) and 27 other `*-implementer` agents — plus `implementation-lead`.

This is **intentional segregation of duties**, not a gap: TDD doctrine plus `rules/separation-of-duties.md` require that the agent writing a test is not the one writing the code to pass it. The rosters are instead **specialty-paired** across the Red/Green boundary — e.g. `xcuitest-writer`↔`ios-swiftui-implementer` (iOS), `espresso-test-writer`↔`android-compose-implementer` (Android), `playwright-e2e-web-test-writer`↔`nextjs-component-implementer` (web), `ml-evaluation-tester`↔`matching/recommendation-implementer` (ML), `data-pipeline-test-writer`↔the data implementers. So the hypothesis that they *should* be the same agent runs against the framework's core invariant; the framework correctly keeps them distinct-but-parallel. The one thing worth noting is the **maintenance burden of keeping two parallel rosters in sync** — a new subsystem needs both a Red writer and a Green implementer added, and nothing enforces that pairing.

#### Hypothesis (b): "The agent reviewing acceptance criteria on a spec should be the same one reviewing them on a story." — CONFIRMED as a real duplication

Acceptance-criteria / testable-behavior review competence is **fragmented across at least four agents at different phases**:

1. `acceptance-criteria-reviewer` — reviews spec acceptance criteria (`spec-authoring`).
2. `user-story-reviewer` — "Validates every user story is complete, **testable**, and scoped" — conceptually the same review applied to a story. **But it is an ORPHAN**: `task-decomposition.js` never dispatches it.
3. `completeness-checker` — in `prd-validation`, "validates each requirement has … **acceptance criteria**" — the same completeness judgment one phase earlier.
4. `test-coverage-gap-reviewer` — in `tdd-red`, checks tests against the acceptance criteria — again judging the same criteria for coverage.

Correspondingly on the authoring side, `acceptance-criteria-writer` (reused in bug-triage + spec-authoring) and the orphaned `user-story-writer` ("Writes a user story per decomposed task, **with acceptance criteria**") are near-duplicate authors. The story-level pair (`user-story-writer` / `user-story-reviewer`) essentially **re-implements the spec-level pair's competence but is dead code** — strong evidence for the user's hypothesis: the same competence was cloned into a second agent instead of reused, and the clone was then left unwired.

Related asymmetry: `acceptance-criteria-writer` runs in **both** bug-triage and spec-authoring, but its independent reviewer `acceptance-criteria-reviewer` runs **only in spec-authoring**. In bug-triage the acceptance criteria are authored with **no independent criteria review** — an inconsistency in how the same artifact is validated across the two entry paths.

#### Other duplications found (separate agents for near-identical artifacts)

- **Diagram authors.** `architecture-diagram-author` (used) produces Mermaid diagrams; `c4-diagram-author` and `uml-diagram-author` (both orphans) cover C4 and UML Mermaid diagrams — three agents for "author an architecture diagram in Mermaid," only one wired in.
- **API-contract authoring across phases.** `api-contract-designer` (architecture, OpenAPI *draft*) and `api-specification-author` (spec-authoring, API *spec*) author the same API contract at two phases, reviewed by yet another agent (`openapi-contract-reviewer`). Defensible as draft→elaborate, but it is two distinct author agents for one artifact lineage.
- **Event-schema authoring across phases.** `event-schema-designer` (architecture *draft*) and `event-contract-author` (spec-authoring *contract*) — same draft→elaborate split for event shapes, with `event-schema-reviewer` judging.
- **GraphQL review gap.** `graphql-schema-designer` drafts GraphQL in `architecture`, but the dedicated `graphql-schema-reviewer` is an **orphan** — the REST path gets `openapi-contract-reviewer` review in spec-authoring while the GraphQL path's reviewer is never invoked (an asymmetric coverage hole, not just duplication).
- **Lead/router agents vs. script routing.** Nine `*-lead`/router agents ARE still dispatched as read-only selectors (`test-design-lead`, `implementation-lead`, `integration-testing-lead`, `code-quality-lead`, `deployment-lead`, `documentation-lead`, `prd-creation-lead`, `prd-validation-lead`, `spec-freshness-lead`), while four others (`spec-authoring-lead`, `task-decomposition-lead`, `trd-authoring-lead`, `sdlc-pipeline-orchestrator`) were **replaced by script control flow and orphaned**. This is an **inconsistent pattern**: some phases keep a lead agent to do runtime specialist selection; others fold that selection into the `.js` and drop the lead. Whichever is correct, the two conventions coexist unreconciled.

### Ambiguity note (candidate vs. actual dispatch)

Six workflows do not run a fixed agent set — a read-only lead picks the fewest specialists at runtime from a hard-coded roster: `tdd-red` (test writers), `tdd-green` (implementers), `tdd-refactor` (optimizers), `integration` (suites), `deploy` (readiness artifacts), `documentation` (doc writers), plus `architecture`'s surface-conditioned design executors and `adversarial`'s attack lanes. For those, the table lists all roster candidates *(roster)*; on any given run only a subset executes. So "appears in one workflow" for, say, `ios-swiftui-implementer` means "is a selectable candidate in tdd-green," not "runs every time."
