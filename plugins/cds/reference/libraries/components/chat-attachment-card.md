---
kind: component
name: chat-attachment-card
aliases: [attachment, file card, output card, produced file, inline file]
status: stable
slots:
  - { name: type-glyph, required: true, accepts: [icon-glyph] }
  - { name: name, required: true, accepts: [text] }
  - { name: kind-line, required: true, accepts: [text] }
  - { name: action, required: false, accepts: [button] }
sizing:
  height: "a fixed two-line block: the name over its kind line"
  padding: "--sp-0-75"
  radius: "--radius-md"
  glyph: "--icon-size-feature on the --icon-viewbox-xl drawing grid"
  gap: "--sp-0-75 between the glyph and the name block"
behavior:
  - "static at rest; the card is a reference to a file, not a preview of it"
  - "the action is a single explicit verb — open, download, or view — never an implicit whole-card target that could surprise"
accessibility:
  - "the card's accessible name joins the file's name to its kind, since a name alone does not say what it is"
  - "the action names its verb and the file it acts on"
  - "the type glyph is decorative; the kind line carries the type in words"
token_bindings: [--surface-raised, --border-subtle, --text-primary, --text-tertiary, --radius-md, --icon-size-feature, --focus-ring, --sp-0-75]
composite: true
---

# Chat attachment card

A file referenced inside a conversation — supplied by the person or produced by the system — as a compact card carrying its name, its kind, and one way to get at it.

## A reference, not a preview

The card states what the file is; it does not render its contents. A preview inside a transcript competes with the turn around it, varies unpredictably in height, and is unreadable at the size a card affords. The action opens it where it can actually be read.

## Variants

- `origin`: `supplied` (the person attached it) | `produced` (the system created it).
- `action`: `present` (default) | `absent` — a card that is purely a record of what was attached.

## Determinations

- The card is a flex row: type glyph at the inline-start, the name over its kind line beside it, the action at the inline-end via `margin-inline-start: auto`.
- Ground `var(--surface-raised)`, `1px solid var(--border-subtle)`, `var(--radius-md)`, padding `var(--sp-0-75)`.
- Name at the compact body size in `var(--text-primary)`, one line, truncating with the full name as the card's accessible name.
- The kind line sits directly beneath at the caption size in `var(--text-tertiary)`, naming the file's category and format in words.
- The type glyph is `--icon-size-feature` on the `--icon-viewbox-xl` grid, keyed to the file's category rather than to its exact format, so the glyph set stays small and legible.
- The card takes the full inline width of the turn it sits in, so a run of attachments aligns.
- Adjacent cards are `var(--sp-0-5)` apart.
- The whole card is not a target. Its one explicit action is, so the card can be read and selected without triggering a download.

## Accessibility

- The accessible name joins the file's name to its kind — a name alone does not say what the thing is.
- The action's accessible name states its verb and the file, since several identical actions may appear in one transcript.
- The type glyph carries `aria-hidden="true"`; the kind line already says what it is.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
