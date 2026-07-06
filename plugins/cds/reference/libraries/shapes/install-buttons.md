---
kind: shape
name: install-buttons
family: landing
aliases: [download buttons, platform downloads, app download row]
status: stable
slots:
  - { name: platform-buttons, required: true, accepts: [button] }
variants: []
self_contained: false
content_defaults:
  platforms: [macOS, Windows, iOS]
---

# install-buttons — Download/install button strip

A horizontal row of platform-specific install buttons, one button per platform.

## Determinations

- Buttons render in a fixed source-defined order (no OS-detected reordering), so the layout is stable across visitors. The detected platform may be visually emphasized (primary fill) while the rest are secondary, but every button's position stays fixed.
- Buttons sit on one centered row with a `--sp-1` gap; below the tablet breakpoint (`foundations/responsive.md` §17.1) they wrap to multiple centered rows without scrolling.
- The platform set is content: it is extensible, and the declared defaults in `content_defaults` are the drafted-mode scaffold; supplied content overrides them.
