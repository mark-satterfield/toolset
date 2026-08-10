---
kind: shape
name: activity-timeline
page_family: app
aliases: [activity log, history, audit trail, event log, state history]
status: stable
slots:
  - { name: entries, required: true, accepts: [timeline-entry] }
  - { name: day-dividers, required: false, accepts: [text] }
  - { name: load-earlier, required: false, accepts: [button] }
variants: [newest-first, oldest-first]
self_contained: false
content_defaults: {}
---

# activity-timeline — Events down a connected column

A vertical run of entries joined by a connector, newest first by default, optionally divided by day.

The entries are timeline-entry Components (`libraries/components/timeline-entry.md`); this arrangement owns the connector, the ordering, the dividers, and how more history is reached.

## Determinations

- One column at the container's full width. Entries stack with `--sp-1` between them.
- A `1px solid var(--border-subtle)` connector runs down the marker column, from the first entry's marker to the last. It stops at the markers rather than running past them, so the run reads as bounded rather than as continuing off-screen.
- `newest-first` is the default: a log is read to find out what just happened, and the most recent entry is what the reader came for. `oldest-first` suits a history read as a narrative from a known beginning.
- Day dividers, when present, are a full-width label breaking the connector, naming the day in words. They are not entries and carry no marker.
- `load-earlier`, when present, sits at the run's block-end for `newest-first` order. Older history is fetched on request rather than on scroll, so a user reading a long log is never pulled downward by content arriving beneath them.
- The run never virtualizes. A log short enough to read is short enough to render, and a log too long to render wants filtering rather than windowing.
- An empty run renders the empty state Component (`libraries/components/empty-state-card.md`), stating that nothing has happened yet rather than showing a bare connector.

## Accessibility

- The run is an ordered list, so each entry's position and the total count are announced.
- Day dividers are headings, so a screen reader can navigate day by day.
- The connector is a border and carries no semantics.
- `load-earlier` announces how many entries arrived and leaves focus on the control, so repeated use does not lose the reader's place.
