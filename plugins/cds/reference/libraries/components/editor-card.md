---
kind: component
name: editor-card
page_family: app
aliases: [prompt turn card, message editor card, rich-text turn card, role-badged editor]
status: stable
slots:
  - { name: role-badge, required: true, accepts: [label] }
  - { name: content, required: true, accepts: [rich-text-editor] }
  - { name: leading-action, required: false, accepts: [button] }
  - { name: trailing-action, required: false, accepts: [icon-button] }
  - { name: helper, required: false, accepts: [text] }
sizing:
  width: "fills the parent track"
  height: "top padding + n × content line-height + bottom padding (grows with content)"
  radius: "--radius-sm"
  max-content-height: "40vh, then internal scroll"
behavior:
  - "states: rest | hover | focus | disabled | empty; collapsed/expanded toggle"
  - "role: system | user | assistant"
accessibility:
  - "badge <label> for= the textbox id; content role=textbox contenteditable"
  - "trailing actions are standalone tab-focusable buttons"
token_bindings: [--surface-raised, --border-subtle, --text-primary, --text-tertiary, --focus-ring, --typeface-sans]
composite: false
---

# Editor card

A self-contained card representing one labelled turn in a composed message sequence (system / user / assistant). The role badge is a small label absolutely positioned in the top-left corner of the card; the content area is a rich-text editor that fills the rest of the card. Optional trailing affordances (delete, info, expand, reorder) live in the top-right corner.

## Slots

- `role-badge` (required): one of "System Prompt", "User", "Assistant" — rendered as a `<label>` element absolutely positioned in the top-left corner.
- `content` (required): the editable text region, rendered as a rich-text editor (e.g., TipTap/ProseMirror). Carries `role="textbox"`. The card's top padding makes room for the badge above the first line of content.
- `leading-action` (optional): a button (e.g., "Generate Prompt") rendered inline at the start of the content row.
- `trailing-action` (optional): an icon button (delete / info / expand / reorder) positioned in the top-right corner with a ~4px inset.
- `helper` (optional): a one-line guidance sentence accompanying the badge, rendered in tertiary ink at the caption scale below the badge.

## Sizing

- Card outer: width fills the parent track; height grows with content — top padding + n × content line-height + bottom padding (calibrates to 69px single-line, 81px+ multi-line at the reference rendering).
- Card padding: top padding sized to seat the badge above the content (calibrates to 36px — badge at 12px from the top, 20px tall); the remaining sides at the small step (calibrates to 12px). Top padding inflates (calibrates to 48px) when a helper line is shown.
- Card border: hairline `--border-subtle` at rest (an alpha-thinned 1px per `foundations/layout.md` §11.9; calibrates to the sub-pixel hairline rendering).
- Card border-radius: `--radius-sm` (calibrates to 8px).
- Card ground: `--surface-raised` (theme-context dependent).
- Card layout: `display: flex; flex-direction: row; align-items: center` with a gap (calibrates to 8px).
- Wrapper (parent of each card): positioned relative — the positioning context for the absolute badge.
- Role badge: `<label>` with `for` pointing at the textbox's `id`; absolutely positioned in the top-left (calibrates to 12px from the left and top); transparent background; zero padding; content-sized.
- Content area: `<div role="textbox" contenteditable="true">`; transparent background; border `0`; padding `0` (the card's top padding handles the vertical offset).
- Trailing-action: icon-button geometry (calibrates to 32×32px), glyph at icon-glyph geometry (calibrates to 16×16px). Host-project implementations targeting WCAG 2.5.5 AAA should ship at ≥44×44px.

## Type bindings

- Role badge: body compact scale (calibrates to 14px), weight 400, `--typeface-sans`; ink `--text-tertiary`.
- Content text: body compact scale (calibrates to 14px, line-height 20px); ink `--text-primary`; `--typeface-sans`.
- Placeholder text: same family/size; ink `--text-tertiary`.
- Helper: caption scale (calibrates to 12px), weight 400, ink `--text-tertiary`.

## Behavior

- `hover`: card border steps within the hairline treatment via a color transition (calibrates to ~150ms ease).
- `focus` (content gains focus): the card border shifts to the input-focus signal (`--focus-ring` color); the focus signal is the border-color shift only, NOT an outline ring. Verify against the host's input-focus foundation.
- `disabled`: `cursor: not-allowed; opacity: 0.5`.
- Reduced motion: suppress the border-color transition for an instant border swap.

## Accessibility

- The card wrapper carries no ARIA role — it's a layout container.
- The badge is a `<label>` with `for` pointing at the textbox's `id`, wiring the role announcement to focus.
- The content area carries `role="textbox"` and `contenteditable="true"`.
- Each trailing-action button is a standard `<button>`, tab-focusable on its own.

## Structural skeleton

```html
<div class="editor-card-wrapper"><!-- relative positioning context -->
  <label for="user-turn-13" class="editor-card__badge"><!-- absolute top-left; --text-tertiary -->User</label>
  <div class="editor-card"><!-- --surface-raised ground, --border-subtle hairline, --radius-sm -->
    <div id="user-turn-13" role="textbox" contenteditable="true" class="editor-card__content">
      <!-- editable rich-text content -->
    </div>
  </div>
</div>
```

## Collapsed state

A `collapsed` card shows only the role badge and a single-line preview of the content (truncated with ellipsis) at the single-line height; the trailing-action set reduces to an expand affordance that toggles back to the full editor. Toggling between collapsed and expanded animates height over 150ms with `--ease-in-out`, suppressed under `prefers-reduced-motion: reduce`.

## Placeholder text

The empty editor renders placeholder text via the editor's placeholder extension as a `::before` pseudo-element on the first empty block, in `--text-tertiary` at the content size; it also carries `aria-placeholder` on the `role="textbox"` element so screen readers announce it.

## Trailing-action catalog

Four trailing actions: Delete, Info, Expand, Reorder — each an icon button. Reorder is a drag handle (`cursor: grab`) that initiates row reordering; it carries `aria-label="Reorder turn"` and exposes keyboard reordering via Arrow Up/Down while focused (with `aria-grabbed` toggling).

## Max-height before scroll

The card uses `overflow: hidden` at the frame; the content editor grows to a `max-height` of `40vh`, after which the editor's own region scrolls internally while the badge and trailing actions stay pinned.
