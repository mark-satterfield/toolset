# OKF frontmatter fields

Quick reference for the YAML frontmatter block at the top of every
concept document. Full rules in [spec-v01.md](spec-v01.md) §4.1.

## Fields

| Field | Required? | Description |
|-------|-----------|-------------|
| `type` | **YES** | Kind of concept — free-form string. E.g. `BigQuery Table`, `Metric`, `Playbook`, `API Endpoint`, `Reference`, `Dataset`. Consumers route/filter/present on this. |
| `title` | Recommended | Human-readable display name. If omitted, consumers may derive it from the filename. |
| `description` | Recommended | One-sentence summary. Used by `index.md` generators, search snippets, previews. |
| `resource` | Recommended | Canonical URI for the underlying asset. Omit for abstract concepts (metrics, playbooks, processes). |
| `tags` | Optional | YAML list of short strings for cross-cutting categorization. |
| `timestamp` | Optional | ISO 8601 datetime of last meaningful change (e.g. `2026-07-04T12:00:00Z`). |
| *(any key)* | Optional | Producer-defined extensions are allowed. **Never delete unknown keys** — preserve them on round-trip. |

## Rules that matter

1. **`type` is the only hard requirement.** A missing or empty `type` is
   the single most common conformance failure (error `E2`).
2. **Type values are free-form and never centrally registered.** Pick
   descriptive, self-explanatory strings. Do not reject a bundle for
   having an unfamiliar type.
3. **Be minimal.** Emit `type` plus the recommended fields that are
   actually warranted. Do not pad with empty `resource:` /
   `tags: []` / placeholder values.
4. **Never invent data.** If you don't know the correct `type`, ask. No
   fabricated URIs, timestamps, or tags.

## Conventional `type` values by domain

These are common, not canonical — invent domain-appropriate values freely.

| Domain | Typical types |
|--------|---------------|
| Data warehouse | `BigQuery Dataset`, `BigQuery Table`, `View`, `Column`, `Metric`, `Join` |
| APIs / services | `API Endpoint`, `Service`, `Event`, `Schema`, `Webhook` |
| Operations | `Playbook`, `Runbook`, `Incident`, `SLO`, `Alert` |
| Business | `Metric`, `KPI`, `Process`, `Policy`, `Glossary Term` |
| External material | `Reference` (mirrored external doc under `references/`) |

## The `okf_version` exception

The **only** place frontmatter is permitted in an `index.md` is the
**bundle-root** `index.md`, which MAY declare the targeted spec version:

```markdown
---
okf_version: "0.1"
---

# My Knowledge Bundle
...
```

No other `index.md` (and no `log.md`) may carry frontmatter.
