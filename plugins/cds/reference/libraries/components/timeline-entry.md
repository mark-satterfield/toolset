---
kind: component
name: timeline-entry
page_family: app
aliases: [activity entry, event row, history entry, audit entry, log entry]
status: stable
slots:
  - { name: marker, required: true, accepts: [icon-glyph] }
  - { name: summary, required: true, accepts: [text] }
  - { name: actor, required: false, accepts: [text] }
  - { name: timestamp, required: true, accepts: [text] }
  - { name: detail, required: false, accepts: [text] }
sizing:
  marker: "--icon-size-inline on the --icon-viewbox-sm drawing grid, centred on the connector"
  marker-column: "--icon-size-marginalia, so every entry's content starts at one inline offset"
  stack-gap: "--sp-0-25 between the summary and its detail"
behavior:
  - "static; an entry records something that happened and is not editable"
accessibility:
  - "the timestamp is a <time datetime> element, so a relative phrase still carries its absolute moment"
  - "the marker is decorative — the summary says what happened"
  - "the entry is one list item, so summary, actor, and time are announced together"
token_bindings: [--border-subtle, --text-primary, --text-secondary, --text-tertiary, --icon-size-inline, --icon-size-marginalia, --sp-0-25]
composite: false
---

# Timeline entry

One thing that happened, on a record: what it was, who did it, and when. The unit of an activity log, a state history, or an audit trail.

## What, who, when — in that order

The summary leads because it is what the reader is scanning for. The actor and the timestamp follow as the qualifying facts. An entry that opens with its timestamp makes the reader parse a date before learning whether the entry is relevant.

An entry with no human actor says so — a system-initiated change names the system rather than leaving the actor blank, because a blank reads as unknown rather than as automatic.

## Variants

- `detail`: `absent` (default) | `present` — the from-and-to of a change, beneath the summary.
- `actor`: `person` | `system` | `absent`.

## Determinations

- The entry is a two-column row: a marker column at `--icon-size-marginalia` holding the glyph, and the content beside it. Every entry's content starts at the same inline offset, so a run reads as one column.
- The marker glyph is keyed to the kind of event, at `--icon-size-inline` on the `--icon-viewbox-sm` grid, centred on the connector the arranging Shape draws.
- Summary at the compact body size in `var(--text-primary)`, one line where possible.
- Actor and timestamp sit on the summary's line, after it, at the caption size in `var(--text-tertiary)`, separated by a middle dot.
- Detail sits `var(--sp-0-25)` beneath the summary at the caption size in `var(--text-secondary)`. A change states its previous and new values, so the entry is legible without opening the record's history elsewhere.
- The entry draws no connector of its own; the run's connector is the arranging Shape's (`libraries/shapes/activity-timeline.md`).

## Accessibility

- The timestamp is a `<time datetime>` element carrying the absolute moment, so a relative phrase like "yesterday" is still resolvable.
- The marker carries `aria-hidden="true"` — the summary already says what happened.
- The entry is a single list item so its parts are announced as one unit rather than as three fragments.
