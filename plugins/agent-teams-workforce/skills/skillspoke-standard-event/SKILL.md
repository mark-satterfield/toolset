---
name: skillspoke-standard-event
description: >-
  The one SkillSpoke standard event and how an event is published: the schema registered as
  skillspoke@standard-event in the EventBridge schema registry skillspoke-events, the
  shared-events-service API every service calls to publish, the values a caller passes and the
  values shared-events-service fills in, the event type naming convention, and optional payload
  schemas. Use whenever you design, specify, review, implement or consume a SkillSpoke event.
user-invocable: false
expertiseFor:
  resourceTypes: [event, event-bus, event-rule]
  terms: ["domain event", "event-driven", "publishes an event"]
---

# SkillSpoke standard event

## The standard event

SkillSpoke has one event. Every SkillSpoke event is an instance of it.

- **Source of truth:** the EventBridge schema registry entry
  `arn:aws:schemas:us-east-1:616930583457:schema/skillspoke-events/skillspoke@standard-event`
  (registry `skillspoke-events`, schema `skillspoke@standard-event`, region `us-east-1`).
- **Shape:** an OpenAPI 3.0.0 document titled `SkillSpokeEventEnvelope`. Its `AWSEvent` schema is
  the EventBridge event; `AWSEvent.detail` is a `SkillSpokeEvent`.
- **Reference copy:** [`standard-event.schema.json`](standard-event.schema.json), beside this file,
  is registry schema version 3. Read field names, required fields, types and enum values from it.
- **Current registry content:** AWS `schemas` `DescribeSchema` with `RegistryName`
  `skillspoke-events` and `SchemaName` `skillspoke@standard-event` in `us-east-1`, called through
  the AWS MCP Server `run_script` tool. The registry content governs when it differs from the
  reference copy.

`SkillSpokeEvent` fields:

| Field | Required | Content |
|---|---|---|
| `eventId` | yes | Unique identifier of this event instance |
| `eventType` | yes | The event type name (see Event type names) |
| `eventSchemaVersion` | yes | Semantic version (`MAJOR.MINOR.PATCH`) of the event's payload schema |
| `category` | yes | Purpose of the event |
| `domain` | yes | Domain the event belongs to |
| `source` | yes | `service`, `region`, `environment` required; `subsystem` optional |
| `timestamps` | yes | `occurredAt`, `publishedAt` required; `expiresAt` optional |
| `trace` | yes | `correlationId` required; `causationId`, `parentEventId`, `rootEventId`, `traceId`, `spanId` optional |
| `lifecycle` | yes | `phase`, `outcome`, `severity`, `isError` required; `statusCode`, `statusSummary`, `statusReason`, `retry`, `details` optional |
| `payload` | no | Present when the event has a payload: `mode`, `schemaUri`, `contentType` required; `sizeBytes`, `inline`, `reference` optional |
| `actor` | no | `actorType`, `actorId`, `actorDisplay` |
| `identifiers` | no | `tenantId`, `userId`, `executionId`, `resourceType`, `resourceId`, `parentResourceId` |
| `businessContext` | no | `process`, `step`, `subStep` |
| `visibility` | no | `classification`, `piiPresent` |
| `tags` | no | Array of strings |

## Publishing path

`shared-events-service` builds every SkillSpoke event. Its API builds the event to the standard
schema, validates it and puts it on the event bus.

Every other service publishes an event by calling the `shared-events-service` API with the
event's values and, when the event has one, its payload. A service calls the API once per event,
and many times in one execution when it has many events to publish.

A design, specification or implementation of an event therefore consists of: the event type
name, the values the publishing service passes to the API, whether the event has a payload, the
payload schema when it has one, the publishers, the consumers, and the delivery and failure
semantics.

This skill governs the event and its publishing path. Report to whoever delegated the task,
citing the source and this skill: any architecture view, specification or test that shows another
service building the event or putting it on the event bus, and any difference between the
standard event and what the `shared-events-service` code accepts.

**When event design work exists.** A change needs event design when it introduces an event type
or an event payload. A service that publishes an existing event type by calling the
`shared-events-service` API is implementation work for that service.

## The events API as a caller uses it

Source: the `shared-events-service` repository
(`$SKILLSPOKE_APPS/shared/services/shared-events-service`). Read these files before you specify
or implement a call:

| File | Holds |
|---|---|
| `src/event/request_schema.json` | The request body schema |
| `src/event/events_publisher.py` | The handler: request validation, event assembly, validation against the standard schema, publication, responses |
| `cdk/stacks/shared_events_service.py` | The REST API, the route and its authorizer |

**Endpoint.** `POST /events` on the API Gateway REST API `shared-events`, authorized by a
Cognito user-pool authorizer. One request publishes one event.

**Request body.** A JSON object. The caller passes:

| Value | Required | Notes |
|---|---|---|
| `eventType` | yes | Matches `^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*){2,3}$` |
| `eventSchemaVersion` | yes | Matches `^[0-9]+\.[0-9]+\.[0-9]+$` |
| `category` | yes | String |
| `domain` | yes | Matches `^[a-z][a-z0-9-]*$` |
| `source.service` | yes | The calling service; a request without it returns 422 |
| `source.subsystem` | no | Component within the calling service |
| `timestamps.occurredAt` | yes | Date-time |
| `timestamps.expiresAt` | no | Date-time |
| `trace.correlationId` | yes | Non-empty string |
| `trace.causationId`, `trace.parentEventId`, `trace.rootEventId`, `trace.traceId`, `trace.spanId` | no | Strings |
| `lifecycle.phase` | yes | `started`, `in-progress`, `finished`, `finalized` |
| `lifecycle.outcome` | yes | `success`, `successWithWarning`, `failed`, `canceled`, `timeout` |
| `lifecycle.severity` | yes | `info`, `warning`, `error`, `critical` |
| `lifecycle.isError` | yes | Boolean |
| `lifecycle.statusCode`, `lifecycle.statusSummary`, `lifecycle.statusReason`, `lifecycle.retry`, `lifecycle.details` | no | As the standard schema defines them |
| `payload` | no | Passed when the event has a payload |
| `payload.mode` | with a payload | `inline` or `reference` |
| `payload.schemaUri` | with a payload | String |
| `payload.contentType` | with a payload | String (MIME type) |
| `payload.inline` | no | The payload content, when `mode` is `inline` |
| `payload.reference` | no | `storageType`, `location`, `checksum`, `encrypted`, when `mode` is `reference` |
| `payload.sizeBytes` | no | Integer |
| `actor`, `identifiers`, `businessContext`, `visibility`, `tags` | no | As the standard schema defines them |

**Values `shared-events-service` fills in.** `eventId` (a ULID), `timestamps.publishedAt`,
`source.region` and `source.environment`. It publishes the event with the EventBridge
`detail-type` set to the `eventType`.

**Responses.**

| Status | Body | When |
|---|---|---|
| 202 | `{"event_id", "status": "published", "bus"}` | The event is on the event bus |
| 422 | `{"error", "details"}` | The body is not valid JSON, fails `request_schema.json`, or has no `source.service` |
| 500 | `{"error": "Publish failed", "message"}` | EventBridge `PutEvents` failed |

## Event type names

The convention is the arc42 view
`docs/tech/architecture/arc42/08-crosscutting-concepts/event-naming-standard.md` in the
`skillspoke-docs` vault. Read it before naming an event type.

- Form: `[domain].[entity].[verb]` or `[domain].[subdomain].[entity].[verb]`.
- Entirely lowercase, kebab-case inside a segment, dots as the only separator.
- The last segment is one past-tense, semantically precise verb (`registered`, `finalized`,
  `locked-out`); a noun belongs in the entity segment.
- Lifecycle trace events use the verbs `started` and `ended`, in matched pairs; the outcome is
  carried in `lifecycle.outcome`.
- A name states a fact about a business or technical capability. It contains no service, stack,
  technology, delivery-channel or version identifier.
- Schema evolution is carried in `eventSchemaVersion`.
- A published event type keeps its name and its meaning; a changed meaning is a new event type.
- Each event type has exactly one owning publisher.
- Pattern: `^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*){2,3}$`.

Examples from the view: `identity.user.registered`, `billing.invoice.finalized`,
`job-search.results.published`.

## Payloads

A payload is the domain-specific content of one event type. A payload is optional, and many
events have none.

- An event with a payload carries it in `payload.inline` (`payload.mode` `inline`) or points to
  it with `payload.reference` (`payload.mode` `reference`).
- An event with no payload carries no `payload` object.
- A `payload` object, when present, carries `mode`, `schemaUri` and `contentType`.

**Payload schema.** An event type with a payload may have a payload schema: a schema of the
content carried in `payload.inline`. A payload schema is the one schema authored for an event.

- Author it as a JSON Schema Draft 4 or OpenAPI 3 document, the two schema types the EventBridge
  schema registry accepts, so that it can be registered.
- Its version is the event's `eventSchemaVersion`.
- It may be registered in the EventBridge schema registry `skillspoke-events`. Registration is
  optional.
- `payload.schemaUri` is the URI of the schema that describes the payload content: it refers to
  the event type's payload schema.
