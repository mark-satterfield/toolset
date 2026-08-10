---
kind: shape
name: diagnostic-detail
page_family: shared
aliases: [more info modal, diagnostic modal, error detail, technical detail, support detail]
status: stable
slots:
  - { name: summary, required: true, accepts: [text] }
  - { name: detail-rows, required: true, accepts: [identifier-row, text] }
  - { name: copy-action, required: false, accepts: [button] }
variants: []
self_contained: false
content_defaults: {}
---

# diagnostic-detail — What a user would need to report a failure

The content of the panel a "more info" affordance opens from any alert: a plain-language summary of what happened, then the identifiers a support conversation would ask for. It fills a dialog (`libraries/components/dialog.md`); this arrangement fixes what goes inside it.

## Determinations

- A vertical stack: the summary paragraph at the body size, then the detail rows beneath a hairline rule.
- Each detail row is a label and a value. A machine identifier — a correlation id, a request id, a timestamp — uses the identifier row Component (`libraries/components/identifier-row.md`) so it is copyable rather than transcribable.
- `copy-action`, when present, copies every detail row as one block, because a user reporting a failure copies all of it or none of it.
- The panel restates the alert's own message as its summary rather than replacing it, so opening the detail never contradicts what the user already read.

## Informational only

The panel carries no action that changes state. It has no retry, no dismiss-and-continue, no destructive control — its only affordances are copying and closing. An action here would sit behind a "more info" label, where a user looking for an explanation would not expect to find one.

## Accessibility

- The panel inherits the dialog's focus trap, Escape-to-close, and focus-return contract.
- Detail rows are a description list, so each identifier is announced with the label naming it.
- The copy action confirms through the toast region (`libraries/components/toast.md`); a silent copy leaves a non-visual user unsure whether it happened.
