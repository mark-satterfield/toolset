---
name: appsync-graphql
description: >-
  GraphQL API design on AWS AppSync: schema design, operations and types, resolvers (JavaScript
  APPSYNC_JS unit and pipeline resolvers, Direct Lambda resolvers, batching), data sources,
  authorization modes and field-level directives, subscriptions and the real-time WebSocket
  protocol with enhanced filtering and invalidation, server-side caching, Merged APIs, Event APIs,
  and the service quotas a design must respect. Use when designing, specifying, reviewing or
  implementing a GraphQL API on AppSync.
user-invocable: false
doc_source: https://docs.aws.amazon.com/appsync/latest/devguide/
---

# GraphQL on AWS AppSync

This skill holds the decisions and checks for a GraphQL API on AppSync. Quotas and features
change: confirm a value that decides a design in the AppSync developer guide and the AppSync
endpoints and quotas page (`https://docs.aws.amazon.com/general/latest/gr/appsync.html`) through
the AWS MCP documentation tools, and cite the page.

## When GraphQL on AppSync fits

| Choose AppSync GraphQL when | Choose something else when |
|---|---|
| Clients need to select fields across several owned data sets in one round trip | One resource per request is enough: a REST API on API Gateway is simpler |
| Clients need real-time updates over WebSocket tied to mutations | Clients only need server push of opaque messages on channels: an AppSync Event API |
| Several teams contribute parts of one graph | One team owns one small API |

A GraphQL API does not remove ownership: each type and field is resolved by the building block
that owns its data. Never resolve another block's data by reading its store; call that block's
interface.

## Schema design

- **Design from client use, not from tables.** Name types for domain concepts; a type does not
  mirror a table's attributes or keys.
- **Operations.** Queries read, mutations change state and return the changed object (so a
  subscription can be attached to them), subscriptions only notify.
- **Inputs.** One input type per mutation (`CreateXInput`), non-null where the field is required.
  Use the AppSync scalars (`AWSDateTime`, `AWSEmail`, `AWSURL`, `AWSJSON`, `AWSPhone`,
  `AWSIPAddress`) instead of free strings where they apply.
- **Nullability.** A field is non-null only when it can always be resolved; a non-null field
  whose resolver fails nulls its parent.
- **Pagination.** Lists that can grow are connections: `items` and `nextToken`, with a `limit`
  argument and a maximum the resolver enforces.
- **Errors.** Expected business failures are part of the type (a union or a result type with an
  error field) when the client must act on them; unexpected failures surface as GraphQL errors
  through `util.error`.
- **Evolution.** Add fields and types; never change a field's type or remove a field a client
  uses. Retire a field with `@deprecated(reason: ...)` first. A breaking change is a new field or
  a new API.

## Resolvers and data sources

| Choice | Use when | Check |
|---|---|---|
| JavaScript unit resolver (`APPSYNC_JS`) | One data source call with light shaping | No network or file access, no async/await or promises; code size at most 32 KB |
| JavaScript pipeline resolver | Several steps in sequence (an authorization check, then a read) | At most 10 functions per pipeline; each function has one data source |
| Direct Lambda resolver | Business logic, calls to other services, anything APPSYNC_JS cannot do | Turn on batching for fields resolved per item (N+1); set the maximum batch size (up to 2,000) |
| DynamoDB data source | Simple reads and writes of the owning block's table | Only the owning block's table; `util.dynamodb` helpers for marshalling |
| HTTP data source | Calling an owned HTTP interface | Authorization of the call (IAM signing) |
| None (local) data source | Values computed in the resolver, pub/sub-only mutations, invalidation | No data access |

- Lint resolver code with `@aws-appsync/eslint-plugin`; AppSync rejects unsupported features at
  save time.
- Request execution time is at most 30 seconds and a resolver's evaluated response at most
  5 MB (not adjustable): long work goes behind an asynchronous operation.

## Authorization

AppSync has five authorization types: `API_KEY`, `AWS_LAMBDA`, `AWS_IAM`, `OPENID_CONNECT`,
`AMAZON_COGNITO_USER_POOLS`. One is the default; others are added as additional modes and
selected per type or field with `@aws_api_key`, `@aws_iam`, `@aws_oidc`,
`@aws_cognito_user_pools`, `@aws_lambda`.

- End users: Cognito user pools or OIDC; restrict operations by group with
  `@aws_cognito_user_pools(cognito_groups: [...])` and check ownership in the resolver.
- Backend callers (a Lambda function, another service): `AWS_IAM`.
- `API_KEY` only for development or data that is safe to expose publicly; keys expire.
- `API_KEY`, `AWS_LAMBDA` and `AWS_IAM` cannot be duplicated among the additional modes; several
  user pools or OIDC providers can.
- Field-level authorization is part of the schema design: decide it per field, not per API.

## Subscriptions and real time

- A subscription is attached to mutations with `@aws_subscribe(mutations: [...])`; a change made
  outside a mutation reaches subscribers only through a mutation (for example a backend mutation
  on a None data source, authorized by IAM).
- Filter on the server with enhanced filtering (filters set in the subscription resolver), not
  only with subscription arguments; authorize what a subscriber may receive in the resolver.
- Close connections from the server with subscription invalidation
  (`extensions.invalidateSubscriptions`) when access ends.
- Quotas: subscription payload at most 240 KB; subscriptions per client connection 200
  (adjustable). Outbound messages are metered in 5 KB units per client.
- Clients use the AppSync real-time WebSocket protocol (or the Amplify client); plan reconnection
  and resubscription.
- For channel-based pub/sub without a GraphQL schema, an AppSync Event API (channel namespaces,
  publish batches of up to 5 events) is the simpler choice.

## Caching

Server-side caching is None (default), full request caching, or per-resolver caching (pipeline
resolvers included), with a cache instance type, a TTL, optional custom cache keys, and
encryption in transit and at rest. Cache only data whose staleness up to the TTL is acceptable,
and never cache per-user data without the identity in the cache key.

## Several teams, one graph

Merged APIs combine the types, data sources, functions and resolvers of several source AppSync
APIs behind one endpoint; each source API is owned, deployed and changed by its own team. Use
them instead of one schema edited by several owners.

## Operations

- Turn on field-level logging at the level the TRD sets and X-Ray tracing.
- Alarm on 4XX and 5XX errors and on latency.
- Attach AWS WAF to a public API.
- A custom domain gives a stable endpoint across API replacement.

## Checks before a design is done

1. Every type and field has one owning building block, and its resolver reads only that block's
   data or calls that block's interface.
2. Every operation names its authorization mode, and every field with narrower access has its
   directive.
3. Every list is paginated with an enforced maximum.
4. No resolver needs more than 30 seconds or returns more than 5 MB; per-item Lambda resolution
   uses batching.
5. Every subscription states the mutation it follows, its server-side filter and when it is
   invalidated.
6. Caching, when used, states its TTL and cache keys, and excludes per-user data or keys on the
   identity.
7. The change is additive, or the breaking change is a new field or API.
