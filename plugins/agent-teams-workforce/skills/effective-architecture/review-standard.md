<!-- GENERATED from review-criteria.json by review_criteria.py. Edit review-criteria.json. -->

# Architecture and TRD criteria

One list. The solutions architect develops the architecture and the TRD to it, and the spec
authors develop the specs to it. Reviewers review against it and against nothing else. Each
criterion has a level and a home. A criterion is satisfied by its home document. Nobody asks
a document for detail below its level.

## How to work (all levels)

P1. The acceptance basis is the PRD's business outcomes, settled owner decisions, the
    section 2 constraints and the documentation model's obligations.
P2. A mechanism named in a PRD is a design input, not a business requirement.
P3. The solutions architect decides technical gaps with cited evidence, asking a specialist
    when the gap needs one. Only business requirements that no design can meet together, or
    a conflict with section 2, reach the owner.
P4. AWS behaviour is established from AWS documentation through the AWS MCP Server. State
    assumptions, tradeoffs and regional applicability. Never invent scale.
P5. Cite an arc42 statement by path and heading, guidance by URL, and code by repository,
    revision and file:line. Code that no pipeline built is a hint and is never evidence that
    arc42 is wrong; only code the matrix marks built or deployed is expected to match.
P6. One design fact lives in one home. Every other document links to it.
P7. Never write section 2. Only architecture-maintainer writes arc42. A script promotes.
P8. A finding names the criterion id, the item, the observation with its path and heading,
    and a bounded correction with a condition that shows it is done. A preference is not a
    finding. Something no criterion requires is not a finding.
P9. A review covers only content that is not yet approved. Approved content is reference: it
    is reported only when an unapproved item cannot be correct unless an approved statement
    is wrong. A re-check covers only the corrected items.

## Architecture level: arc42 sections 3 to 8

A1.  A spec author can name the building block, its repository and stack, the owner of each
     store, each interface and its caller, and each event type and its publisher without
     inventing a design.
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
A10. The front matter of each document records repository, view_type, scope, subject, shows
     and lifecycle_state.
A11. Names of blocks, stores, interfaces and event types agree across documents.
A12. Every document stays at architecture level and within its single purpose: no route
     method or path, field name, key or index name, parameter name, metric or alarm name, or
     schema, and no fact outside the document's subject.
A13. The design meets each PRD outcome it concerns and no section 2 constraint is broken.
A14. Each diagram renders, is readable, and agrees with the text beside it.

## Technical-requirement level: the TRD

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
    shape that belongs to a spec.

## Implementation level: the specs and the Tasks

These are not reviewed in the architecture review. They are listed here so that everyone can
see where each detail lives.

I1. Each route has its method, path, authorizer, request and response fields and status
    codes.
I2. Each store has its key attribute names, indexes, access patterns and expiry attribute.
I3. Each event names its publishing service and has the values passed to the
    shared-events-service API.
I4. Configuration names, SSM parameter names, and log, metric and alarm names are present
    and are generated with atw-naming.
I5. Idempotency key fields and timeout settings are stated.
I6. Each contract this repository shares with another repository (a route it exposes or
    calls, an event it publishes or a routing rule matches) names the other repository's
    element, and its fields are exactly those of the other repository's spec where that spec
    exists. An event contract names no consumer: a producer's spec names no routing rule or
    target, and a routing rule's spec names the event types it matches.
I7. A Task can name the repository, stack, handler, table, route, event and the shared
    capabilities it must use without inventing a design.
