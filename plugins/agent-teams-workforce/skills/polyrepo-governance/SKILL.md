---
name: polyrepo-governance
description: >-
  Create, update, deprecate, list, or search the registry of the PROJECT'S OWN scripts,
  tools, procedures, and knowledge-base locations — the executable and procedural resources
  the project provides for working with its repositories. This is where local procedures the
  steward writes (for example, a clone script) get registered so the other skills can find
  and run them. First token may be a CUDLS verb (create | update | delete | deprecate | list
  | search); if absent, infer.
---

# Polyrepo Governance

You own the registry of the project's *own* operational resources — the scripts, tools,
procedures, and knowledge-base locations it provides for working with its repos. This is
distinct from **polyrepo-info**: governance is curated, executable/procedural project
resources; the knowledge store is discovered facts. It is also distinct from the manifest's
structural repo data (**polyrepo-repo**).

## What you record

The manifest's `governance` section. Entry shape:

```yaml
governance:
  - id: <slug>
    type: script | tool | procedure | knowledge-base
    name: <name>
    location: <path or URL>
    invoke: <how to run or use it — for scripts/tools>
    notes: <optional>
# No date field — git history is the audit trail for when an entry changed.
```

## Local procedures (the steward's proactive builds)

When the steward writes a new **local procedure** — project-side, not pushed back into the
plugin — the script lives under `.polyrepo/procedures/<name>` and is registered here. That is
how a capability the steward invents (e.g., "clone a repo") becomes something **polyrepo-repo**
and others can discover and run. Registering it is a governance `create`.

## Operations (CUDLS)

- **create** — register a script/tool/procedure/knowledge-base location.
- **update** — revise an entry (path moved, invocation changed).
- **delete / deprecate** — retire a resource; keep the record with a reason (don't drop it).
- **list** — enumerate registered resources by type.
- **search** — find the resource that does a thing ("is there a way to clone a repo?").

## Recording

Changes follow the learning protocol (`../polyrepo-repo/references/learning-protocol.md`):
update the `governance` section **and** append `.polyrepo/changelog.md`.

## Boundaries

Governance is edited only through this flow. Retired tooling is deprecated, not deleted — keep
the record and the reason.
