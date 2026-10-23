<!-- GENERATED from review-criteria.json by review_criteria.py. Edit review-criteria.json. -->

# Architecture and TRD criteria

One list. The solutions architect develops the architecture, its detailed design and the TRD
to it, and reviews and approves them against it; the spec authors develop the specs to it,
and the spec review reviews them against it. Nothing is reviewed against anything else. Each
criterion has a level and a home document, and is satisfied by its home document.

## How to work (all levels)

P1.  The acceptance basis is the PRD's business outcomes, settled owner decisions, the
     section 2 constraints and the documentation model's obligations.
P2.  A mechanism named in a PRD is a design input, not a business requirement.
P3.  The solutions architect decides technical gaps with cited evidence, asking a specialist
     when the gap needs one. Only business requirements that no design can meet together, or
     a conflict with section 2, reach the owner.
P4.  AWS behaviour is established from AWS documentation through the AWS MCP Server. State
     assumptions, tradeoffs and regional applicability. Never invent scale.
P5.  Cite an arc42 statement by path and heading, guidance by URL, and code by repository,
     revision and file:line. Code that no pipeline built is a hint and is never evidence
     that arc42 is wrong; only code the matrix marks built or deployed is expected to match.
P6.  One design fact lives in one home. Every other document links to it.
P7.  Never write section 2. Only architecture-maintainer writes arc42 and the detailed
     architecture. A script promotes.
P8.  A finding names the criterion id, the item, the observation with its path and heading,
     and a bounded correction with a condition that shows it is done. A preference is not a
     finding. Something no criterion requires is not a finding.
P9.  A review covers the content this Epic adds or changes and the content in its reach that
     no Epic's elaboration has approved yet (no matrix approved flag; the effective baseline
     included, as the effective-architecture skill, Lifecycle, the baseline and iteration,
     says). Content an earlier Epic approved is reference: it is reported only when an
     unapproved item cannot be correct unless an approved statement is wrong. A re-check
     covers only the corrected items.
P10. No architecture decision is made by instinct. Every AWS resource the design defines is
     reviewed with the AWS tools (the AWS MCP servers and the aws-core skills) against AWS
     best practice and security best practice, the design has a Well-Architected review, and
     every decision between two or more options states the options considered and the reason
     for the choice; each is recorded in the Epic's review log, to the
     log-architecture-review skill's schema.

## Architecture and design: arc42 and the detailed architecture

Reviewed and approved by `aws-solutions-architect`.

A1.  Anyone who specifies or builds the work can name, from the architecture and design
     documents, the building block, its repository and stack, the owner of each store, each
     interface and its caller, and each event type and its publisher without inventing a
     design.
A2.  Section 5 names each building block the PRD needs, what it is responsible for and what
     it owns. Each store has one owning block and a statement of what it holds.
A3.  Each interface is named with the block that exposes it and who may call it. Trust
     boundaries are explicit: who may call each boundary and what each runtime may call.
A4.  Each event type is named in the event catalog with its producers and description, and
     each routing rule names the event types it matches (or all), its targets and the stack
     that owns it.
A5.  Section 6 shows, for each important scenario and each failure the PRD's outcomes depend
     on, which building blocks interact and in what order. Retry, dead-letter and idempotent
     behaviour are stated as behaviour.
A6.  Section 7 says where each block runs and which stack holds each resource. Values shared
     between stacks are named as shared, by the mechanism section 2 fixes.
A7.  Each rule that applies across blocks is a design fact in section 8 with its reason, in
     the form "Because of X, the address is verified by Y".
A8.  No fact is stated in two documents. Section 6 links to a rule; it does not restate it.
A9.  Every behaviour a shared service, component, layer or library provides is taken from
     it, by the shared-home rule of arc42 section 4 (04-solution-strategy). Each shared
     home's section 5 document states under "Provides" what consumers obtain from it and
     must not implement.
A10. The front matter of each document records the catalog keys the documentation model
     states for its document class: a view records view_type, scope, subject, shows and
     lifecycle_state; a standard or policy records document_class: standard or
     document_class: policy and lifecycle_state, and has no view_type, scope or shows.
A11. Names of blocks, stores, interfaces and event types agree across documents.
A12. Each document holds the facts of its one subject, in the place the architecture
     documentation model gives them: in arc42 when the statement stays true if the code is
     rewritten, otherwise in its document under detailed/ (one component, one feature,
     components working together, or the whole system), linked from the arc42 view of its
     subject.
A13. The design meets each PRD outcome it concerns and no section 2 constraint is broken.
A14. Each diagram renders, is readable, and agrees with the text beside it.
A15. Where the design has an interface, each route has its method, path, authorizer, request
     and response fields and status codes in the detailed design of the component that
     exposes it.
A16. Where the design has a store, it has its key attribute names, indexes, access patterns
     and expiry attribute, and its logical or physical data model, in the detailed design of
     the component that owns it.
A17. Where the design publishes an event, its publishing service and the values passed to
     the project's event-publishing API are in the detailed design of the publishing
     component.
A18. Configuration names, SSM parameter names, and log, metric and alarm names the design
     introduces are in the detailed design of the component that uses them, each generated
     with the project's naming command.
A19. Idempotency key fields and timeout settings are in the detailed design of the component
     that applies them; a timeout is the value its TRD requirement states.
A20. Where the work needs it, a component's internal structure (its classes or modules,
     object and data models with their attributes and types, and the lifecycle of its
     entities) is drawn in its detailed design, in the view types the documentation model's
     list names for it.

## Technical-requirement level: the TRD

Reviewed and approved by `aws-solutions-architect`.

T1. Every requirement has a stable id, a kind, a statement with a checkable value, a source
    and the element it applies to.
T2. Where the design has the element, the TRD carries its obligations: availability,
    latency, security controls, retention, recovery, limits, timeouts and retry counts, that
    logs, metrics and alarms exist, and cost constraints. Cost unit math is kept as evidence
    in the solutions architect's result.
T3. Each shared capability the design uses has one requirement of kind `reuse` naming the
    element, the behaviour and the capability.
T4. No requirement contradicts an effective arc42 statement or section 2, and none creates
    an element.
T5. Every PRD requirement that needs a technical obligation has one.
T6. A requirement says what, with a value. It does not say how, and it holds no name or
    shape that belongs to the architecture and design documents.

## The specs and the Tasks

Reviewed and approved by `spec-reviewer`.

These are not part of the architecture. A spec and a Task carry what their work builds from
the architecture and design documents, by link or as stated there; they decide no design.

I1. Each route has its method, path, authorizer, request and response fields and status
    codes as the detailed design records them.
I2. Each store has its key attribute names, indexes, access patterns and expiry attribute as
    the detailed design records them.
I3. Each event names its publishing service and has the values passed to the project's
    event-publishing API as the detailed design records them.
I4. Configuration names, SSM parameter names, and log, metric and alarm names are present as
    the detailed design records them.
I5. Idempotency key fields and timeout settings are stated as the detailed design records
    them.
I6. Each contract this repository shares with another repository (a route it exposes or
    calls, an event it publishes or a routing rule matches) names the other repository's
    element, and its fields are exactly those of the other repository's spec where that spec
    exists. An event contract names no consumer: a producer's spec names no routing rule or
    target, and a routing rule's spec names the event types it matches.
I7. A Task can name the repository, stack, handler, table, route, event and the shared
    capabilities it must use without inventing a design.
