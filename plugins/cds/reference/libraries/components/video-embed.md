---
kind: component
name: video-embed
aliases: [video player, embedded video, video frame, youtube embed, vimeo embed, third-party video, video facade]
status: stable
slots:
  - { name: source, required: true, accepts: [video-reference] }
  - { name: poster, required: true, accepts: [image] }
  - { name: caption, required: false, accepts: [text] }
sizing:
  frame: "aspect-ratio 16/9; the frame takes its container's full inline size and derives its block size from the ratio"
  radius: "--radius-lg"
  play-control: "--icon-size-button"
  caption-gap: "--sp-1 between the frame and its caption"
behavior:
  - "at rest the frame shows the poster and a play control; no request reaches the video host until the reader activates it"
  - "activation mounts the player in the frame in place, or opens it over the page in a lightbox, per the activation variant"
  - "the player never autoplays and never carries a muted autoplaying loop; playback begins on the reader's action"
  - "the frame holds one block size across both states, so mounting the player reflows nothing"
accessibility:
  - "the play control is a button whose accessible name states the action and the video's title"
  - "the host's caption track is requested and shown by default; a video with no caption track carries a transcript link in its caption slot"
  - "the poster's alt describes the video's subject, or is aria-hidden when the caption already does"
  - "an overlaid player returns focus to the play control on close"
  - "the mounted frame carries a title naming the video, since an untitled frame is announced only as a frame"
token_bindings:
  - --surface-secondary
  - --border-subtle
  - --text-primary
  - --text-secondary
  - --radius-lg
  - --icon-size-button
  - --sp-1
composite: false
content_defaults: {}
---

# Video embed

A ratio-locked frame holding one video from a third-party host, shown as a poster until the reader chooses to play it. The frame is the unit a Shape places when its slot accepts a video; the host, the player, and the network request all sit behind the reader's action rather than in front of it.

Distinct from the lightbox (`libraries/components/lightbox.md`), which is the overlay a video opens *into* and carries no poster state of its own, and from decorative looping media (`foundations/imagery.md` §16.5), which is artwork that happens to move and has no player, no controls, and no reader action.

## Anatomy

1. **poster** — the still frame at rest, filling the frame at the declared ratio.
2. **play control** — one button centered on the poster, at `--icon-size-button`, carrying the system play glyph (`libraries/components/icon-glyphs.md`).
3. **player** — the host's frame, absent until activation, filling the same box the poster filled.
4. **caption** — one optional line beneath the frame at the compact body size in `--text-secondary`.

## Variants

- `ratio`: `wide` (16/9, default) | `classic` (4/3) | `portrait` (9/16). The ratio is a property of the source material; a frame whose ratio disagrees with its video letterboxes inside the host's player rather than cropping it.
- `activation`: `in-place` (default — the player replaces the poster within the same frame) | `overlay` (the player opens in a lightbox above the page, leaving the poster in the flow).

## Determinations

- The frame takes its container's full inline size and derives its block size from the ratio, so a Shape sizes the video by sizing its slot and never by declaring a height.
- Ground at rest is `--surface-secondary` with a `1px solid var(--border-subtle)` hairline and `var(--radius-lg)`, so a poster that fails to load leaves a frame rather than a hole.
- The play control sits centered on the poster at `--icon-size-button`, painting through `currentColor` against the poster. It carries the system's own focus ring on `:focus-visible` (`foundations/accessibility.md` §18.2) rather than relying on the poster for contrast.
- Nothing is requested from the video host before activation: the poster is a local asset resolved through the artwork contract (`artwork.md`), and the player's source is assigned at activation. A frame that loads its player at page load has no facade, whatever it displays.
- The player requests the host's privacy-preserving delivery endpoint where the host offers one, and requests related-content suggestions and host branding be suppressed, so the frame ends at the video rather than at the host's wider content.
- Playback is inline on small viewports rather than handing off to the platform's fullscreen player, so the reader stays on the page.
- `overlay` activation composes the lightbox contract (`libraries/components/lightbox.md`) for the overlay itself: the blurred backdrop, the close glyph, and escape-to-close are the lightbox's, and this component supplies the poster, the trigger, and the source.
- Several embeds on one page each activate independently; activating one does not mount, unmount, or pause another.

## Accessibility

- The play control is a `<button>`, not the poster image with a handler. Its accessible name states both the action and which video it plays, since several posters on one page are otherwise indistinguishable.
- The mounted frame carries a `title` naming the video. A frame without one is announced as an unlabeled frame, and a reader tabbing into it has no way to know what it holds.
- Captions are requested from the host and shown by default. Where the host carries no caption track, the caption slot carries a link to a transcript — a video whose content exists nowhere in text is inaccessible regardless of how the player is framed.
- The poster takes `alt` describing what the video shows when the caption does not already say it, and `aria-hidden="true"` when it does, so the same description is not announced twice.
- Under `overlay` activation, focus moves into the overlay on open and returns to the play control on close.
- Nothing about the frame animates on entry or hover; the component's only motion is the video the reader started.
