---
kind: component
name: lightbox
page_family: shared
aliases: [lightbox, video dialog, media modal, video lightbox]
status: stable
slots:
  - { name: content-panel, required: true, accepts: [video, image] }
  - { name: backdrop, required: true, accepts: [blurred-dark-wash] }
  - { name: close-glyph, required: true, accepts: [icon-button] }
sizing:
  content_panel: "up to 75rem, 90vw, 90vh"
behavior: [display-toggle-mount, backdrop-blur]
accessibility: [native-video-controls, caption-tracks, escape-close]
token_bindings: []
composite: false
---

# Lightbox

The modal dialog variant for video and image content, with a blurred backdrop: content panel + blurred near-black backdrop + close glyph. Shares the mount pattern of the dialog (`libraries/components/dialog.md`).

## Determinations

- Backdrop: mapped near-black neutral at 90% opacity with `backdrop-filter: blur(5–10px)`. Lightboxes are the only dialogs that apply backdrop blur.
- Content panel scales up to `75rem`, `90vw`, `90vh`.

## Video player controls

Use the browser-native `<video controls>` playback controls rather than a custom control bar, so the platform's accessible playback controls apply. Keyboard handling follows the native `<video>` contract: Space toggles play/pause when the player is focused, arrow keys seek and adjust volume, and `F` toggles fullscreen. Dialog-level Escape closes the lightbox (exiting fullscreen first if active), returning focus to the invoking element.

## Caption tracks

Embed captions via `<track kind="captions" srclang="…" label="…">`; default the captions track to showing when the host supplies one. Image content uses descriptive `alt` text on the `<img>` instead.
