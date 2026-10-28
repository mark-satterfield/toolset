# SDLC Workforce Agents

These agents implement the SDLC pipelines — PRD creation through deployment, plus cross-cutting documentation and governance — under separation-of-duties rules: every agent performs exactly one task category (plan, orchestrate, execute, approve, or test). Each purpose below is the agent's own description; an agent a workflow does not start is available to a caller that chooses it through the `find-specialists` catalog.

## Governance

Gate and conflict rulings, and context integrity. `gate-enforce` starts `phase-gate-enforcer` and, in its exhaustion mode, `exhausted-gate-ruler`; the others are available to a caller that chooses them.

| Agent | Category | Purpose |
| --- | --- | --- |
| phase-gate-enforcer | approve | Rules pass, loop or escalate on the constitutive criteria of one phase gate, from the criteria and the artifact the gate-enforce workflow quotes: loop when the cause of an unmet criterion is inside the phase, escalate when it is upstream, naming where it goes back to. Deterministic checks and competitive criteria are settled by the gate script and never reach it. |
| exhausted-gate-ruler | approve | Rules how a run continues from a phase gate whose loops are spent: proceed, with the latest output standing and every unmet criterion carried on as a named residual with its mitigation, or one directed revision under a concrete, changed instruction. Started by the gate-enforce workflow in its exhaustion mode. |
| advantage-evaluator | approve | Rules commit or revert on a competitive (non-constitutive) finding that work was allowed to proceed under: before the outcome exists it states the observation window and the evidence that will decide, then judges the observed outcome against it. Speculative execution with rollback, so a tradeable finding never halts a run. |
| constitutional-agent | approve | Rules on a conflict between two constitutive constraints that no gate can settle: establishes the constitutional layer the conflict falls under (the owner's section 2 constraints and settled decisions recorded in the matrix, the business outcomes of the PRD the work serves, and the review standard's acceptance basis), names which constraint prevails and under what conditions, and writes the ruling as a precedent record a later conflict can cite. |
| context-curator | execute | Assembles a context index for one receiving agent and task: a file of pointers (paths, headings, matrix ids and atw-matrix commands) to exactly what the role needs, with every constitutive constraint that binds it carried by pointer to its one home, never copied or summarized, and keeps the constraint manifest those pointers come from current. |

## PRD Creation

`prd-creation` starts each of these agents in turn and, when the writer and the verifier do not converge, `review-dispute-decider` (Spec Authoring).

| Agent | Category | Purpose |
| --- | --- | --- |
| stakeholder-request-intake-writer | execute | Turns one raw stakeholder request into the structured intake of a feature: the scope the request frames (what it asks for and what it leaves out), the problem, the audience, the desired outcome, the constraints it states and the open questions it leaves, WHAT the users need and never HOW to build it. |
| feature-persona-writer | execute | Writes the one target persona a feature serves, grounded in the audience, problem and outcome of the feature's intake: a proto-persona whose goals, frustrations and context are each stated, inferred or marked as an assumption, behavior over demographics. |
| feature-objective-writer | execute | Writes the one objective a feature must move and the key results that prove it was met, grounded in the feature's intake: a qualitative, user-centered objective and measurable key results, each with its metric and target. |
| prd-writer | execute | Writes a template-conformant PRD, WHAT and never HOW, from a feature's intake, persona and objective, with acceptance criteria for its P0 requirements, and the one-paragraph scope of the Epic that pairs with it; on a revision, applies the alignment verdict on its previous draft. |
| prd-alignment-verifier | test | Independently judges whether a draft PRD aligns with the intake brief, persona and objective it was written from, and is template-conformant and WHAT-not-HOW, on four dimensions (intake, persona, objective, template). |

## PRD Validation

`prd-validation` starts one specialist per lens, and `brd-traceability-auditor` only when a BRD is named; it merges their results. `prd-to-spec` hands the PRD file to its agents as it stands and starts none of these. `nfr-analyst` and the lead are available to a caller that chooses them.

| Agent | Category | Purpose |
| --- | --- | --- |
| prd-validation-lead | orchestrate | Manual-only coordinator for explicitly assigned PRD validation work. Selects bounded analysts and routes their findings without making solution or approval decisions. The active prd-validation mini dispatches its lens specialists itself and does not dispatch this lead. |
| requirement-classifier | test | Classifies every requirement a PRD states as business or technical and, for each technical rule, asks the matrix whether the architecture already states it; never rewrites the PRD. |
| ambiguity-detector | test | Finds the requirements of a PRD whose user-observable behavior is unclear, contradictory within itself or open to two incompatible readings (vague quantifiers, missing user-observable boundary conditions, unstated assumptions); reports each with a concrete clarification, never fixes. |
| completeness-checker | test | Checks that each requirement of a PRD has an actor, a trigger or action, an observable user outcome and a behavioral acceptance criterion, and reports each missing or defective element; never supplies one. |
| requirements-conflict-detector | test | Finds sets of requirements in a PRD whose WHAT cannot all hold, citing the requirements in tension; never resolves them. |
| constraint-extractor | execute | Extracts the explicit and implied constraints a PRD imposes (regulatory, business, platform, policy), each with its kind and where the PRD states or implies it; invents none. |
| domain-boundary-validator | test | Checks that a PRD's requirements stay inside one bounded context, and reports each requirement that makes the feature own behavior another feature or service owns or that sits in more than one context. |
| requirements-clarifier | plan | Raises the open BUSINESS questions a PRD's author must answer before it can be specified, each tied to its requirement and unresolved; never answers them and never raises a technical gap. |
| brd-traceability-auditor | test | Maps each PRD requirement to the objectives of a BRD the run names, for information only: a correspondence, never a verdict on the PRD. |
| nfr-analyst | plan | Lists the non-functional quality intents a PRD states or implies (performance, availability, security, privacy, accessibility, operability and the rest), each tied to the requirements that state or imply it, as input to a TRD; never quantifies them and never reports them as defects of the PRD. Available to a caller that chooses it; no workflow dispatches it. |

## Architecture

`aws-solutions-architect` has single responsibility for the architecture a PRD needs. It chooses the design specialists, review specialists and diagram authors a gap needs through the `find-specialists` catalog and puts to each one request a round, which the script runs, states the TRD changes its decisions make and the facts the script has `architecture-maintainer` write into arc42, reviews and approves its own architecture and records the proof in the Epic's review log. `architecture-team-lead` routes what the architect could not settle, and `architecture-decider` rules on what the team could not settle. The remaining agents here are available to a caller that chooses them.

| Agent | Category | Purpose |
| --- | --- | --- |
| aws-solutions-architect | execute | Holds single responsibility for the architecture a PRD needs, from the first read of the PRD until the architecture and the TRD are designed, reviewed and approved, with the review log that proves how. |
| architecture-team-lead | orchestrate | Routes what the solutions architect could not settle, so that the team settles it with the least further work. |
| architecture-decider | approve | Rules between the positions on an architecture matter the solutions architect and the architecture team lead could not settle, from the evidence each position carries, and records the ruling in the matrix as the settlement of the disagreement. |
| architecture-maintainer | execute | Writes the solutions architect's decisions into the architecture documents (arc42 and detailed/), each fact in its one home with links from every other document, and corrects the effective documents to match what a Story built. |
| architecture-diagram-author | execute | Draws one architecture diagram of a design the solutions architect has settled, of any view type the documentation model lists (C4, UML, context map, data flow, deployment and the others), and returns it with its home, view type and the elements it shows. |
| c4-diagram-author | execute | Draws one C4 diagram (system context, container, component or deployment) of a design the solutions architect has settled, and returns it with its home, view type and the elements it shows. |
| uml-diagram-author | execute | Draws one UML diagram (sequence, state, activity, class, component or deployment) of a design the solutions architect has settled, and returns it with its home, view type and the elements it shows. |
| architecture-impact-analyst | test | Judges what an architecture change reaches. Given the architecture views an integration changed, created or deleted, it takes from the matrix every Epic, open Task and entry those views reach (`atw-matrix impact`, `affected`), and rules on each one: unaffected, not yet elaborated, elaborated but unbuilt, or already built, with a knock-on Task proposed for each built item. It changes no bead and writes no code or document; it writes only its result file. |
| architecture-fitness-function-author | execute | Defines testable assertions from the owner's constraints and the architecture decisions, e.g. "every Lambda uses the configured logging library", "no service reads another service's table". |
| ubiquitous-language-writer | execute | Captures each bounded context's ubiquitous language — terms, definitions, usage rules — as a maintained glossary. |

## Design Specialists

Each answers a question or does a bounded piece of design for the solutions architect in one domain, loads the `design-specialist-contract` skill and the skills of its domain, and is found by the architect through the `find-specialists` catalog. No workflow starts them by name; `infra-intent` also starts `cdk-infrastructure-designer` to turn a Task's recorded infrastructure into provisioning intent.

### Domain, data and integration

| Agent | Category | Purpose |
| --- | --- | --- |
| bounded-context-mapper | plan | Answers a question or does a bounded piece of design for the solutions architect on bounded contexts: their boundaries, domain responsibilities, which service owns each, the relationships between contexts and the published language each exposes. |
| domain-event-modeler | plan | Answers a question or does a bounded piece of design for the solutions architect on domain events as facts: which fact each event states, the bounded context and aggregate that owns it, what triggers it, the causal flow it belongs to and the business meaning of the data it carries. |
| data-architect | plan | Answers a question or does a bounded piece of design for the solutions architect on pure data architecture independent of any engine — conceptual and logical data models, entities and relationships, which domain owns each entity and its system of record, data flows and lineage, reference and master data, data classification and retention classes, operational versus analytical data, and data contracts between domains. |
| persistence-architecture-specialist | plan | Answers a question or does a bounded piece of design for the solutions architect on which store holds each data set (DynamoDB, Aurora or RDS, ElastiCache or MemoryDB, Neptune, DocumentDB, Timestream, S3, EBS, EFS or FSx), which block owns each store, the consistency each scenario needs, and the data lifecycle across stores. |
| integration-pattern-architect | plan | Answers a question or does a bounded piece of design for the solutions architect on how building blocks interact: which interactions are synchronous calls and which are events, the delivery path each takes (direct call, EventBridge rule, SNS fan-out, SQS buffer, Step Functions), and its end- to-end delivery guarantee, ordering, idempotency and failure behaviour. |
| security-architecture-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on trust boundaries, the threat model of a design and the mitigation of each threat across those boundaries: who may cross each boundary and what each runtime may reach. |
| cdk-infrastructure-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on which repository and which CDK stack hold each resource and building block, how stacks share values, which shared infrastructure must exist first, and construct and parameter names; and express the infrastructure the architecture records for a build Task as CDK provisioning intent. |

### Compute

| Agent | Category | Purpose |
| --- | --- | --- |
| lambda-function-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on AWS Lambda functions: runtime and architecture, memory, timeout and ephemeral storage, concurrency (reserved and provisioned), SnapStart, layers, invocation model and event source mappings, asynchronous invocation destinations, VPC attachment and cold-start behaviour. |
| container-service-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on containers on Amazon ECS: Fargate or ECS Managed Instances or EC2 capacity, task definitions (CPU, memory, containers, health checks), services and their deployment and scaling, Amazon ECR repositories and image lifecycle. |
| kubernetes-cluster-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon EKS: cluster version and access, compute (managed node groups, Karpenter, Fargate profiles, EKS Auto Mode), pod networking, workload identity, add-ons and pod scaling. |
| ec2-fleet-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon EC2 fleets: instance type selection, AMIs, launch templates, Auto Scaling groups and their scaling policies, Spot and mixed instances, IMDSv2 and fleet operations through Systems Manager. |
| batch-compute-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on AWS Batch: compute environments (Fargate, EC2, Spot), job queues and their priorities, job definitions, array and multi-node jobs, retries and timeouts, and scheduling policies. |

### Databases and storage

| Agent | Category | Purpose |
| --- | --- | --- |
| relational-database-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on relational databases on Amazon Aurora, Amazon RDS, Aurora DSQL and RDS Proxy — engine and cluster shape, capacity, access path, replicas, backups, and the relational schema (tables, keys, constraints, indexes, partitioning, migrations). |
| dynamodb-table-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon DynamoDB and DAX — access-pattern-first single-table or multi-table design, partition and sort keys, GSIs and LSIs, capacity mode, TTL, streams, transactions, global tables, backups and cost. |
| cache-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on in-memory caching and in-memory data stores on Amazon ElastiCache (Valkey, Redis OSS, Memcached; serverless or node-based) and Amazon MemoryDB — caching pattern, key and TTL design, invalidation, eviction, topology, durability and multi-Region replication. |
| graph-database-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on graph data on Amazon Neptune Database and Neptune Analytics — engine and capacity choice, property graph or RDF, node and edge model, query language (openCypher, Gremlin, SPARQL), traversal and supernode design, loading, graph algorithms and vector search. |
| document-database-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on document data on Amazon DocumentDB (MongoDB compatible) — cluster type and capacity, document model (embedding or referencing), indexes, MongoDB API compatibility, change streams, transactions and read scaling. |
| time-series-database-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on time-series data on Amazon Timestream (Timestream for InfluxDB, and Timestream for LiveAnalytics for existing accounts) — engine choice, measurement, tag and field model, cardinality, retention and downsampling, ingestion and query. |
| object-storage-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on object storage on Amazon S3 and the S3 Glacier storage classes — buckets, key layout, storage classes and lifecycle, versioning and Object Lock, replication, access control and Block Public Access, presigned URLs, multipart upload and event notifications. |
| block-and-file-storage-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on block and file storage for EC2, containers and Lambda on Amazon EBS, Amazon EFS and Amazon FSx (Lustre, NetApp ONTAP, OpenZFS, Windows File Server) — volume and file system type, performance and throughput mode, availability, snapshots and backups, lifecycle tiering and access. |

### Networking and edge

| Agent | Category | Purpose |
| --- | --- | --- |
| vpc-network-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon VPC networking: CIDR plan, subnets and route tables, internet and NAT gateways, VPC endpoints (gateway and interface) and PrivateLink, security groups and network ACLs, Transit Gateway and peering, and VPC flow logs. |
| load-balancer-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on Elastic Load Balancing: choosing an Application, Network or Gateway Load Balancer, listeners and TLS, routing rules, target groups and health checks, stickiness, deregistration and cross-zone behaviour. |
| dns-and-edge-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon Route 53 and Amazon CloudFront: hosted zones, records and routing policies, health checks and failover, CloudFront distributions, origins and origin access control, cache and origin request policies, edge functions, and custom domains. |

### APIs, events and messaging

| Agent | Category | Purpose |
| --- | --- | --- |
| api-contract-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on REST APIs on Amazon API Gateway (REST API): which building block exposes each interface, its resources and methods, who may call it and how the caller is authorized, request validation, throttling and usage plans, errors, and how it stays compatible. |
| graphql-api-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on GraphQL APIs on AWS AppSync: schema, operations and types, which block resolves each field from which owned data, resolvers and data sources, authorization modes, subscriptions, caching and compatibility. |
| event-routing-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon EventBridge: event type names and their registry entries, the payload schema of a new event type, buses, routing rules (event pattern, targets, owning stack), each rule target's retry policy and dead-letter queue, and EventBridge Scheduler schedules. |
| queue-and-topic-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon SQS queues and Amazon SNS topics: standard or FIFO, visibility timeout, retention, redrive policies and dead- letter queues, SNS subscriptions, filter policies and delivery retry, fan-out, and Amazon MQ where a broker protocol is required. |
| workflow-orchestration-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on AWS Step Functions: Standard or Express workflows, state machine structure in Amazon States Language, service integration patterns, retries and catches, sagas and compensation, Map and Parallel states, callbacks, and execution logging. |

### Streaming and analytics

| Agent | Category | Purpose |
| --- | --- | --- |
| stream-processing-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on real-time data streams on Amazon Kinesis Data Streams, Amazon Data Firehose, Amazon MSK and Amazon Managed Service for Apache Flink — stream and capacity mode, partition keys and ordering, retention, consumers and fan-out, delivery buffering, transformation and processing windows. |
| data-lake-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on the data lake on AWS Glue, AWS Lake Formation and Amazon S3 Tables — zones and table layout, open table format (Apache Iceberg), partitioning, the Glue Data Catalog, ingestion and ETL jobs, connections to sources, data quality and Lake Formation permissions. |
| analytics-query-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on serverless SQL analytics with Amazon Athena over the data lake — workgroups and their limits, query result handling, data layout for scan cost, partition projection, federated and Iceberg queries, CTAS and UNLOAD, and capacity. |
| data-warehouse-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on data warehousing on Amazon Redshift (Serverless or provisioned RA3) — workgroup or cluster shape, table design (distribution, sort keys, encoding), loading with COPY and zero-ETL, materialized views, data sharing, Spectrum and workload management. |

### Security and identity

| Agent | Category | Purpose |
| --- | --- | --- |
| iam-policy-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on AWS IAM: roles and their trust policies, identity and resource policies with least privilege, condition keys and confused-deputy protection, permission boundaries, cross-account access, service-linked and service roles, and IAM Identity Center for human access. |
| user-authentication-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on end-user authentication with Amazon Cognito: user pools and app clients, sign-up and sign-in flows, MFA and passkeys, OAuth 2.0 and OIDC flows, social and SAML federation, tokens and their lifetimes, Lambda triggers, and identity pools. |
| encryption-and-secrets-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on AWS KMS keys and key policies, envelope encryption and key rotation, AWS Secrets Manager secrets and their rotation, and AWS Certificate Manager certificates. |
| perimeter-protection-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on AWS WAF web ACLs and rules (managed rule groups, rate-based rules, bot control), AWS Shield Standard and Advanced for DDoS protection, Route 53 Resolver DNS Firewall, and Amazon GuardDuty threat detection. |

### AI and machine learning

| Agent | Category | Purpose |
| --- | --- | --- |
| foundation-model-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon Bedrock foundation models - model and inference profile choice per task, Converse API calls, maxTokens and timeouts, quotas and throughput, prompt caching, attaching guardrails to a model call, and inference cost. |
| rag-architecture-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on retrieval-augmented generation and semantic search - Bedrock Knowledge Bases, chunking, embeddings models, vector stores (Aurora pgvector, S3 Vectors, OpenSearch, Neptune Analytics), hybrid retrieval, re-ranking, metadata filtering and retrieval evaluation. |
| applied-ai-services-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on the AWS pre-trained AI services - Amazon Textract document extraction, Amazon Rekognition image and video analysis, and Amazon Comprehend text analysis and PII detection - their operations, synchronous or asynchronous paths, limits, confidence handling and cost. |
| ml-feature-pipeline-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on machine learning features - feature definitions and engineering, batch or streaming computation, SageMaker Feature Store online and offline stores, SageMaker Data Wrangler data preparation, training-serving consistency and feature drift. |
| ml-training-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on training and fine-tuning models on Amazon SageMaker AI - base model and technique (SFT, DPO, RLVR, RLAIF), training data, training jobs, managed Spot and checkpointing, hyperparameter tuning, evaluation and acceptance, experiment tracking and retraining. |
| ml-inference-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on serving trained models on Amazon SageMaker AI - real-time, serverless and asynchronous endpoints, batch transform, multi-model and multi-container endpoints, scaling, deployment guardrails and shadow tests, and Model Monitor. |
| ai-agent-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on custom AI agents - Amazon Bedrock AgentCore Runtime and Harness, agent frameworks such as Strands, AgentCore Memory, tools through AgentCore Gateway and MCP, multi-agent and A2A, AgentCore Identity and Cedar policies, and agent bounds. |
| generative-ai-pattern-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on generative AI flow patterns - prompt chaining, routing, parallelisation, orchestrator and workers, evaluator-optimiser loops, prompt structure, structured output, chain of verification, LLM-as-judge evaluation, human in the loop and applying guardrails to a flow. |

### Observability and governance

| Agent | Category | Purpose |
| --- | --- | --- |
| monitoring-and-tracing-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon CloudWatch and AWS X-Ray: metrics and embedded metric format, log groups and retention, Logs Insights queries, alarms (metric, composite, anomaly detection) and their actions, dashboards, distributed tracing with X-Ray and ADOT, Application Signals, synthetics and SLO alarms. |
| audit-and-compliance-designer | plan | Answers a question or does a bounded piece of design for the solutions architect on AWS CloudTrail (trails, management and data events, CloudTrail Lake, log integrity and retention) and AWS Config (recording, managed and custom rules, conformance packs, remediation), and the Security Hub controls they feed. |

## Architecture Review Specialists

Each reviews one aspect of an Epic's unapproved architecture and TRD when the solutions architect chooses it through the `find-specialists` catalog and asks it a review question. No workflow starts them.

| Agent | Category | Purpose |
| --- | --- | --- |
| architecture-boundary-guardian | test | Reviews, for the solutions architect, the boundaries of a design: whether each building block's responsibilities and owned data stay inside its bounded context, whether every interface that crosses a boundary is explicit about who exposes it and who may call it, whether shared behaviour is taken from its shared home, and whether the design breaks a section 2 constraint or departs from an established pattern without a stated reason. |
| architecture-pattern-challenger | test | Reviews, for the solutions architect, the structure of a design for concrete weaknesses: a mechanism that does not do what the requirement needs, a structure more complex than the requirement, or an AWS pattern used against its documented best practice, each reported with the simpler sufficient repair. |
| architecture-tradeoff-skeptic | test | Reviews, for the solutions architect, the trade-off claims of a design: whether each choice between options states the options and a reason the evidence supports, and whether the assumptions and estimates it rests on (latency, throughput, limits, effort) hold against the stated constraints and AWS documentation. |
| failure-mode-analyst | test | Reviews, for the solutions architect, how a design fails and recovers: throttling, duplicate and out-of-order delivery, poison messages, downstream outages, timeouts, retries, dead-letter queues, idempotency and recovery paths across Lambda, SQS, SNS, EventBridge and the event path, as the runtime views and the TRD state them. |
| operational-readiness-reviewer | test | Reviews, for the solutions architect, whether a design can be operated: the logs, metrics, alarms and dashboards each block needs, the TRD's observability, availability and recovery obligations, how each failure is detected and who is told, and the operational burden at the stated usage. |
| new-resource-cost-reviewer | test | Reviews, for the solutions architect, the cost of each billable AWS resource a design adds: its unit prices from the AWS Price List, the monthly unit math at the stated usage computed by script, its fixed monthly floor separated from its usage cost, and the total against the stated cost ceilings. |
| changed-resource-cost-reviewer | test | Reviews, for the solutions architect, the cost effect of a design's changes to existing resources: changed billable limits, capacity modes, retention or usage, the cost assumptions each change rests on, a monthly floor it adds or moves, and any cost cliff (a pricing tier, free-tier limit, quota or capacity-mode boundary) the stated usage reaches. |

## TRD

The script starts `trd-author` once the architecture check passes, from the architect's TRD changes, and for the correction the TRD confirm step asks for. The other two are available to a caller that chooses them.

| Agent | Category | Purpose |
| --- | --- | --- |
| trd-author | execute | Completes the Epic's TRD once the architecture is decided, from the seed a script wrote from the constraints that bind the Epic, the requirements the PRD implies and the solutions architect's changes, and corrects it where its confirmation finds it does not resolve. |
| prd-trd-traceability-verifier | test | Builds and checks the TRD's SOURCE traceability matrix: every TRD requirement anchored to a PRD requirement OR to an architecture view, every PRD requirement needing technical elaboration answered, and genuine scope drift flagged. The relation is not 1:1 and an architecture-sourced requirement is not an orphan. |
| trd-decider | approve | Rules on a dispute over a TRD from the evidence the sides wrote: a TRD maker-checker deadlock, competing TRD approaches, or checkers that contradict each other on one TRD section; generates no TRD content or analysis. For a caller that runs a TRD review loop; in elaboration TRD disputes go to architecture-decider through the architecture team. |

## Spec Authoring

Elaboration starts, per repository, `ui-design-source-selector` (frontend repositories), the two specification authors (`api-specification-author` also writes the acceptance criteria, after the contracts, in the same session), `dynamodb-schema-access-pattern-reviewer` when a stack the Story builds in holds a DynamoDB store, `spec-reviewer`, and `review-dispute-decider` for each finding an author disputes. The other agents here are available to a caller that chooses them.

| Agent | Category | Purpose |
| --- | --- | --- |
| spec-authoring-lead | orchestrate | Routes maker output to checkers and findings back to makers until checkers pass, then reports the spec packet; never evaluates spec quality, only pass/rework signals. |
| ui-design-source-selector | plan | Chooses the design source of each UI item a frontend repository's Story builds, from the cds bundles the owner supplied and the configured Configurable Design System (cds) - a supplied bundle, the live design system, or no design change; designs nothing. |
| api-specification-author | execute | Writes the spec of the API, event, error and UI contracts one repository's Story builds, from the recorded architecture and design, then the acceptance criteria and Definition of Done of that Story from the TRD, the contracts and the data model; designs nothing. |
| data-model-specification-author | execute | Writes the spec of the data one repository's Story builds, from the recorded architecture and design; designs nothing. |
| acceptance-criteria-writer | execute | Derives traceable criteria and Definition of Done from the finished specification set. |
| definition-of-done-writer | execute | Writes the Definition of Done of a given scope of work as independently verifiable true-or-false statements about the finished work, never checklist steps, each traced to the requirement or design decision it comes from. For a caller that needs a Definition of Done on its own; in elaboration the acceptance-criteria-writer writes it with the criteria. |
| dynamodb-schema-access-pattern-reviewer | test | Reviews the DynamoDB stores of one repository's data-model spec: whether each access pattern it states can be served by the keys and indexes it states, at the stated capacity, without a scan or client-side filtering, and whether each store has the key attributes, indexes, access patterns and expiry attribute the detailed design records. Returns findings the data-model author can correct without interpretation; changes nothing. |
| spec-reviewer | test | Reviews one repository's three specification documents (the API, event and error contracts, the data model, and the acceptance criteria) against the specs-and-Tasks criteria I1 to I7 of the review standard, once, and returns findings a document's author can correct without interpretation; changes nothing. |
| acceptance-criteria-reviewer | test | Reviews acceptance criteria and Definition of Done statements for testability, completeness and ambiguity: whether a test can be derived from each without interpretation, with boundary and failure cases covered; reports findings, never fixes. For a caller that wants criteria checked on their own; in elaboration spec-reviewer reviews the criteria document with the specs. |
| event-schema-reviewer | test | Validates event contracts against the project's standard event and each event's payload schema — event type names, passed values, publishing conditions, consumer obligations, retry/DLQ behavior. |
| graphql-schema-reviewer | test | Reviews the GraphQL contracts of a specification against the architecture and detailed design that record the API and against AppSync patterns: types, operations, resolver and data-source mappings, authorization modes and directives, error shapes, pagination and naming; reports findings, never fixes. For a caller that wants a spec's GraphQL contracts checked. |
| review-dispute-decider | approve | Rules on a review dispute between a maker and its reviewer, from the evidence the two sides wrote: each spec review finding a specification document's author disputes (the finding stands, with the directive the author applies, or the document stands), and a PRD draft the prd-writer and the prd-alignment-verifier could not converge on (accept or reject); writes no document content and no analysis of its own. |

## Planning and Scoring

Elaboration starts `task-decomposer` and `task-dependency-mapper`; `task-dependency-assessment` also starts the mapper for a Task created outside elaboration, `dependency-assessment` starts `epic-dependency-assessor`, and `wsjf-scoring` starts `wsjf-scorer`. Elaboration writes Stories by script, so `story-bead-writer` serves a Story written outside it. The reviewers are available to a caller that chooses them.

| Agent | Category | Purpose |
| --- | --- | --- |
| task-decomposer | execute | Decomposes what one Story builds into coherent, sized build Tasks in one repository. |
| task-dependency-mapper | execute | Maps the build dependencies between Tasks: an edge wherever one Task cannot be built until another is, because it consumes something the other provides. Proposes the cross-Story edges among the Tasks of one Epic's Stories, or every edge to or from one Task created outside elaboration; writes no edge itself. |
| epic-dependency-assessor | plan | Proposes and validates the Epic-to-Epic edges to and from ONE Epic, by the shared-item rule of the epic-sequencing skill, and accounts for every owned edge standing on it; scores nothing and applies nothing. |
| wsjf-scorer | execute | Judges the WSJF inputs of work items under the wsjf skill's rubric: for an Epic its user-business value, time criticality and their confidence from its PRD, and its job size estimate while it is not sized from its Tasks; for the Tasks of an Epic their job sizes. Writes the judgments; computes no RR-OE and no WSJF, and writes nothing to a bead. |
| wsjf-scoring-reviewer | test | Reviews the job sizes in a set of Task WSJF judgments for consistency, evidence and defensibility against the wsjf skill's rubric and recomputes the arithmetic; reports findings, never fixes. For a caller that wants a scoring run checked. |
| story-bead-writer | execute | Writes the title and description of ONE Story bead, a single-repository container paired with a spec set, and names the work outside the Story's repository that the Epic's closure in the matrix holds. For a caller that needs a Story written outside elaboration; elaboration writes its Stories by script. |
| user-story-reviewer | test | Reviews user stories (persona, goal, benefit and acceptance criteria) for completeness, testability and scope against the work each story covers and the spec it cites; reports findings, never fixes. For a caller that holds user stories, such as a PRD's or a person's backlog. |
| beads-format-validator | test | Validates that Beads issues are structurally complete (title, acceptance criteria found where the beads contract looks, dependencies that resolve, spec links that resolve) and obey the hierarchy rule; reports defects, never fixes. For a caller that wants a set of issues checked before work starts. |

## Built Version

`built-version` starts the comparer and, when it records a difference, `architecture-maintainer` and the conformance reviewer, after a Story's deploy to AWS dev is verified.

| Agent | Category | Purpose |
| --- | --- | --- |
| built-architecture-comparer | test | Compares the code one Story built with the approved architecture and design headings that describe the stacks and entries it built, and records each difference as an in-review view under built/<element>/, citing the code by file and line. |
| architecture-conformance-reviewer | test | Checks, without modifying anything, that a correction of the effective architecture documents describes each element exactly as the built views of a Story record it, at every scope, with conforming front matter and placement and section 2 untouched. |

## Spec Freshness

No workflow starts these agents; they remain for a spec written well before its build.

| Agent | Category | Purpose |
| --- | --- | --- |
| spec-freshness-lead | orchestrate | Routes spec freshness checks to validators and aggregates findings into one freshness packet. |
| spec-currency-validator | test | Checks, before implementation begins, that a specification still matches the project: every module, interface, contract, data model, file path and convention it references still exists and still matches, each claim classed current, drifted or unverifiable with evidence. For a caller that holds a spec written some time before its build. |
| dependency-change-detector | test | Detects dependency version and contract changes since a specification was written, by diffing manifests and lockfiles against the spec-time reference and checking changed contracts, classing each as unchanged, reconciled in the spec, or needing reconciliation. For a caller that holds a spec written some time before its build. |

## Test Design

`tdd-red` starts the writers its contract's surfaces call for (`tdd-unit-test-generator` always). The other agents here are available to a caller that chooses them.

| Agent | Category | Purpose |
| --- | --- | --- |
| test-design-lead | orchestrate | Routes spec acceptance criteria to test writers, confirms Red (every new test fails), and assembles the Red readiness packet. |
| tdd-unit-test-generator | test | Writes failing unit tests, including cdk synth assertion tests of CDK stacks, from acceptance criteria before the implementation exists and confirms each fails for the intended reason; and, in update mode, rules on every existing test of any kind an implementer names (update, delete or keep, citing the contract) and applies the ruling. Python and TypeScript, back end, front end and CDK. |
| consumer-driven-contract-test-writer | test | Writes failing consumer-driven contract tests from the spec's API and event contracts. |
| security-test-case-designer | test | Designs failing security test cases from the threat model: abuse cases, negative paths, authorization matrices. |
| aws-integration-test-writer | test | Writes failing integration tests covering the event delivery path the effective architecture describes, hop by hop. |
| playwright-e2e-web-test-writer | test | Writes failing Playwright E2E web tests for UI and API flows from spec acceptance criteria. |
| performance-benchmark-writer | test | Writes failing performance benchmarks with budgets from the spec's non-functional requirements. |
| xcuitest-writer | test | Writes failing XCUITest suites for iOS features from spec acceptance criteria pre-implementation, confirming each fails for the intended reason. |
| espresso-test-writer | test | Writes failing Espresso suites for Android features from spec acceptance criteria, confirming each test fails for the intended reason. |
| mobile-e2e-test-writer | test | Writes failing Detox and Maestro E2E tests for React Native and cross-platform mobile flows before implementation, confirming each fails for the intended reason. |
| ml-evaluation-tester | test | Writes and runs ML evaluation suites — matching quality, recommendation relevance, embedding drift — confirming each fails before the component exists. |
| data-pipeline-test-writer | test | Writes failing data pipeline tests — ETL correctness, CDC ordering, data quality, replay safety — confirming each fails for the intended reason. |
| acceptance-criteria-coverage-assessor | test | Establishes, before any test is written, which acceptance criteria the repository's existing tests already encode and which are gaps, and — when every criterion is covered — runs only those tests and rules whether they are red, already-satisfied or not-encoded. Use before Red to avoid duplicate tests or a manufactured red for behaviour that already exists. Never writes or repairs a test. |
| test-plan-strategy-reviewer | test | Reviews a feature's test plan and authored suites at the strategy level — balance across unit, contract, integration, E2E, security and performance layers, test investment in the spec's highest risks, feasibility of the environments the tests need, duplication and contradiction between suites — and reports findings only. |
| test-isolation-specialist | test | Validates that tests are independent — no shared mutable state, no order dependence, self-cleaning fixtures — by static inspection and by running the suites in shuffled order and repeatedly, and reports each isolation defect with a reproduction; never fixes. |
| test-strategy-decider | approve | Decides a feature's test strategy — pyramid shape across test layers, environment matrix per platform, coverage thresholds — from strategy analyses and reviewer findings others produced, with a recorded rationale and rejected alternatives; generates no analysis of its own. |

## Implementation

`tdd-green` starts `implementation-lead` to select the implementers, then each selected implementer in turn. Every implementer loads the `implementer-contract` skill. `task-to-deploy` also starts `cdk-stack-author` for an infrastructure Task.

| Agent | Category | Purpose |
| --- | --- | --- |
| implementation-lead | orchestrate | Selects the implementer(s) whose specialties cover a Task, in build order, from the Task's build contract — its spec documents and the architecture views it was designed against. |
| chassis-extension-implementer | execute | Implements Lambda handlers as chassis superclass extensions for API endpoints and event consumers; writes minimum code to pass failing unit tests. |
| api-gateway-cdk-implementer | execute | Implements API Gateway resources, methods, and authorizers in CDK; writes minimum code to pass failing unit tests. |
| cdk-stack-author | execute | Writes AWS CDK stacks, constructs and app wiring in Python for an infrastructure Task, as the Task, its spec, the provisioning intent and the architecture give them, with the minimum change that makes the failing synth assertion tests pass. Never deploys. |
| event-api-client-implementer | execute | Implements the calls a service makes to the project's central event API to publish the project's events. |
| event-driven-consumer-implementer | execute | Implements the handler code of a routing rule's target, for whatever target type the target's owner chose. |
| dynamodb-access-layer-implementer | execute | Implements DynamoDB access patterns from the data model spec; writes minimum code to pass failing tests. |
| postgresql-access-layer-implementer | execute | Implements Aurora PostgreSQL access patterns through the RDS Data API from the data model spec, and the schema migrations they need; writes minimum code to pass failing tests. |
| power-tools-configuration-implementer | execute | Configures Lambda Power Tools — structured logging, tracing, metrics, idempotency — on Lambdas built on the chassis; configures, never rebuilds. |
| cognito-lambda-trigger-implementer | execute | Implements Cognito Lambda triggers — sign-up, confirmation, token customization, custom auth challenges — on the chassis the architecture describes. |
| webauthn-implementer | execute | Implements WebAuthn passkey flows across web clients and the Cognito-backed auth stack: registration and authentication ceremonies with client-side handling. |
| cds-ui-implementer | execute | Implements a Task's web UI components and pages in the application repository with the Configurable Design System (cds) applied by construction, from the supplied cds bundle or the live design system, and audits the changed UI against it before reporting; writes the minimum code that makes the failing tests pass. |
| nextjs-component-implementer | execute | Implements the non-visual React/Next.js work — component state, data fetching, Next.js routing — writing minimum code to pass failing unit tests. Visual component and page work goes to cds-ui-implementer, which builds with the cds design system. |
| appsync-cdk-implementer | execute | Implements AppSync GraphQL APIs in CDK: schema wiring, resolvers, data sources, authorization. |
| appsync-client-subscription-implementer | execute | Implements AppSync client subscriptions for real-time web features. |
| ios-swiftui-implementer | execute | Implements iOS features in SwiftUI; writes minimum code to pass failing XCUITest suites. |
| android-compose-implementer | execute | Implements Android features in Kotlin and Jetpack Compose; writes minimum code to pass failing Espresso suites. |
| react-native-implementer | execute | Implements React Native cross-platform mobile features; writes minimum code to pass failing Detox and Maestro tests. |
| bedrock-integration-implementer | execute | Implements the code that calls Amazon Bedrock foundation models - Converse and ConverseStream calls, prompt assembly from specified templates, guardrail and prompt-cache settings on the call, structured-output parsing, and inference error handling - writing minimum code to pass failing tests. Embeddings calls belong to vector-search-embeddings-implementer. |
| llm-observability-implementer | execute | Implements LLM observability — prompt/response logging, token and cost metrics, drift alerts — writing minimum code to pass failing tests. |
| sagemaker-implementer | execute | Implements the code that runs models on Amazon SageMaker AI as the ml-training-designer and ml-inference-designer designs record them - training job launch and training entry scripts, model registration, inference handler scripts, and the calls that invoke real-time, serverless and asynchronous endpoints or start batch transform - writing minimum code to pass failing tests. Endpoint and other resource provisioning in CDK belongs to cdk-stack-author. |
| applied-ai-services-implementer | execute | Implements the code that calls the AWS pre-trained AI services as the applied-ai-services-designer design records it - Amazon Textract document extraction, Amazon Rekognition image and video analysis, and Amazon Comprehend text analysis and PII detection - with their synchronous and asynchronous paths, result paging, confidence thresholds and error handling, writing minimum code to pass failing tests. Foundation-model extraction belongs to bedrock-integration-implementer. |
| agentcore-agent-implementer | execute | Implements custom AI agent code on Amazon Bedrock AgentCore as the ai-agent-designer design records it - the Strands (or other specified framework) agent and its AgentCore Runtime entrypoint, AgentCore Memory sessions, tool wiring through AgentCore Gateway and MCP, and outbound credentials through AgentCore Identity - writing minimum code to pass failing tests. MCP servers and Gateway targets belong to mcp-server-implementer; direct model calls to bedrock-integration-implementer. |
| vector-search-embeddings-implementer | execute | Implements vector search and embeddings for ML features — embedding generation, index read/write, similarity queries. |
| matching-algorithm-implementer | execute | Implements matching algorithms - scoring functions, ranking and tie-breaking, candidate filtering, score normalisation and the composition of these stages into the specified matcher - writing minimum code to pass failing tests. |
| recommendation-engine-implementer | execute | Implements recommendation engine components for ML features; writes minimum code to pass failing unit tests. |
| behavioral-signals-implementer | execute | Implements behavioral signal capture and feature pipelines feeding matching and recommendation models; minimum code to pass failing tests. |
| mcp-server-implementer | execute | Implements MCP servers on AWS, including AgentCore Gateway-fronted deployments — tool definitions and schemas, authorization, transport config, CDK deployment wiring. |
| glue-etl-implementer | execute | Implements Glue ETL jobs for batch data processing; writes minimum code to pass failing data-pipeline suites. |
| kinesis-stream-implementer | execute | Implements Kinesis stream producers and consumers — record serialization, partition keys, checkpointing — writing minimum code to pass failing data-pipeline tests. |
| dynamodb-streams-cdc-implementer | execute | Implements change data capture from DynamoDB Streams; writes minimum code to pass failing data-pipeline test suites. |
| s3-data-lake-implementer | execute | Implements S3 data lake layout, partitioning, and lifecycle policies; writes minimum code to pass failing data-pipeline tests. |
| athena-redshift-analytics-implementer | execute | Implements Athena queries and Redshift analytics models over the data lake — tables, views, SQL — writing minimum code to pass failing data-pipeline tests. |
| payments-integration-implementer | execute | Implements Stripe payment features: checkout sessions, webhook handlers built on the chassis, subscription lifecycle, refunds, and idempotent operations, with secrets in Secrets Manager. |
| email-notification-implementer | execute | Implements transactional and notification email features: responsive templates, rendering pipelines, delivery through Amazon SES, and bounce/complaint handling. |

## Code Quality

`tdd-refactor` starts `code-refactoring-specialist`, which decides which refactorings the changed files need. The other agents here are available to a caller that chooses them.

| Agent | Category | Purpose |
| --- | --- | --- |
| code-quality-lead | orchestrate | Routes refactor work to specialists, verifies tests stay green after every change, and assembles the refactor evidence packet. |
| complexity-analyzer | plan | Analyzes complexity and duplication in a green-tested change set and returns a prioritized refactor recommendation memo, with the optimizer specialties (Lambda, DynamoDB cost, front-end performance, lint fixing) the change calls for; performs no refactoring. |
| code-refactoring-specialist | execute | Refactors the code a change touched for clarity, cohesion, less complexity and less duplication without changing behavior: decides which refactorings the changed files need (none is a valid answer), applies them through GitNexus (impact before each symbol, rename for every rename, detect_changes before finishing), and keeps the test suite green or gives up so the caller restores the tree. |
| lint-finding-fixer | execute | Fixes the lint, format and type-check findings of a check report on a change set with the smallest style-level change, keeping tests green; never suppresses or reconfigures a rule. |
| lambda-performance-optimizer | execute | Applies measured Lambda performance optimizations — cold start (init work, imports, bundle size), client and connection reuse, hot paths — to Lambda code whose tests are green, and recommends memory and timeout values with evidence, without changing behavior. |
| dynamodb-cost-optimizer | execute | Reduces the DynamoDB cost of code whose tests are green within the approved data model — scans replaced by keyed queries, batching, projections, pagination, fewer round trips — and recommends capacity-mode and index changes with a stated cost basis, without changing behavior or data semantics. |
| frontend-performance-optimizer | execute | Applies measured frontend performance optimizations — bundle trimming, code splitting and lazy loading, render-path fixes, Core Web Vitals (LCP, INP, CLS) — to React and Next.js code whose tests are green, without changing behavior, accessibility or visual output. |
| code-correctness-reviewer | test | Independently reviews a refactor or optimisation change set for correctness regressions and behavioral drift: re-runs the test suite itself, compares contracts, error and data semantics and side effects before and after, and flags modified, weakened or skipped tests and suppressed lint rules; reports findings, never fixes. |
| accessibility-validator | test | Validates UI changes against WCAG 2.2 A/AA — contrast, keyboard navigation, ARIA, focus management, screen-reader flows — reporting violations with locations and remediations; never fixes. |

## Integration Testing

No workflow starts these agents; each is available to a caller that chooses it.

| Agent | Category | Purpose |
| --- | --- | --- |
| integration-testing-lead | orchestrate | Read-only selector a caller invokes to choose the integration suites for a change when it cannot derive them from declared contract surfaces. Chooses the fewest applicable suites and whether provisioning must precede them, returning suites, provisionEnv and rationale. Does not dispatch workers, run tests, aggregate results, classify failures or judge gates. |
| cross-repo-integration-test-coordinator | orchestrate | Sequences cross-repo integration test runs over the event chain, aligns environment state between repos, and routes consolidated results to its caller. Coordinates only — runs no tests. |
| test-environment-provisioner | execute | Provisions and resets integration test environments — the event path, functions and data stores the suites depend on — confirming readiness. |
| aws-integration-test-runner | test | Runs AWS integration test suites against the provisioned test environment, reporting structured pass/fail, coverage, and flakiness results. |
| event-flow-tester | test | Tests event flows end-to-end through the EventBridge-SQS-Lambda chain, verifying delivery, routing, retry, and dead-letter behavior per hop. |
| data-consistency-checker | test | Verifies data consistency across services and stores after integration and event-flow runs — partial writes, orphaned records, divergent state. |
| cross-service-contract-tester | test | Runs contract tests across service and repo boundaries, verifying providers and consumers honor approved API and event contracts. |
| flaky-test-detector | test | Verifies intermittent test failures via repeated controlled reruns; reports verified-flaky tests as findings only — never edits or disables tests. |
| root-cause-analyst | plan | Diagnoses a bug bead read-only: the reproduction, the root cause, the distinct defects behind it, the files a fix must change, the blast radius, the surfaces the fix touches, and the repository it lives in; never fixes. |

## Adversarial Validation

`adversarial` starts the attackers its lanes call for against the designated test environment and test identities the caller names, then `adversarial-critique-adjudicator`. No build or deploy step runs it.

| Agent | Category | Purpose |
| --- | --- | --- |
| adversarial-review-loop-supervisor | orchestrate | Sequences the adversarial validation loop: testers attack project code in designated test environments only; the Adversarial Critique Adjudicator rules on findings, which route back until pass or loop-limit escalation. |
| injection-attack-tester | test | Probes this project's endpoints in designated test environments only for SQL, NoSQL, command, and template injection; reports each confirmed path with a minimal reproduction. |
| auth-bypass-tester | test | Attempts auth bypass — token forgery, session fixation, flow skipping — against the project's auth flows in designated test environments only, reporting each confirmed bypass. |
| permission-escalation-tester | test | Attempts horizontal and vertical privilege escalation against this project's own IAM and authorization model in designated test environments only, reporting each confirmed escalation with a minimal reproduction. |
| race-condition-tester | test | Probes this project's concurrent flows in designated test environments only for race conditions and idempotency gaps — TOCTOU, double-spend, lost updates, replay duplication — reporting each defect with a minimal reproduction. |
| contract-violation-tester | test | Sends contract-violating inputs — malformed payloads, type/range violations, schema mismatches — across the project's service boundaries in designated test environments only. |
| dependency-cve-auditor | test | Audits the project's Python and Node dependencies for known CVEs, scoring severity and exploitable transitive paths. |
| dos-resilience-tester | test | Probes load and resource-exhaustion resilience in designated test environments only, reporting where throttling, backpressure, or quotas fail; findings are competitive, not gate-stopping. |
| data-exposure-scanner | test | Scans the project's responses, logs, and storage in designated test environments only for data exposure — leaked secrets, PII, over-returned fields, unencrypted storage — reporting each confirmed exposure. |
| infrastructure-security-scanner | test | Scans project IaC and deployed test infrastructure, designated test environments only, for public exposure, over-broad IAM, missing encryption, and open security groups, reporting each with a minimal reproduction. |
| adversarial-critique-adjudicator | approve | Rules on each adversarial finding whether it is real, its severity, and whether it is constitutive (a hard stop) or competitive (a tradeable concern), with a rationale per finding; the referee whose rulings implementers cannot downgrade. |

## Deployment and Landing

The `deploy` workflow starts `smoke-test-author` and then `dev-deployer`. A Story's deploy pipeline publishes, synthesizes and deploys with no agent and, when one of those steps fails, runs `story-deploy-fix`, which starts `deploy-failure-fixer`. `settle` starts `worktree-lander`. Deploys go only to AWS dev; the other agents here are available to a caller that chooses them.

| Agent | Category | Purpose |
| --- | --- | --- |
| deployment-lead | orchestrate | Routes the feature deployment sequence, validates preconditions per step, and assembles the deployment evidence packet. |
| smoke-test-author | test | Writes, before the deploy, the smoke tests that verify a change's critical paths against the endpoints of a deployment, parameterized by environment variables so the deploy session can run them against AWS dev once it has deployed. Never deploys and never runs them against a deployment. |
| dev-deployer | execute | Deploys one repository to AWS dev by the mechanism the repository deploys by (cdk deploy of the affected stacks, or the repository's own deploy path such as a static-site build, S3 sync and CloudFront invalidation), then runs its smoke tests or names the one command that runs them. Never deploys to any other environment and never writes code. |
| deploy-failure-fixer | execute | Diagnoses a failed package publish, cdk synth, cdk deploy to AWS dev or stack verification from its output and the CloudFormation stack events, fixes the CDK (or whatever else the deploy needs) in the Story's worktree, runs the repository's synth assertion tests, corrects a test the fix proves wrong, and names the command that runs them. Never deploys, commits or publishes. |
| worktree-lander | execute | Lands the work in a git worktree: commits every change through the repository's hooks (fixing every finding they report, never bypassing them), and when asked pushes the branch and opens its pull request with the project's PR command. Never pushes to the default branch and never merges. |
| github-actions-pipeline-implementer | execute | Writes and changes a repository's GitHub Actions workflows: OIDC authentication to AWS with no stored credentials, dependency and build caching, and the build, test, lint and deploy jobs the repository's own commands define. A specialist a caller chooses when a repository's CI/CD workflows must be created or changed. |
| cdk-infrastructure-drift-detector | test | Detects drift between a repository's deployed CloudFormation stacks and its CDK app (cdk diff, CloudFormation drift detection, template comparison) and reports each divergence with evidence; read-only, never remediates. A specialist a caller chooses to check deployed infrastructure against its code. |
| slo-error-budget-designer | plan | Designs a deployed service's SLOs and error budgets: SLIs from the CloudWatch metrics it emits, targets and windows traced to its NFRs, error budget policy and multi-window burn-rate CloudWatch alarms; recommends, never adopts. A specialist a caller chooses when a service needs SLOs. |
| finops-analyst | plan | Models what a feature costs to run on AWS before it ships — unit economics, scaling cost curves across load scenarios, budget impact, cost cliffs — and ranks cost recommendations; decides nothing. A specialist a caller chooses for a pre-deployment cost analysis. |
| incident-response-runbook-designer | execute | Writes a deployed feature's operational runbooks — incident response keyed to its alarms and SLIs, rollback steps that match its deployment strategy, and disaster recovery (backup, restore, failover) for its AWS resources — with every referenced command and resource verified. A specialist a caller chooses when a feature needs runbooks. |
| production-readiness-review-facilitator | orchestrate | Coordinates a production readiness review: checks the required artifacts exist (rollout result, smoke test results, drift report, SLO design, runbooks), routes each to the reviewer charged with it, and assembles the readiness packet with the reviewers' findings verbatim; never decides readiness. A coordinator a caller chooses before a production deployment. |
| deployment-strategy-decider | approve | Decides one repository's deployment strategy (rollout mechanism such as Lambda alias traffic shifting, canary, blue-green or all-at-once; canary health criteria; rollback triggers) from analyses others produced (rollout options and risk, FinOps, SLO design, drift), with a recorded rationale; produces no analysis. A specialist a caller chooses when a rollout must be decided. |

## Documentation

`documentation` starts `documentation-currency-auditor`, then each writer it assigns stale documents to, each followed by `documentation-accuracy-reviewer`. `filing-clerk` files a fact in the documentation vault when a person or the steward asks.

| Agent | Category | Purpose |
| --- | --- | --- |
| documentation-lead | orchestrate | Routes documentation work for shipped changes, tracks artifacts lacking current docs, and reports documentation currency. |
| documentation-currency-auditor | test | Audits which documents a change leaves stale or missing, with cited evidence, and assigns each stale document to the documentation writer whose kind covers it (API reference, README, changelog, user guide, or internal and technical documents); names the specification files the change contradicts. Read-only. |
| api-documentation-writer | execute | Updates the human-readable API reference documents of shipped APIs from their OpenAPI and GraphQL specifications: endpoint and operation guides, request, response and error examples, SDK snippets. Never edits a specification file. |
| readme-writer | execute | Writes and maintains README files — setup, usage, onboarding — derived from shipped code and pipelines. |
| changelog-writer | execute | Writes the changelog entries for a change before it merges, from the change and the conventional commits on its branch, in the project's changelog format, flagging breaking changes and recommending the semantic version increment. Never decides, sets or bumps a version. |
| user-guide-writer | execute | Updates user-facing feature guides and walkthroughs, for the people who use the product, from the spec and the shipped behaviour. Not internal or technical documents, READMEs, changelogs or API reference documents. |
| developer-documentation-writer | execute | Updates a repository's internal and technical documents so they match the shipped code: developer guides, design and implementation notes, module and service documentation, configuration references and contributing guides. Not READMEs, changelogs, API reference documents, user guides or specification files. |
| documentation-accuracy-reviewer | test | Reviews the documents a documentation writer updated for a change against the behaviour the change ships, claim by claim, and reports each inaccurate claim and each uncovered behaviour with cited evidence. Read-only; never fixes. |
| filing-clerk | execute | The documentation filing clerk for the project's documentation vault. Hand it a fact, decision, definition, or note and it (1) searches the project's Obsidian vault — fast, from several angles — to see whether it is already documented, (2) hunts for any single-source-of-truth violation (an unmarked duplicate of something canonical), (3) if the fact is genuinely new, decides the one correct home and files it there with proper classification frontmatter, and (4) reports what it did and any conflicts for the owner to adjudicate. Use PROACTIVELY whenever the owner says things like "if we don't have it already, note that…", "file this", "document that…", "make sure it's written down somewhere", "capture this", "record that we decided…", "add … to arc42 / the glossary / the docs", or offloads a fact so the owner won't forget it. Examples: "note in arc42 somewhere that we use Amazon Bedrock AgentCore and the Strands Agents SDK for our agent" → clerk checks the SAD, files under §4 Solution Strategy if absent; "define 'aging authority' in the glossary if it isn't there" → clerk searches, adds a glossary term; "record that student verification uses SheerID" → clerk finds the right tech/spec doc and files it. |

## Cumulative Regression Assurance

`task-to-deploy` starts the assessor to write the regression scope and, after Green, the mapping of tests to requirements; the reviewer reviews each.

| Agent | Category | Purpose |
| --- | --- | --- |
| regression-impact-assessor | plan | Maps the components a Task changes to every current requirement they can affect, across all PRDs and the repositories that consume them, and to the unit, contract, integration and nonfunctional test layers each requires — before Red as the regression scope, after Red as the final mapping to actual test IDs and JUnit-reporting run commands — retaining earlier requirements unless an accepted source supersedes them. |
| regression-coverage-reviewer | test | Independently reviews a regression scope or final regression mapping against the actual requirement sources across PRDs, the changed code and the test assertions — completeness of discovered requirements and test layers, preservation of earlier requirements and tests, source-backed supersession, and, for a mapping, that the mapped tests exist, assert the obligations and are collected by the declared commands — and approves it or returns concrete findings. |

## Workflow Helpers

Sessions the named workflows start for one mechanical or judging step.

| Agent | Category | Purpose |
| --- | --- | --- |
| test-command-resolver | execute | Finds the command a repository itself declares for running its whole test suite — from its AGENTS.md or CLAUDE.md, else the test task of its Taskfile — and returns it exactly as declared, or a resolution error naming the files read. Runs nothing and changes nothing. |
| test-failure-parser | execute | Reads the saved output of one test-suite run and names every failure it reports — each failing test, and each test file the runner could not load — with the output line that names it and the runner's final summary, whatever the test runner. Never reruns the suite, fixes code or changes the log. |
| cds-live-auditor | test | Audits the UI files a Task changed against the live Configurable Design System (cds) when no mockup or cds bundle was supplied, and rules each finding. |
| cds-finding-reviewer | test | Rules on the findings a deterministic cds audit of a Task's changed UI could not rule on - each class name the supplied cds bundle's stylesheets do not name - as a violation, allowed, or a cds gap, against the bundle and the configured design system; changes no file. |
| shared-capability-reviewer | test | Rules, for each definition a deterministic reuse check could not rule on, whether a function a Task added duplicates a behaviour a shared capability (a shared library, layer, chassis or service) provides to its consumers — duplicate or not-duplicate, with one sentence of reason. Reads only the named function and the provides entry; changes nothing. |
| workflow-command-runner | execute | Executes one workflow-supplied checksum-guarded deterministic command and returns its exact compact machine receipt; never interprets or authors its payload. |

## Standalone

Reached through the `polyrepo-router` skill or the `/polyrepo-steward` command; `deploy-mechanism` also asks it what a repository publishes and deploys.

| Agent | Category | Purpose |
| --- | --- | --- |
| polyrepo-steward | execute | The fleet's caretaker and the place to ask about the project's repositories; ask it first whenever work involves more than one repository. Carries out the fleet's routine management and keeps its records true, but never authors or edits a repository's content; it says when its templates, master copies or tool need to change, and specialist agents write the changes. |

## AWS service coverage

Each entry of the AWS specialist catalog is covered by one design specialist, and in one case
two (entry 19). The build agents are those that write the service's own code: handlers, access
layers, jobs, clients and resolvers. `cdk-stack-author` writes the CDK stacks that provision every
service below, so it is not repeated in each row; "none" means no build agent other than it writes
code for the service.

| # | Catalog entry | Design specialist | Build agents |
| --- | --- | --- | --- |
| 1 | Ephemeral Compute | lambda-function-designer | chassis-extension-implementer, power-tools-configuration-implementer, lambda-performance-optimizer |
| 2 | Container Orchestration | container-service-designer | none |
| 3 | Kubernetes Control Plane | kubernetes-cluster-designer | none |
| 4 | Virtual Machine & Scaling | ec2-fleet-designer | none |
| 5 | Batch & HPC Processing | batch-compute-designer | none |
| 6 | Relational Database | relational-database-designer | postgresql-access-layer-implementer |
| 7 | Key-Value & Wide-Column | dynamodb-table-designer | dynamodb-access-layer-implementer, dynamodb-streams-cdc-implementer, dynamodb-cost-optimizer |
| 8 | In-Memory Caching | cache-designer | none |
| 9 | Graph Database | graph-database-designer | none |
| 10 | Document Database | document-database-designer | none |
| 11 | Time-Series Database | time-series-database-designer | none |
| 12 | Object Storage | object-storage-designer | s3-data-lake-implementer |
| 13 | Block & File Storage | block-and-file-storage-designer | none |
| 14 | Core Network Fabric | vpc-network-designer | none |
| 15 | Load Balancing | load-balancer-designer | none |
| 16 | DNS & Edge Delivery | dns-and-edge-designer | none |
| 17 | Synchronous API Gateway | api-contract-designer (REST API) | api-gateway-cdk-implementer, chassis-extension-implementer |
| 18 | GraphQL API | graphql-api-designer | appsync-cdk-implementer, appsync-client-subscription-implementer |
| 19 | Pub/Sub & Messaging | event-routing-designer (EventBridge), queue-and-topic-designer (SNS) | event-api-client-implementer, event-driven-consumer-implementer |
| 20 | Queuing & Worker Integration | queue-and-topic-designer | event-driven-consumer-implementer |
| 21 | Workflow Orchestration | workflow-orchestration-designer | none |
| 22 | Real-Time Streaming | stream-processing-designer | kinesis-stream-implementer |
| 23 | Data Catalog & ETL | data-lake-designer | glue-etl-implementer, s3-data-lake-implementer |
| 24 | Serverless Query | analytics-query-designer | athena-redshift-analytics-implementer |
| 25 | Data Warehousing | data-warehouse-designer | athena-redshift-analytics-implementer |
| 26 | Authorization & IAM | iam-policy-designer | none |
| 27 | Application Authentication | user-authentication-designer | cognito-lambda-trigger-implementer, webauthn-implementer |
| 28 | Cryptography & Secrets | encryption-and-secrets-designer | none |
| 29 | Perimeter & Threat Protection | perimeter-protection-designer | none |
| 30 | Foundation Model Integrator | foundation-model-designer | bedrock-integration-implementer, llm-observability-implementer |
| 31 | RAG & Vector Data | rag-architecture-designer | vector-search-embeddings-implementer |
| 32 | Applied AI Services | applied-ai-services-designer | applied-ai-services-implementer |
| 33 | MLOps Data Prep | ml-feature-pipeline-designer | behavioral-signals-implementer |
| 34 | MLOps Training | ml-training-designer | sagemaker-implementer |
| 35 | MLOps Inference | ml-inference-designer | sagemaker-implementer |
| 36 | Telemetry & Monitoring | monitoring-and-tracing-designer | power-tools-configuration-implementer, llm-observability-implementer |
| 37 | Configuration & Audit | audit-and-compliance-designer | none |

Entries 38 to 41 (Source Control & Artifact, Pipeline Orchestration, Build & Test Execution,
Deployment & Rollout: CodeCommit, CodeArtifact, CodePipeline, CodeBuild, CodeDeploy) have no
design specialist, because the project delivers with GitHub Actions and CDK:
`github-actions-pipeline-implementer` writes the workflows, `dev-deployer` deploys to AWS dev and
`deploy-failure-fixer` fixes a failed deploy.

Across the data entries (6 to 13 and 22 to 25), `data-architect` decides the data itself before
any store is chosen, and `persistence-architecture-specialist` chooses the store for each data
set and which block owns it.

### Topics beyond the catalog

| Topic | Design specialist | Build agents |
| --- | --- | --- |
| Bedrock | foundation-model-designer; rag-architecture-designer for Knowledge Bases; ai-agent-designer for AgentCore | bedrock-integration-implementer, llm-observability-implementer; agentcore-agent-implementer for AgentCore agents |
| AI: retrieval, search and pre-trained AI services | rag-architecture-designer, applied-ai-services-designer | vector-search-embeddings-implementer, recommendation-engine-implementer, matching-algorithm-implementer, applied-ai-services-implementer |
| Machine learning | ml-feature-pipeline-designer, ml-training-designer, ml-inference-designer | behavioral-signals-implementer, matching-algorithm-implementer, recommendation-engine-implementer, sagemaker-implementer; ml-evaluation-tester writes the evaluation suites |
| Custom agents | ai-agent-designer | agentcore-agent-implementer (the agent, its Runtime entrypoint, Memory, Gateway tool wiring and Identity); mcp-server-implementer (MCP servers and Gateway targets) |
| Custom AI patterns | generative-ai-pattern-designer | bedrock-integration-implementer |
| Pure data architecture | data-architect | none: it designs the data, which the engine designers and access-layer implementers then realise |
