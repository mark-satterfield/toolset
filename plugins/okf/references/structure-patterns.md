# OKF structure patterns

How to organize a bundle's directory tree, generate indexes, and
cross-link concepts. The spec ([spec-v01.md](spec-v01.md)) is
deliberately silent on domain structure — this file collects proven
patterns. None are mandatory.

## Organizing the tree

The directory structure is **independent of the domain**. Group concepts
into subdirectories by kind or by subject area — whatever aids
navigation. Common top-level groupings:

```
bundle/
├── index.md              # root listing (may declare okf_version)
├── log.md                # optional change history
├── datasets/             # logical groupings of tables
├── tables/               # one concept per table
├── references/           # mirrored external material as first-class concepts
├── metrics/              # abstract concepts, no `resource`
├── joins/                # documented relationships between tables
└── playbooks/            # operational procedures
```

Guidance:

- **One concept per file.** Do not pack multiple tables/metrics into one
  document.
- **Directory = grouping, not concept.** A directory is described by its
  `index.md`, not by a same-named concept file.
- **Keep depth shallow** where you can — two or three levels is usually
  enough. Deep trees hurt progressive disclosure.
- **`references/` is special by convention** — it holds external
  material (docs, license text, taxonomy tables) mirrored as OKF
  concepts so citations can point into the bundle instead of at fragile
  external URLs.

## Progressive disclosure via `index.md`

An `index.md` lets a reader (human or agent) see what's available before
opening files. Place one in any directory. **No frontmatter** (except the
root `okf_version` exception). Group entries under headings; each entry
is a bullet with the linked concept's `description`:

```markdown
# Tables

* [Orders](orders.md) - One row per completed customer order.
* [Customers](customers.md) - One row per registered customer.

# Subgroups

* [References](references/) - External docs mirrored as concepts.
```

- Link to **subdirectories** with a trailing slash: `[References](references/)`.
- Pull the description text from each child's frontmatter.
- `scripts/gen-index.sh` generates a conformant `index.md` for a
  directory automatically from child frontmatter.

## Cross-linking

Express relationships with standard markdown links woven into prose —
**not** a standalone "Links" section.

- **Absolute (bundle-relative), preferred:** `[customers](/tables/customers.md)`
  — stable when files move within a subdirectory.
- **Relative:** `[churn](./churn.md)` — fine for close neighbors.

The *kind* of relationship (joins-with, depends-on, parent/child) is
carried by the surrounding sentence, not the link syntax. Broken links
are explicitly allowed — they represent not-yet-written knowledge.

Good relationships to surface as links:

- Foreign keys between tables → link the FK column to its target table.
- A metric's inputs → link to the tables/metrics it derives from.
- A join concept → link both sides.
- A playbook's triggers → link the asset that raises the alert.
- Shared tags → candidates for a link if the relationship is real.

## Log files

Record history in a `log.md` at the relevant scope, newest first, ISO
8601 date headings:

```markdown
# Update Log

## 2026-07-04
* **Creation**: Added `orders`, `customers`, and the `sales` dataset.
* **Initialization**: Established directory structure and root index.
```

The leading bold word (`**Creation**`, `**Update**`, `**Deprecation**`)
is convention, not a requirement.

## A minimal, well-formed bundle

```
saas-metrics/
├── index.md          # okf_version: "0.1"; links to metrics/
├── log.md
└── metrics/
    ├── index.md
    ├── mrr.md        # type: Metric
    ├── churn.md      # type: Metric, links MRR as denominator
    └── nps.md        # type: Metric
```
