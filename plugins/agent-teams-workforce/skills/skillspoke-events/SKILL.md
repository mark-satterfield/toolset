---
name: skillspoke-events
description: >-
  Use whenever you design, specify, review or implement anything that publishes, routes or
  consumes a SkillSpoke event: the standard event and its fields, event type names, the path an
  event takes from publisher to consumer, and what a publisher and a consumer must do.
user-invocable: false
expertiseFor:
  resourceTypes: [event, event-bus, event-rule]
  terms: ["domain event", "event-driven", "publishes an event"]
---

# SkillSpoke events

The source is the effective arc42 architecture in the `skillspoke-docs` vault, under
`docs/tech/architecture/arc42/`:

| View | Holds |
|---|---|
| `08-crosscutting-concepts/event-platform-and-envelope.md` | The standard event, the central event API and the events API function, the event type registry, coat-check, routing rules, up to the point a rule forwards an event to its target |
| `08-crosscutting-concepts/event-consumption.md` | What happens after a rule forwards an event: the consumer's SQS queue and DLQ, duplicate suppression, reading a reference payload, applying only newer versions, DLQ reconciliation, the per-service SQS configuration |
| `08-crosscutting-concepts/event-naming-standard.md` | Event type names and their ownership |
| `08-crosscutting-concepts/events-as-observability.md` | The four kinds of event every service emits, the event log, correlation |
| `08-crosscutting-concepts/idempotency.md` | Duplicate suppression in the chassis |
| `08-crosscutting-concepts/retry-and-backoff.md` | The one retry policy and the owner of each retry |
| `05-building-block-view/events-platform/README.md` | What `shared-events-service` and `shared-events-infra` own |
| `06-runtime-view/event-publication-and-delivery.md` | The path every event takes |
| `06-runtime-view/pii-present-event-publication.md` | The publish sequence of an event that carries personal data |
| `06-runtime-view/event-catalog.md` | Event types by owning producer and category |

Read the view that covers your task before you decide anything this skill does not state.

## The standard event

Because every consumer, routing rule and investigation reads one shape, SkillSpoke has one event:
every event, whatever its purpose, is the standard event `SkillSpokeEvent`.

- Because the events service validates every event against the EventBridge schema registry, the
  registry entry is the contract: registry `skillspoke-events`, schema
  `skillspoke@standard-event`, region `us-east-1`
  (`arn:aws:schemas:us-east-1:616930583457:schema/skillspoke-events/skillspoke@standard-event`).
  [`standard-event.schema.json`](standard-event.schema.json), beside this file, is a reading copy;
  the registry content governs.
- The schema is an OpenAPI 3.0 document titled `SkillSpokeEventEnvelope`. Its `AWSEvent` has
  `detail-type` `SkillSpoke Event`, `source` `skillspoke.events-publisher` and a `detail` of type
  `SkillSpokeEvent`.

| Field | Required | Content |
|---|---|---|
| `eventId` | yes | ULID of this publication |
| `eventType` | yes | The event type name (see Event type names) |
| `eventSchemaVersion` | no | Semantic version (`major.minor.patch`) of the event's payload schema, not of the standard event |
| `category` | yes | `business`, `monitoring`, `audit`, `security` or `infrastructure` |
| `domain` | yes | Primary domain of the event; matches `^[a-z][a-z0-9-]*$` |
| `source` | yes | `service`, `region`, `environment` required; `subsystem` optional |
| `timestamps` | yes | `occurredAt`, `publishedAt` required; `expiresAt` optional |
| `trace` | no | When present: `correlationId` required; `causationId`, `parentEventId`, `rootEventId`, `traceId`, `spanId` optional |
| `lifecycle` | no | When present: `phase` (`started`, `in-progress`, `finished`, `finalized`), `outcome` (`success`, `successWithWarning`, `failed`, `canceled`, `timeout`), `severity` (`info`, `warning`, `error`, `critical`), `isError` required; `statusCode`, `statusSummary`, `statusReason`, `retry`, `details` optional |
| `visibility` | yes, by the platform | `piiPresent` (boolean) and `classification` (`public`, `internal`, `restricted`, `pii`, `phi`) |
| `payload` | no | When present: `mode` (`inline` or `reference`), `schemaUri`, `contentType` required; `sizeBytes`, `inline`, `reference` optional |
| `actor` | no | `actorType`, `actorId`, `actorDisplay` |
| `identifiers` | no | `tenantId`, `userId`, `executionId`, `resourceType`, `resourceId`, `parentResourceId` |
| `businessContext` | no | `process`, `step`, `subStep` |
| `tags` | no | Free-form labels |

Three identifiers answer three different questions, so an event carries all three and each keeps
its own meaning:

| Identifier | Answers | Assigned by |
|---|---|---|
| `trace.correlationId` | Which request chain is this part of? | The work that started the chain; carried forward on every hop |
| `eventId` | Which publication is this? | The events service, per publication |
| dedup key (`dedupKey`) | Which fact is this? | The publisher, from the fact itself |

## Categories

The `category` values are `business`, `monitoring`, `audit`, `security` and `infrastructure`
(see The standard event); `audit` and `security` are described below. An error event is one whose
`lifecycle.isError` is true, whatever its category. The kinds of event every service emits
(business, telemetry, process and error events) are described in `events-as-observability.md`.

- Because the end of a process must state its own outcome, telemetry and process events come in
  pairs: one `started` and exactly one `ended`, whose `lifecycle.outcome` says how the work ended
  and whose `lifecycle.details` carries the error category, code and message.
- Because an event may be read by anyone investigating a request, an error or warning event
  carries identifiers and codes (event type, correlation id, trace id, handler and route template,
  error code and class) and no request body or dependency message text.
- Because the audit recorder of `shared-audit-infra` and the seeker's activity history select what
  they store by category, an employee action is an ordinary event with category `audit` and a
  seeker's privacy-sensitive action is an ordinary event with category `security`; each carries
  the provenance (actor, timestamp, action, session, gate outcome) and none of the content.

## Event type names

- Form: `[domain].[entity].[verb]` or `[domain].[subdomain].[entity].[verb]`; pattern
  `^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*){2,3}$`. A name is entirely lowercase, kebab-case inside a
  segment, with dots as the only separator.
- Because a name states a fact that has happened, its last segment is one past-tense, semantically
  precise verb (`registered`, `finalized`, `locked-out`), and a noun belongs in the entity segment
  (`subscription.trial-end.approached`). The verbs `updated`, `modified`, `processed`, `handled` and `transitioned` name no
  particular transition and are not used; `changed` is used only when the entity segment names what
  changed and the signal-only body names the changed keys.
- Because a name must survive service rewrites, database changes, language migrations, team
  reorganization and indefinite replay, it names a business or technical capability and contains
  no service, stack, technology, persistence-operation or deployment identifier.
- Because producers publish facts and the notifications and messaging services decide delivery, a
  delivery channel is never a domain prefix and a name carries fact semantics, not a command.
- Because the payload schema's version is carried in `eventSchemaVersion`, a name has no version identifier.
- Because consumers and replays depend on a name's meaning, a published event type keeps its name
  and meaning; a changed meaning is a new event type.
- Because the outcome is carried in `lifecycle.outcome`, the lifecycle verbs are `started` and
  `ended` only, in matched pairs; a nested workflow emits one pair per step.
- Because a generic event would force every consumer to filter on the publisher's payload, a
  lifecycle producer emits one distinctly typed event per fact rather than one generic event with a
  kind discriminator in its body.

Examples: `identity.user.registered`, `billing.invoice.finalized`, `job-search.results.published`.

## Ownership

| Owner | Owns |
|---|---|
| `shared-events-infra` | The bus `skillSpoke-events`, its resource policy, the archive, the rule that writes every event to the event log, the rule that sends error events (`lifecycle.isError` true) to alert dispatch, the bus SSM parameters |
| `shared-events-service` | The central event API and the events API function (`events-gateway`) behind it, building and validating the standard event, publication to the bus, coat-check, the registry path scheme, the `visibility` vocabulary |
| Each publishing service | Its event types, their registry entries, their payload schemas and payload models, its own OAuth2 app client |
| Each consuming service | Its EventBridge rules, its SQS queue and DLQ, its consumer Lambda, its idempotency table, its grant on the coat-check prefixes it reads |
| `shared-chassis-lib` | The event helper, consumer batch handling, duplicate suppression, the mapping of failures to named errors |
| `shared-apiClient-lib` | The OAuth2 token, the HTTP call and its retries |

- Because a fact that is emitted twice or silently dropped corrupts every consumer, each event
  type has exactly one owning publisher (the single-emitter invariant). Where several trigger
  paths can raise the same fact, the shared owning pipeline is the one point of emission.
- Because an aggregate has authority only over its own facts, it emits only facts it owns, even
  when another aggregate lives in the same service.
- Because a browser holds no service app client and has no path to the private API, a fact about a
  browser interaction is published by the backend context that owns it.

## The path an event takes

```text
sending code -> chassis event helper -> shared-apiClient-lib -> POST /v1/events
  -> the events API function builds, validates, publishes -> bus skillSpoke-events
  -> consuming service's rule -> that service's SQS queue (+ DLQ) -> consumer Lambda
```

- `shared-events-service` is the only builder, validator and publisher of events. Any code can
  send an event; it sends the values of the event and an optional payload in the body of its API
  request, which is not the event, as many times as it needs in one execution.
- The event platform ends where a rule forwards an event to its target. The target queue, its DLQ
  and the processing behind it belong to the consuming service (`event-consumption.md`).
- Because the bus resource policy grants `events:PutEvents` to the events API function's role
  only, the central event API is the one way onto the bus for every SkillSpoke principal.
- Because every service-to-service call identifies its caller through its own app client, and a
  public endpoint would carry PII-bearing events off the private network, the central event API is
  a PRIVATE REST v1 API (`POST /v1/events`) reachable only through the platform `execute-api`
  interface endpoint and authorized by a Cognito user-pool authorizer that checks the
  event-publish scope of a client-credentials token.
- By project convention, all cross-service events flow through one custom bus, `skillSpoke-events`.
- By project convention, delivery is EventBridge rule to SQS to Lambda everywhere: a consumer
  Lambda is triggered by its queue.
- Because events are the primary observability source, a rule in `shared-events-infra` writes
  every event to the event log, the CloudWatch Logs log group `/aws/events/skillSpoke-events`,
  asynchronously after publication. The event log is where a request is investigated; the durable
  record of an employee action is the employee audit trail.

## What a publisher does

1. **Register the event type.** Because the registry is closed-world, the publisher's own stack
   writes one SSM parameter per event type before first publication, at
   `/skillSpoke/{serviceName}/eventRegistry/{seg1}/{seg2}/{seg3}[/{seg4}]` (each dot segment of the
   event type as one camelCase path segment), with the value
   `{category, piiPresent, allowedProducerClient, service}`. Because the entry lives in the
   publisher's stack, a new event type needs no deployment of `shared-events-service`.
2. **Classify the payload model.** Because the registry's `piiPresent` is derived at synth from
   the payload model, every field of the model carries a PII classification and an unclassified
   field counts as PII.
3. **Publish after commit.** Because an event must exist if and only if its state change durably
   committed, a publisher emits from a transactional outbox, from a change-data-capture stream on
   its own store (a DynamoDB stream feeding a publisher Lambda), or from a queue-driven consumer
   after its own conditional write. Because a rejected or failed publication must be replayable,
   the fact stays in that outbox, stream or DLQ until it is accepted. A change-data-capture
   publisher's event-source mapping declares an on-failure destination, bisect-on-function-error,
   a maximum retry count and a maximum record age, and carries an iterator-age alarm, because a
   poison record otherwise blocks every later change on its shard unseen.
4. **Fill in the API request with the chassis event helper.** The helper provides static helpers
   and data structures that the sending code fills in, including its OAuth2 client id and secret.
   They build the body of the API request, which is not the event: `eventType`, `category`,
   `domain`, `timestamps.occurredAt`, the `visibility` block, and any `eventSchemaVersion`,
   `lifecycle`, `identifiers`, `businessContext` and `tags`; the `trace` identifiers of the
   current work (the correlation id and, when one exists, the causation id, available from
   `RequestContext`); the payload when the event has one; and the `dedupKey` and subject account
   id. Code that runs outside the chassis calls `shared-apiClient-lib` itself with the same
   request body.
5. **Pass a dedup key.** Because delivery is at-least-once and `eventId` differs on every
   publication, the publisher derives a dedup key from the fact itself (the entity, the transition
   and the entity's version or sequence) and passes the identical key on every republication.
   Because coat-check keys and access logs carry it verbatim, the key is an opaque token; a key
   derived from an identifier is a keyed hash. Fan-out to several channels keeps one key.
6. **Pass the subject account id** with an event whose payload carries personal data, because the
   coat-check key is `<eventType>/<subjectAccountId>/<dedupKey>` and forget-me finds an account's
   payloads by that prefix.

### What the events service decides for the publisher

- Because a caller could otherwise claim another service's identity, `source.service` and `actor`
  come from the caller's verified OAuth2 client identity: the events API function maps the token's `client_id`
  to a service, requires it to equal the registry entry's `allowedProducerClient`, and sets
  `source.service` from the entry. The actor is the calling service, of type `system`; a user
  subject travels as payload data.
- Because `eventId` and `timestamps.publishedAt` describe the publication, the events API function
  always generates them.
- Because classification must hold even when a payload is opaque, the events API function
  classifies from the event's own fields and the registry entry, and never reads or redacts
  `payload.inline`.
- Because a state change must not be reported before it is durable, the events API function
  returns 202 only after `PutEvents` returns `FailedEntryCount` 0.
- Idempotency of the publish endpoint runs inside the events API function, on its own DynamoDB
  idempotency table; when that table cannot be reached, the API returns 500 and publishes nothing.

| Response | When | What the chassis event helper does |
|---|---|---|
| 202 (`eventId`, `status` `accepted`, `event_type`, `domain`, `event_bus`) | The event is on the bus | Continues |
| 400 | The body is unparseable | Permanent failure |
| 422 with `details[]` naming each failed field | The event fails validation: an unknown field, a missing required value, a `trace` without `trace.correlationId`, an absent or inconsistent `visibility` block (`piiPresent` true with `public`), an unregistered event type, a `category` that differs from the registry entry, a `pii-required` type declared `piiPresent=false`, a caller that is not the entry's allowed producer, a malformed or identifying `dedupKey`, a publisher-supplied reference with `piiPresent=true` | Raises `EnvelopeRejected`; because the request is a contract defect that a retry cannot fix, reports a batch item failure so the message goes to the publisher's DLQ and is redriven after the contract is fixed |
| 403 from the API Gateway authorization layer | Infrastructure drift | Retries with bounded backoff, then dead-letters the message tagged `PublishAuthorisationFailure` |
| 503 | `PutEvents` or a coat-check write failed, or the registry could not be read on a cold cache | Transient: bounded retry with backoff |
| 500 | The idempotency table cannot be reached, or an unexpected fault in the events API function | Not retried; the fact stays in the producer's outbox, stream or DLQ for redrive |

Nothing is stored or published on any non-2xx response.

## Payloads

A payload is the domain-specific content of one event type; many events have none.

- Because a signal-only body makes a duplicate delivery benign and an out-of-order delivery
  self-correcting, an event that tells a consumer an entity changed carries the entity identifier
  and its new version, and not the entity's state.
- Because a consumer with destructive capability could act on a misread signal, a transition
  payload is reduced to the fact: the subject, the from-state, the to-state, the reason and the
  effective time.
- Because two competing events can arrive in the order that hides a failure, a workflow whose
  completion may be partial emits one completion event carrying per-item or per-field outcomes.
- Because an announced resource must be retrievable, a publisher stores the resource durably
  before it publishes the event that announces it.
- Because the published event must fit the EventBridge and SQS size limits, the events API
  function moves an inline payload larger than 262,144 serialized UTF-8 bytes to the coat-check
  bucket and publishes a reference (`payload.mode` `reference`, with `storageType`, `location`,
  `checksum`, `encrypted`). Only the events API function offloads, inside its own invocation; API
  Gateway has no offload feature.
- Because no personal data may transit EventBridge, SQS, a DLQ or the event log, the events API
  function moves the payload of every `piiPresent=true` event to coat-check regardless of size.
- Because API Gateway invokes the events API function synchronously, a request is limited by the
  6 MB Lambda synchronous payload limit before API Gateway's 10 MB limit; the size limits are in
  the Coat-check pattern of `event-platform-and-envelope.md`. A publisher whose `piiPresent=false`
  payload is too large for one request stores it itself and sends a reference.
- Because the coat-check key names the fact and the object is written put-if-absent, a
  republication of the same fact writes no new object.
- Because a coat-check object must outlive every queued reference to it and no longer, current
  objects expire after a configured window whose default is 14 days, the maximum SQS message
  retention.

## Schemas and versions

- The standard event has one schema, in the EventBridge schema registry (see The standard event).
- An event type with a payload may have a payload schema: the one schema authored for an event. Its
  version is the event's `eventSchemaVersion`, `payload.schemaUri` refers to it, and it may be
  registered in the EventBridge schema registry `skillspoke-events`. Registration is optional.
  Some payload schemas are standardized and shared across events (for example the description of
  an S3 object), so every consumer parses that shape the same way.
- Because a path or value must keep its meaning while a consumer still resolves it, a change to the
  standard event or to a payload schema is additive: no property removed, no new required
  property, no narrowed type, no removed enum value. A breaking change is a new version, and a
  breaking change to the standard event deploys in the same `deployment/waves.yaml` wave as
  `shared-events-service` and every publisher it affects.
- Because the same value must decide the same way in every service, an enumeration that decides
  whether an event fires (a threshold set, a trigger-type vocabulary) is one central constant
  shared by every emitter and subscriber, and each member binds to a registered event type.

## Routing

- Because a subscription must change without touching the publisher, a consuming service declares,
  in its own stack, one EventBridge rule for each event type it wants, targeting its own queue.
- A rule may match on any field of the event. Rules most often match the event's metadata
  (`eventType`, `domain`, `category`) and its `lifecycle` fields; a rule that matches a payload
  field is less common and permitted, and ties the rule to that payload's schema.
- Because one subscriber's failure must leave every other subscriber's delivery unaffected, each
  subscriber has its own queue and DLQ and receives its own copy.
- Because a rule that matches PII-present events could otherwise send them outside the account, its
  only permitted target is an SQS queue in the same account; a chassis CDK Aspect fails synth on
  any other target.
- Because a routing mistake must be detectable without failing the publisher, a publication that
  matches no rule succeeds and emits a metric and a structured log naming the event type, the
  source service and the correlation id.
- Because a cold start must not walk a healthy message to the DLQ, each consumer queue has a
  visibility timeout of at least six times the function timeout, long polling, a declared
  retention, a redrive to its DLQ after a `maxReceiveCount` of at least 5 and a DLQ alarm; the
  event-source mapping enables `ReportBatchItemFailures`. `ChassisFunction` derives the bounds.

## What a consumer does

Everything after a rule forwards an event is the consuming service's, as
`event-consumption.md` describes; this section and the next summarize it.

1. **Wait for the contract.** Because acting on an unregistered contract fabricates state, a
   consumer acts on a cross-domain event only once its publisher's registry entry exists.
2. **Read every event as the standard event,** and validate a payload against the event type's
   payload schema.
3. **Suppress duplicates first.** Because EventBridge and SQS deliver at least once, every consumer
   that writes is idempotent: the chassis applies Powertools Idempotency on the consuming service's
   own DynamoDB table, keyed on the dedup key, before the consumer inspects `payload.mode`.
4. **Fail closed on the idempotency table.** Because treating an unreadable table as "no record"
   turns an outage into duplicated side effects, an unreachable table raises the retryable
   `IdempotencyStoreUnreachable`, reported as a batch item failure.
5. **Dereference a reference payload.** When `payload.mode` is `reference`, the consumer reads the
   object through the S3 gateway endpoint under its own `s3:GetObject*` grant on the
   `<eventType>/*` prefix. Because a payload may have expired or been forgotten, `NoSuchKey` maps
   to `ReferenceExpired` (permanent, acknowledged); `AccessDenied` maps to `ReferenceNotReachable`
   (alarmed); a connect timeout is transient.
6. **Report failures per record.** Because one poisoned record would otherwise redrive the whole
   batch and re-apply every sibling, the consumer reports batch item failures per record.
7. **Tolerate any order.** Because EventBridge and SQS may deliver out of order, a state-changing
   event carries a monotonic per-entity version in its payload, and the consumer stores the
   last-applied version and applies an event only when its version is strictly greater.
8. **Fail closed on cost and security.** Because a delayed re-enable must never overtake a
   suspension, a consumer whose projection gates cost or security moves to the less-secure state
   only on an event provably newer than the transition into the more-secure state.

## Retries and dead-letter handling

- Because one policy keeps retries from amplifying load, every retry uses jittered exponential
  backoff with a ceiling and a capped attempt count, and each kind of call has one owner:
  `shared-apiClient-lib` for the call to the central event API (connection errors, 429, 502, 503,
  504), SQS redelivery for a failed consumer handler.
- Because exhaustion must be a visible state, a message that fails `maxReceiveCount` deliveries
  lands in the consumer's DLQ, and a DLQ depth above zero raises a CloudWatch alarm whose state
  change reaches alert dispatch (`shared-ops-infra`) through EventBridge.
- Because a redelivery after an expired record would look like a first attempt, an idempotency
  record is retained longer than the retry horizon that can redeliver the same operation (the SQS
  retry sequence plus the DLQ max-receive window) plus margin; each operation type declares both
  lifetimes together.
- Because the loss of a money, entitlement or audit event corrupts downstream state, a scheduled
  reconciler replays DLQ and authoritative-store deltas into the consumer idempotently until the
  projection converges, and alarms when it does not converge within its declared window.
- Recovery from a contract defect is to fix the registry entry or the publisher, then redrive the
  DLQ into its source queue.

## Correlation

- Because investigation starts from the correlation id, an event that carries `trace` carries
  `trace.correlationId`, and the same id travels on every hop of the request chain.
- Because the X-Ray header is lost on archive replay and in a DLQ, `trace.traceId` in the event is
  the durable link from an event to its trace.
