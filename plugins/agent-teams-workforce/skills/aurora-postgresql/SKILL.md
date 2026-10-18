---
name: aurora-postgresql
description: >-
  SkillSpoke's one authority on PostgreSQL: Aurora PostgreSQL Serverless v2 reached through the
  RDS Data API. Use whenever you design, specify, review, implement, test or provision anything
  that stores data in PostgreSQL: relational schemas, the Python Data API access layer,
  migrations, pgvector similarity search, graph-shaped data and the choice between PostgreSQL
  and a graph database, database security, performance and operations. It states where
  SkillSpoke and AWS differ from generic PostgreSQL guidance, and it overrides that guidance,
  including the `design-postgres-tables`, `pgvector-semantic-search` and
  `database-schema-designer` skills, where they disagree.
user-invocable: false
---

# Aurora PostgreSQL in SkillSpoke

The source of every architecture decision is the effective arc42 architecture in the
`skillspoke-docs` vault, under `docs/tech/architecture/arc42/`. This skill points to it and
restates none of its decisions. Read the view that covers your task before you decide anything
this skill does not state.

| View | Holds |
|---|---|
| `08-crosscutting-concepts/persistence-per-data-set.md` | Which data set lives in PostgreSQL, its owning service, and the PostgreSQL topology (one cluster per owning service, Data API only, why Aurora) |
| `07-deployment-view/environments-and-accounts.md` | Capacity, availability, backups and deletion protection per environment |
| `07-deployment-view/network.md` | The `rds-data` interface endpoint and the security groups |
| `05-building-block-view/shared-components.md` | `PlatformPostgresCluster` in `shared-cdk-lib`; the Data API client, outbox writer and `OutboxRelay` in `skillSpoke-dataAccess-lib` |
| `08-crosscutting-concepts/powertools-and-chassis.md` | What the chassis and `skillSpoke-dataAccess-lib` give every PostgreSQL handler |
| `08-crosscutting-concepts/concurrency-control.md` | Contended writes and atomic unique creation |
| `08-crosscutting-concepts/migration-and-backfill.md` | How data migrations and backfills run |
| `08-crosscutting-concepts/service-isolation.md` | Store ownership; no service reads another service's database |

Generic guidance this skill builds on, read as reference and overridden here where it differs:
`design-postgres-tables` (table design) and `pgvector-semantic-search` (pgvector), both from
pg-aiguide; `database-schema-designer` (relational modelling). For a fact about PostgreSQL
itself, search the PostgreSQL manual for the engine's major version with the `pg-aiguide` MCP
server (`search_docs`). For an AWS fact, use the AWS documentation (`aws-mcp`
`aws___search_documentation`, `aws___read_documentation`); for ACU sizing and engine upgrade
planning, retrieve the `amazon-aurora-postgresql` AWS skill with `aws___retrieve_skill`, and
apply its numbers through CDK only.

## 1. Platform facts

- **Engine and shape.** Aurora PostgreSQL Serverless v2, one cluster per owning service in that
  service's own stack, built with `PlatformPostgresCluster` from `shared-cdk-lib`. A service
  never reads or writes another service's database; it calls that service's API or consumes its
  events.
- **Access.** Lambdas reach the cluster only through the RDS Data API (`rds-data`), over the
  `rds-data` interface endpoint. No connection pool, no RDS Proxy, no direct wire-protocol
  connection from application code. Generic pooling advice (pg-pool, PgBouncer, RDS Proxy) does
  not apply.
- **Scale to zero.** In `dev` the minimum capacity is 0 ACU with automatic pause; a paused
  writer resumes on the first Data API request, which takes less than 15 seconds. In `qa` and
  `prod` the minimum is 0.5 ACU with a reader in a second AZ. Every call that wakes a paused
  cluster bills ACUs until it pauses again.
- **Data API limits** (AWS documentation, `data-api.limitations.html`, `data-api-timeouts.html`,
  `BeginTransaction`): queries run on the writer only; a response larger than 1 MiB is
  terminated; a call that does not finish in 45 seconds is cancelled unless
  `continueAfterTimeout` is set; a transaction is rolled back after 3 minutes without a call
  that uses its id, and after 24 hours in any case; array parameters are not supported; the
  `schema` parameter is not supported; Aurora PostgreSQL 14 and later needs `scram-sha-256`
  passwords.
- **Engine versions and extensions.** Use the latest Aurora PostgreSQL major version that
  `PlatformPostgresCluster` supports. Before relying on an extension or an extension version,
  check the Aurora PostgreSQL extension table for that engine version
  (`AuroraPostgreSQLReleaseNotes/AuroraPostgreSQL.Extensions.html`). In use: `vector`
  (pgvector 0.8.x on current minors), `pg_trgm`, and PostGIS where a service needs it.
  `ltree` and `pgrouting` are available. **Not available on Aurora:** pgvectorscale,
  pg_textsearch, TimescaleDB, Apache AGE. Any guidance that depends on them does not apply.

## 2. The Data API access layer (Python)

The Data API client, its retry while a paused cluster resumes, the transactional outbox
writer and the `OutboxRelay` handler are in `skillSpoke-dataAccess-lib`. Use them; never write
a second client, retry loop or outbox. The rules below are what code built on that library
must do, and what the library itself must do.

- **Typed parameters, always.** Every value goes in `parameters` as a named `SqlParameter`
  (`:name` in the SQL), never by string formatting, f-strings or concatenation. Parameter
  binding is the injection defence. Identifiers (table, column, sort direction) are never
  taken from input; map an input to one of a fixed set of SQL fragments in code.
- **Type hints.** Send `DECIMAL`, `DATE`, `TIME`, `TIMESTAMP`, `UUID` and `JSON` values as
  strings with the matching `typeHint`. A `timestamptz` value is sent as a UTC `TIMESTAMP`
  string. A vector is sent as a string literal (`'[0.1,0.2,...]'`) and cast in SQL
  (`:q::halfvec(1024)`). Because array parameters are not supported, pass a list as a JSON
  string and expand it in SQL (`jsonb_array_elements_text(:ids::jsonb)`), or as a `{...}`
  literal cast to the array type.
- **Results.** Read rows with `formatRecordsAs="JSON"` and validate them into a Pydantic model
  or frozen dataclass at the boundary (`python-coding`); never pass raw records upward. Keep
  every response under 1 MiB: select only the columns needed, never select an embedding
  column unless the caller needs the vector, and page with a keyset cursor
  (`WHERE (sort_key, id) > (:after_key, :after_id) ORDER BY sort_key, id LIMIT :page_size`),
  never `OFFSET`.
- **Transactions.** A statement sent without `transactionId` commits on its own. Several
  statements that must commit together run in one transaction: `BeginTransaction`, every
  `ExecuteStatement` with that `transactionId`, then `CommitTransaction`, and
  `RollbackTransaction` on any failure. Keep a transaction short (well inside 3 minutes
  between calls). Session state (`SET`, temporary tables, prepared statements) does not
  survive between calls outside a transaction; use `SET LOCAL` inside the transaction that
  needs it.
- **Batches.** `BatchExecuteStatement` runs one statement for many parameter sets; inside a
  transaction it is all-or-nothing.
- **Publishing events.** A state change that announces an event writes its outbox row in the
  same transaction as the change, through the library's outbox writer
  (`skillspoke-events` skill, "Publish after commit").
- **Retries and timeouts.** Retry `DatabaseResumingException` (in the library) and the
  throttling and 5xx errors the AWS SDK's standard retry mode covers, with jittered
  exponential backoff and a capped attempt count; never retry a `DatabaseErrorException`
  caused by the SQL itself. Set the SDK read timeout above the 45-second Data API timeout
  (at least 60 seconds) and keep it inside the Lambda timeout, so a call never times out on
  the client while the database still commits (`aws-core:aws-sdk-python-usage`).
- **Idempotency.** A write that a retried invocation may repeat is idempotent in SQL:
  `INSERT ... ON CONFLICT (natural key) DO NOTHING` or `DO UPDATE ... WHERE` the stored version
  is older, guarded by a unique constraint. Handler-level idempotency is the chassis's
  (Powertools Idempotency); do not build a second one in the data layer.
- **Concurrency.** Contended updates use optimistic concurrency (a `version` column checked in
  the `WHERE` clause and the affected-row count checked) as `concurrency-control.md`
  describes.
- **Clients and configuration.** Create the `rds-data` client once at module level
  (`python-coding`, Design). The cluster ARN, the secret ARN and the database name come from
  SSM Parameter Store parameters the owning stack writes, read through the chassis; never
  hardcode them. Name every parameter and variable with the `resource-naming` skill.

## 3. Relational schema design

`design-postgres-tables` is the reference for types, constraints and indexes. SkillSpoke adds
or overrides:

- **Keys.** Use `bigint GENERATED ALWAYS AS IDENTITY` for keys that never leave the service.
  An identifier exposed outside the service (in an API, an event, another service's store or
  a log) is a `uuid`, generated with `uuidv7()` on PostgreSQL 18 and later and
  `gen_random_uuid()` before that, so no sequence is leaked and an id is unique across stores.
- **Types.** `timestamptz` for time, `numeric` for money, `text` with a `CHECK` for bounded
  strings, `jsonb` only for genuinely optional attributes, `NOT NULL` wherever the data
  requires it. Index every foreign key column yourself.
- **Normalize to 3NF**; denormalize only for a measured read problem.
- **Temporal facts.** Data whose history matters (the company and normalized datasets) is an
  effective-dated fact model: each fact row has `valid_from`/`valid_to` (a `tstzrange` with
  an exclusion constraint where overlaps must be impossible), a source and an observed time;
  current values are a view or a partial index on the open range, never an overwrite.
- **Audit and state transitions.** Every table has `created_at` and `updated_at`. A state
  machine records each transition in a history table written in the same transaction as the
  state change.
- **Fuzzy matching.** `pg_trgm` with a GIN (`gin_trgm_ops`) index for alias, name and
  duplicate matching; full-text search with a `tsvector` generated column, a GIN index, and an
  explicit text search configuration in both the column and the query.
- **Multi-tenancy.** Tables shared by many seekers carry the seeker's id, and every query
  filters on it. Where several tenants share a table and a missed filter would leak data,
  enable row-level security with the tenant id set by `SET LOCAL` inside the transaction.
- **Partitioning** only for tables expected to grow very large or to be pruned by range; at
  alpha scale most tables need none.

## 4. Migrations

- Schema changes are versioned SQL migration files in the owning service's repository, applied
  in order and recorded in a migrations table, and run at deploy time by the service's own
  stack (a CDK custom resource or a migration Lambda that calls the Data API). Never change a
  schema by hand or through an MCP server. Data migrations and backfills follow
  `migration-and-backfill.md`.
- Every migration is idempotent and restartable, and backward compatible with the code still
  running: expand (add a nullable column, a new table, a new index), deploy the code, backfill,
  then contract (add `NOT NULL`, drop the old column) in a later migration.
- `CREATE INDEX CONCURRENTLY` cannot run inside a transaction: send it as its own
  `ExecuteStatement` without `transactionId`, with `continueAfterTimeout` set, and make it
  restartable (`DROP INDEX IF EXISTS` an invalid index first). Long DDL also sets
  `continueAfterTimeout`; a DDL statement stopped midway can leave errors.
- A migration that must be atomic runs inside one Data API transaction (PostgreSQL DDL is
  transactional).
- Adding a column with a volatile default rewrites the table; add it nullable, backfill in
  batches, then set the default and the constraint.
- Extensions are created by a migration (`CREATE EXTENSION IF NOT EXISTS vector`), never
  assumed.

## 5. Vector search (pgvector 0.8.x)

`pgvector-semantic-search` is the reference. SkillSpoke adds or overrides:

- **Type and dimension.** Store embeddings as `halfvec(N)`, with `N` the exact output
  dimension of the embedding model in use; `halfvec` indexes up to 4,000 dimensions and
  `vector` up to 2,000. Record the model id and version with every embedding (a column, or one
  table per model), so a model change re-embeds and never mixes vectors from two models.
- **Index.** HNSW with `halfvec_cosine_ops` and the `<=>` operator by default (`m = 16`,
  `ef_construction = 64`); IVFFlat only for the write-heavy cases the reference names.
- **Query-time settings through the Data API.** `SET hnsw.ef_search`, `hnsw.iterative_scan`
  and `hnsw.max_scan_tuples` do not persist between Data API calls. Set them with `SET LOCAL`
  inside the same transaction as the query, or as a role or database default
  (`ALTER ROLE ... SET hnsw.ef_search = 100`) in a migration.
- **Filtered search.** Use iterative scans (`SET LOCAL hnsw.iterative_scan = relaxed_order`)
  for selective filters, a B-tree prefilter for very selective ones, and partial HNSW indexes
  for a few filter values. The reference's pgvectorscale and hypertable options do not exist
  on Aurora.
- **Bulk load.** `COPY` is not available through the Data API. Load with
  `BatchExecuteStatement` in batches that keep each request under the limits, and build the
  HNSW index after the initial load.
- **Hybrid search.** BM25 through pg_textsearch is not available on Aurora. Hybrid search is
  pgvector plus PostgreSQL full-text search (`tsvector`, `ts_rank_cd`) or `pg_trgm`, the two
  ranked lists fused with reciprocal rank fusion, in SQL or in the application.
- **Recall.** Measure recall against an exact search (`SET LOCAL enable_indexscan = off`) on a
  sample before tuning, and again after a model or index change.

## 6. Graph-shaped data: PostgreSQL or a graph database

The architecture agents choose the store for each graph-shaped data set, as they choose every
store. Neither PostgreSQL nor a graph database is the default; apply this rule, state the
reasons in the decision, and record it as the architecture records any store decision.

**PostgreSQL fits** when the graph serves the owning service's own queries and:

- the relationships are a hierarchy or a shallow network: a taxonomy (`ltree`), a parent and
  child tree, or adjacency of one to a few hops;
- traversals have a known, small maximum depth and run as `WITH RECURSIVE` queries over a node
  table and an edge table (indexes on `(source_id, edge_type)` and `(target_id, edge_type)`,
  the `CYCLE` clause, and an explicit depth limit);
- path finding on a weighted edge table is occasional (`pgrouting`);
- the graph must join transactionally with relational facts and pgvector similarity in the
  same service, in one Data API transaction.

**A graph database fits** when any of these is a requirement:

- deep or variable-length traversals (many hops, unknown depth) on a request path, where
  recursive SQL grows with every hop;
- graph algorithms over the whole graph or large parts of it: centrality, community
  detection, similarity by shared neighbourhood, shortest paths at scale;
- GraphRAG: retrieval that combines graph traversal with vector similarity, for example
  following the entities and relationships extracted from a seeker's imported documents
  (resumes, CVs and other documents) and ranking them by embedding similarity;
- a graph query language (openCypher, Gremlin, SPARQL) is the natural expression of the
  queries, or the graph is shared by several consumers through the owning service's API.

**Facts to weigh, not verdicts:**

- PostgreSQL adds no store and no cost: the graph lives in the cluster the service already has,
  which scales to zero in `dev`.
- Amazon Neptune is the AWS graph database; Neptune Analytics adds graph algorithms and vector
  search. Neptune has a monthly floor and does not scale to zero, provisioned or serverless.
  Confirm current prices with the AWS pricing tools before stating a figure.
- Both can hold the same data set: an architecture can keep the system of record in PostgreSQL
  and project the graph into a graph database for the traversals and algorithms that need it,
  through the owning service's events.
- Apache AGE (openCypher inside PostgreSQL) is not available on Aurora or RDS.

## 7. Security

- **Roles.** Each service has its own database and roles; the application role the Lambdas
  use has only `CONNECT`, `USAGE` on its schemas and the DML it needs, never `rds_superuser`,
  ownership of the schema, or `BYPASSRLS`. Migrations run as a separate role that owns the
  schema. A read-only role (`SELECT` only, `default_transaction_read_only = on`) serves
  inspection tools. The master user is for bootstrap only.
- **Secrets.** Each role's credentials are a Secrets Manager secret with rotation, created in
  the owning stack; code and agents never read a secret's value, only pass its ARN to the Data
  API.
- **IAM.** A Lambda's role gets `rds-data:ExecuteStatement`, `BatchExecuteStatement`,
  `BeginTransaction`, `CommitTransaction` and `RollbackTransaction` on its own cluster ARN only
  (CDK `grantDataApiAccess`), and `secretsmanager:GetSecretValue` on its own role's secret
  only.
- **Encryption and exposure.** Storage encrypted with a customer managed KMS key, TLS for every
  connection (the Data API is HTTPS), no public access, no publicly reachable endpoint.
- **Injection.** Parameter binding (section 2) is the defence; a test that probes for injection
  sends hostile values through every parameter and every identifier-mapping input.

## 8. Performance and operations

- Read plans with `EXPLAIN (ANALYZE, BUFFERS)` on realistic data before adding an index; find
  costly statements with `pg_stat_statements`.
- Autovacuum stays on; watch dead tuples and bloat on update-heavy tables, and separate hot
  columns into their own table when updates churn wide rows.
- Watch `ServerlessDatabaseCapacity`, `ACUUtilization` and resume events in CloudWatch, and
  Performance Insights where it is enabled. A workload that keeps a `dev` cluster awake costs
  ACU hours; schedule-driven jobs should not poll a paused cluster.
- Capacity ranges, backups and deletion protection per environment are the architecture's
  (`environments-and-accounts.md`); they change only through `PlatformPostgresCluster`
  settings in CDK, never by a direct AWS call.

## 9. Testing

- **Unit tests** mock the `rds-data` client (or the library's client interface) and assert
  the SQL text, the parameters and their type hints, the transaction calls, and the handling
  of `DatabaseResumingException` and `DatabaseErrorException`.
- **SQL tests** run the migrations and the queries against a local PostgreSQL with the same
  major version and extensions (for example the `pgvector/pgvector` container image), through
  an adapter that sends the same SQL and parameters the Data API would.
- **Integration tests** run against the service's `dev` cluster through the Data API, with data
  the test creates and removes itself; expect the first call to wake a paused cluster.

## Inspecting a live database

The read-only `awslabs-postgres-mcp-server` (when it is configured for the session) runs
`SELECT`, `EXPLAIN` and schema queries against a `dev` cluster through the Data API, as a
read-only database role. Use it to inspect an existing schema or a query plan. It never
changes a schema or data, and never creates a cluster; those happen only through migrations
and CDK. When its tools are not available or it cannot connect, say so and work from the
service's migration files.
