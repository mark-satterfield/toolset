---
name: data-architecture
description: The method of data architecture independent of any database engine - conceptual and logical data models, entities, relationships and identifiers, which domain owns each entity and its system of record, data flows and lineage, reference and master data, data classification and retention classes, operational versus analytical data, and data contracts between domains - with the checks to apply to each. Use when deciding what data a system holds and who owns it, before any store or engine is chosen, or when deciding how data is owned, classified and kept across stores.
user-invocable: false
---

# Data architecture

Data architecture decides what data exists, what it means, who owns it, how it moves and how
long it is kept. It comes before the choice of store and before engine-level design: a logical
model names entities, attributes and relationships, never tables, keys, indexes or partitions.
Each section below gives the decision, the method and the checks. A design fact belongs in the
architecture only when it is a decision; a check that fails is a finding to fix in the design.

## 1. Conceptual and logical data models

**Decision.** The entities the requirements name, what each one means, its identity, its
attributes and its relationships with their cardinality and optionality.

**Method.**

1. Take the nouns of the requirements that the system must remember beyond one request. Each is
   a candidate entity; a noun that only describes another entity is an attribute; a noun that
   links two entities and carries its own facts (a date, a status, a role) is an associative
   entity.
2. Write one sentence of meaning per entity in the domain's own words (the ubiquitous language
   of its bounded context). Two entities with the same name and different meanings in two
   contexts are two entities; name them per context.
3. Give each entity its identity: a natural key only when the domain guarantees it is unique
   and never changes (otherwise a surrogate identifier), and state who issues it.
4. Draw each relationship with its cardinality (one to one, one to many, many to many) and its
   optionality, and state whether the child can exist without the parent (composition) or not.
5. Normalise the logical model to third normal form, so each fact is stated once. Denormalising
   is a physical decision for the engine designer and is not made here.
6. Mark each attribute's type at the logical level (text, number, money with currency,
   timestamp with time zone, enumeration with its values, identifier of another entity) and
   whether it is required.

**Checks.**

- Every entity has one sentence of meaning, one identity and one owning domain (section 2).
- No attribute holds a list or a structure that has its own identity; that is an entity.
- No relationship is many to many without an associative entity when the link carries facts.
- Derived values (totals, counts, statuses computed from other facts) are marked derived, with
  the rule that derives them; they are not a second source of the same fact.
- Time is explicit: an attribute whose value changes and whose history matters is modelled as a
  history (effective-from and effective-to, or an append-only event), not overwritten.
- Money carries its currency; a quantity carries its unit; a timestamp carries its time zone.

## 2. Ownership and the system of record

**Decision.** For each entity, the one domain that owns it, the one system of record that holds
its authoritative copy, and every copy elsewhere with how it is kept current.

**Method.**

1. The owner is the domain whose rules create and change the entity. Other domains may hold
   copies (read models, caches, projections, analytics), never a second writable original.
2. Each entity has exactly one system of record. A copy states its source, the mechanism that
   keeps it current (the owner's events, a change data capture stream, a scheduled export) and
   its allowed staleness.
3. Other domains reach the entity through the owner's interface: its API or its events. No
   domain reads or writes another domain's store directly.
4. When two domains both seem to create the same entity, split it: each owns the part its rules
   change, under its own name, and one refers to the other by identifier.

**Checks.**

- Every entity has one owner and one system of record; no entity has two writers.
- Every copy names its source, its update mechanism and its staleness bound.
- No cross-domain foreign key: a reference to another domain's entity is an identifier only,
  with no store-level constraint across domains, and the design says what happens when the
  referenced entity is deleted.

## 3. Data flows and lineage

**Decision.** How data moves between domains and stores: what each flow carries, from which
producer to which consumer, how often, and what each consumer derives from it.

**Method.**

1. List each flow with its producer, consumers, trigger (event, request, schedule), payload
   entities and delivery guarantee (at least once, at most once).
2. For each derived data set, record its lineage: the sources it is computed from and the
   transformation, so a wrong value can be traced and a source change can be assessed.
3. Prefer the owner publishing facts (events) to consumers pulling the owner's store; a
   consumer that needs the data at query time calls the owner's API.

**Checks.**

- Every consumer of at-least-once delivery handles duplicates (an idempotency key or a natural
  idempotent write).
- Every derived data set can be rebuilt from its sources, and the design says how.
- No flow carries data of a higher classification (section 5) to a consumer not allowed to hold it.

## 4. Reference and master data

**Decision.** Which data is reference data (code lists and enumerations shared across domains:
countries, currencies, statuses) and which is master data (core shared entities such as a
person or an organisation), and who owns each.

**Method.** Give each reference list one owner and one versioned source; consumers take a copy
and refresh it. For master data, choose the owning domain and the identifier every other domain
uses for the same real-world thing; record how duplicates are matched and merged.

**Checks.** No domain keeps its own diverging copy of a reference list; every master entity has
one identifier used across domains; a merge of two records says what happens to references to
the record that disappears.

## 5. Classification and retention classes

**Decision.** For each entity and attribute, its sensitivity class and its retention class.

**Method.**

1. Classify each attribute against the workload's data classification scheme (for example
   public, internal, confidential, restricted; personal data and special-category personal
   data marked as such). The entity takes the highest class of its attributes unless the
   sensitive attributes are separated.
2. State the handling each class requires: who may access it and for what purpose, where it may
   be stored, encryption, logging of access, masking in logs and non-production copies, and
   destruction (AWS Well-Architected, SEC07-BP01 "Understand your data classification scheme";
   SEC07 data classification best practices).
3. Give each data set a retention class from the requirement that sets it (a legal or
   contractual period, the user's right to erasure, an operational need): how long it is kept,
   what happens at the end (deletion, anonymisation, archive) and what triggers it (age, account
   closure, a request).
4. Minimise: an attribute with no requirement that needs it is not collected.

**Checks.**

- Every attribute that identifies a person is classified as personal data, and the design says
  how a deletion request reaches every copy, backup policy and derived data set holding it.
- Every data set has a retention class with an end-of-life action; "forever" is stated with its
  reason.
- Sensitive attributes never appear in logs, metrics dimensions, event payloads to consumers not
  allowed them, or identifiers that are visible to others (for example a key that embeds an email).

## 6. Operational versus analytical data

**Decision.** Which data serves transactions (operational: current state, small reads and writes,
strict consistency) and which serves analysis (analytical: history, large scans, aggregates), and
how analytical data is derived.

**Method.** Keep the operational model in the owning domain. Derive analytical data from the
owner's events or change data capture into a separate analytical model (facts and dimensions,
or wide denormalised tables), with its own retention and classification. Never run analytical
scans against an operational store on the request path.

**Checks.** Every analytical data set states its source flows, freshness and grain (what one row
means); personal data in analytical data is minimised, pseudonymised or aggregated as its class
requires.

## 7. Data contracts between domains

**Decision.** For each flow or interface that carries data across a domain boundary, the
contract: the entities and attributes it carries, their meaning, types and classification, the
owner, the version and the compatibility rule.

**Method.** The producer owns the contract. Changes are backward compatible (add optional
attributes; never remove, rename or change the meaning or type of one) within a version; a
breaking change is a new version that runs beside the old one until consumers move.

**Checks.** Every cross-domain flow has a contract with an owner and a version; every attribute
in it has a meaning and a classification; no consumer depends on an attribute the contract does
not state.

## Where the decisions belong

- The conceptual model, ownership, systems of record, flows, classification scheme and
  retention classes are architecture: arc42 sections 5 (building blocks), 6 (runtime flows) and
  8 (cross-cutting concepts).
- Retention periods, staleness bounds and freshness are requirements with values: the TRD.
- The logical model of one domain (entities, attributes, relationships) is the detailed design of
  the component or feature that owns it.

## Sources

AWS documentation through the AWS MCP documentation tools: the AWS Well-Architected Framework
security pillar (data classification, SEC07; data protection at rest and in transit, SEC08 and
SEC09) and reliability pillar (data backup, REL09). For a value or a service behaviour, search
the documentation; never state one from memory.
