# Extraction schema — the typed decision packet

This file defines the exact shape of the packet `arc42-extract` emits. The packet is the sole
artifact downstream authors consume; its shape is a contract (see `trd-feed-contract.md`). Treat
the field names and types here as fixed — do not add, drop, or rename fields without versioning the
contract.

## Top-level structure

The packet is an object with three buckets, one per extracted arc42 section (§2, §4, §8). Every bucket is always
present, even when empty (an absent section is signaled inside the bucket, never by omitting it).

```json
{
  "schemaVersion": "1.0",
  "source": {
    "sad": "docs/architecture/",
    "layout": "one-file-per-section",
    "extractedFrom": ["02-constraints.md", "04-solution-strategy.md", "08-crosscutting.md"]
  },
  "constraints":          { "sourceSection": 2, "present": true,  "entries": [ /* Entry */ ] },
  "solutionStrategy":     { "sourceSection": 4, "present": true,  "entries": [ /* Entry */ ] },
  "crosscuttingConcepts": { "sourceSection": 8, "present": true,  "entries": [ /* Entry */ ] }
}
```

- `schemaVersion` — string. Bump on any breaking change to entry shape so downstream readers can fail loudly on mismatch.
- `source` — provenance for the whole packet: where the SAD lives, which layout was detected, and the concrete files read.
- Each bucket has `sourceSection` (the canonical arc42 number), `present` (boolean), `entries` (list), and `missingReason` (string, only when `present` is `false`).

## The Entry type

Every entry in every bucket has the **same four required fields**. This uniformity is what lets the
TRD and spec authors iterate the packet generically.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Stable, content-anchored, unique across the whole packet. Derivation rule below. |
| `sourceSection` | integer | yes | Canonical arc42 section number (`2`, `4`, `8`, or `9`). Redundant with the bucket but carried on the entry so a flattened list stays self-describing. |
| `statement` | string | yes | The extracted text. Verbatim or minimally normalized (whitespace collapse, leading list-marker stripping). Never paraphrased into new meaning. |
| `rationaleRef` | string \| null | yes (nullable) | A pointer to the rationale/justification span in the SAD. `null` when the SAD states none. Never fabricate rationale to fill it. |

### Worked entries

A constraint:

```json
{
  "id": "C-runtime-node20",
  "sourceSection": 2,
  "statement": "The service MUST run on Node.js 20 LTS; no native addons requiring a C toolchain.",
  "rationaleRef": "02-constraints.md / Technical Constraints / TC-3"
}
```

A solution-strategy statement:

```json
{
  "id": "S-event-driven-core",
  "sourceSection": 4,
  "statement": "Domain state changes are propagated as events over an internal bus; read models are projections.",
  "rationaleRef": "04-solution-strategy.md / Approach / paragraph 2"
}
```

A crosscutting concept:

```json
{
  "id": "X-authz-rbac",
  "sourceSection": 8,
  "statement": "Authorization is role-based; every endpoint declares a required role, enforced centrally in middleware.",
  "rationaleRef": null
}
```

A decision with supersession:

```json
{
  "id": "AD-payments-idempotency",
  "sourceSection": 4,
  "statement": "All payment writes MUST be idempotent, keyed on a client-supplied request id.",
  "rationaleRef": "04-solution-strategy.md / Idempotency / rationale"
}
```

## Stable-ID derivation rule

IDs MUST be **deterministic** and **content-anchored**, not positional. The same SAD content yields
the same ID on every re-run so downstream references survive section reordering and re-extraction.

1. **Prefix by bucket** — `C-` constraints, `S-` solution strategy, `X-` crosscutting concepts,
   `AD-` an entry whose SAD source is a §9 architecture-decision record surfaced into one of the
   three buckets as current state. An `AD-` entry carries `sourceSection: 9`; §9 is a source, never
   a fourth bucket (see `trd-feed-contract.md`, Guarantee 1).
2. **Slug from the strongest available anchor**, in priority order:
   - **the SAD's own identifier for the entry, slugified — and this is the normal case, not the
     exception.** `sad-maintainer` mints an explicit tag on every §2/§4/§8 entry it writes and
     preserves it across every rewording, precisely so the ID anchors here;
   - else a short kebab-case slug derived from the salient nouns of the `statement` (lowercase, ASCII, hyphen-separated, ~2–4 tokens).
3. **Disambiguate collisions** by appending a numeric suffix (`-2`, `-3`) in stable document order, only when two entries would otherwise produce the same slug.

The ID is an opaque-but-readable handle. Downstream authors cite it; they do not parse it for
meaning beyond the bucket prefix.

**Which branch of rule 2 an entry lands on decides whether its citations survive an edit**, and
that is why the tag matters. A TAGGED entry keeps its ID through any rewording: the tag is the
anchor, the words are not, and a TRD requirement, a spec or a Task bead citing it keeps resolving.
An UNTAGGED entry is anchored to the salient nouns of its statement, so rewording those nouns
re-IDs it and every citation to it stops resolving — with no error anywhere, which is the whole
danger. Changing a tag is therefore reserved for a genuinely different fact: a materially changed
statement is a new fact, it gets a new tag, and the contract's supersession mechanism (never ID
reuse) is how that change is tracked.

## Validation invariants

Before emitting, assert:

- Every entry has non-empty `id`, integer `sourceSection` in `{2,4,8,9}`, non-empty `statement`, and a `rationaleRef` key (value may be `null`). `9` is legal and names a §9 decision record surfaced into one of the three buckets; it is not a bucket of its own.
- `id` is unique across the **entire** packet, not just within a bucket.
- Each entry's `sourceSection` equals its bucket's `sourceSection`, except an `AD-` entry drawn from §9, whose `sourceSection` is `9` while it sits in the bucket its content belongs to.
- Every bucket is present; a `present: false` bucket has an empty `entries` list and a `missingReason`.
- No entry's `statement` contains content that cannot be located in the SAD source recorded in `source.extractedFrom`.
