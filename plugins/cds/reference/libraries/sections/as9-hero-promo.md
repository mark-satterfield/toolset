---
kind: section
name: hero-promo
id: AS9
family: app
aliases: [promo card, hero promotional card, upgrade banner card]
status: stable
mode: deterministic
content_contract:
  cta_label: "primary CTA text"
theme: default
composition_notes: []
---

# AS9 — Hero promo card

A full-width promotional card inside an app main pane: a title ("Build faster with your team"), a 1–2-line body, and a primary CTA on the left; a decorative art thumbnail on the right. The promo is the screen's onboarding or upgrade moment.

```html
<section class="hero-promo-card">
  <div class="hero-promo-card__text">
    <h2>Build faster with your team</h2>
    <p>Everything your team needs to ship, in one place…</p>
    <button class="btn-primary">Get started ›</button>
  </div>
  <div class="hero-promo-card__art">…</div>
</section>
```

## Determinations

- Art treatment: inline SVG that inherits the `--accent-heroes` slot via `currentColor` (`foundations/motion.md` §15.6) so it recolors per theme without per-theme artwork. No raster, no animation.
