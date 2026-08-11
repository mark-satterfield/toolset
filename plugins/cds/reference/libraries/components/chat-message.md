---
kind: component
name: chat-message
aliases: [message, chat turn, conversation turn, message bubble, reply]
status: stable
slots:
  - { name: body, required: true, accepts: [text, code-block, chat-attachment-card] }
  - { name: attachments, required: false, accepts: [chat-attachment-card] }
  - { name: turn-actions, required: false, accepts: [icon-button] }
sizing:
  authored-max-width: "a proportion of the column, so an authored turn never spans the full measure and stays visibly distinct from a response"
  authored-padding: "--sp-0-75 block, --sp-1 inline"
  authored-radius: "--radius-lg"
  response-measure: "--column-reading — the response is prose and takes a prose measure"
  turn-gap: "--sp-2 between adjacent turns"
behavior:
  - "a response streams in progressively; the turn's box grows with it and the transcript holds the growing turn in view unless the user has scrolled away"
  - "turn actions appear on hover and on focus-visible and reserve their space at rest"
accessibility:
  - "each turn names its author for assistive technology, since the visual asymmetry that distinguishes them carries no semantics"
  - "a streaming response is announced through the transcript's live region as it arrives, and is complete in the document when streaming ends"
  - "turn actions are reachable by keyboard, never by hover alone"
token_bindings: [--surface-secondary, --text-primary, --text-secondary, --radius-lg, --ease-in-out, --focus-ring, --sp-0-75, --sp-1, --sp-2]
composite: true
---

# Chat message

One turn in a conversation. The two kinds of turn are shaped differently on purpose, and the asymmetry is the entry's main determination.

## Authored and response are not mirror images

- An **authored** turn — what the person said — is a contained block: a ground, a radius, a bounded width, aligned to the inline-end. It is short, it is a discrete act, and it reads as a thing that was submitted.
- A **response** turn is plain prose on the surrounding ground: no container, no ground, no radius, aligned to the inline-start at a reading measure. It is long, it is what the user came to read, and a container around it would frame the page's primary content as an aside.

Symmetrical bubbles make a long response fight its own frame and waste inline space on both margins. The asymmetry is the design, not an inconsistency.

## Variants

- `author`: `authored` (the person's turn) | `response` (the system's turn).
- `state`: `complete` (default) | `streaming` — the response is still arriving | `interrupted` — the response stopped before completing, and says so in place rather than being silently truncated.
- `turn-actions`: `absent` (default) | `present` — per-turn controls such as copy or retry, revealed on hover and `:focus-visible`.

## Determinations

- Turns are `var(--sp-2)` apart. Adjacent turns by the same author use the same gap; the alignment already groups them, and a tighter gap makes a long exchange read as one block.
- The authored turn: ground `var(--surface-secondary)`, `var(--radius-lg)`, padding `var(--sp-0-75)` block and `var(--sp-1)` inline, capped well short of the column so it is visibly narrower than a response, aligned to the inline-end.
- The response turn: no ground, no border, no radius. Ink `var(--text-primary)` at the body size, at the `--column-reading` measure, aligned to the inline-start.
- A response may contain any body content — prose, lists, code blocks (`libraries/components/code-block.md`), attachment cards — laid out as it would be anywhere else on the page. It is a document, not a message.
- While `streaming`, the turn grows as content arrives with no per-token animation. Characters appearing with their own transition are unreadable at speed.
- An `interrupted` turn keeps everything it received and states that it stopped, at the caption size in `var(--text-secondary)`, beneath the content. Discarding partial output loses work the user may want.
- Turn actions sit at the turn's block-end, reserving their height at rest so revealing them does not shift the transcript.

## Accessibility

- Each turn carries an accessible name identifying its author. Alignment, ground, and radius are visual conventions with no semantics, so a screen reader learns nothing from them.
- A streaming response is announced through the transcript's live region as it arrives, so the reader is not told to go and look (`libraries/shapes/chat-transcript.md`).
- When streaming ends, the complete turn is in the document and readable in the normal reading order without any further action.
- Turn actions are real buttons, reachable by Tab, revealed by `:focus-visible` as well as by hover.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
