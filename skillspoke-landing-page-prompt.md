# SkillSpoke Landing Page — Build Specification

**Output:** A single self-contained `index.html` file. All CSS in a `<style>` block. All JavaScript inline in a `<script>` block at the end of `<body>`. No external dependencies except Google Fonts loaded via `<link>` tags in `<head>`. No build tools, no frameworks, no component libraries, no npm packages.

**Fidelity target:** Awwwards / FWA / Webby caliber. This is not a wireframe. This is not a template. This is a finished, shippable marketing page that would make a design director pause scrolling.

---

## Table of Contents

1. [Document Setup](#1-document-setup)
2. [CSS Custom Properties](#2-css-custom-properties)
3. [Global Styles](#3-global-styles)
4. [Navigation](#4-navigation)
5. [Hero Section](#5-hero-section)
6. [Social Proof Strip](#6-social-proof-strip)
7. [Three Pillars Section](#7-three-pillars-section)
8. [How It Works Section](#8-how-it-works-section)
9. [Testimonial Section](#9-testimonial-section)
10. [Final CTA Section](#10-final-cta-section)
11. [Footer](#11-footer)
12. [Scroll Reveal System](#12-scroll-reveal-system)
13. [Responsive Behavior](#13-responsive-behavior)
14. [Accessibility Requirements](#14-accessibility-requirements)
15. [Anti-Slop Rules](#15-anti-slop-rules)

---

## 1. Document Setup

### `<head>` Contents

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SkillSpoke — Find Where You Belong</title>
  <meta name="description" content="SkillSpoke amplifies human capability through clarity, empathy, and elegant automation. Job seeking reimagined.">

  <!-- Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;0,700;1,400&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
</head>
```

### Semantic Structure

The `<body>` contains exactly these landmark elements in order:

```
<body>
  <header role="banner">         — Navigation
  <main role="main">
    <section id="hero">          — Hero
    <section id="proof">         — Social proof strip
    <section id="pillars">       — Three pillars
    <section id="how">           — How it works
    <section id="testimonial">   — Testimonial
    <section id="cta">           — Final CTA
  </main>
  <footer role="contentinfo">    — Footer
</body>
```

Every `<section>` gets an `aria-labelledby` attribute pointing to its heading element's `id`.

---

## 2. CSS Custom Properties

Define these on `:root`. Use them everywhere. Never use raw hex values in component styles.

```css
:root {
  /* Color */
  --color-bg:       #EDE8DF;
  --color-surface:  #F5F1EA;
  --color-ink:      #1C1A18;
  --color-muted:    #6B6560;
  --color-rule:     #CEC9BF;
  --color-accent:   #8B7355;
  --color-warm-hi:  #D4A96A;
  --color-white:    #FFFFFF;

  /* Typography */
  --font-serif:  'Lora', Georgia, serif;
  --font-sans:   'Inter', system-ui, sans-serif;
  --font-mono:   'JetBrains Mono', monospace;

  /* Spacing (8px base) */
  --space-1:   4px;
  --space-2:   8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-6:  24px;
  --space-8:  32px;
  --space-12: 48px;
  --space-16: 64px;
  --space-24: 96px;

  /* Layout */
  --max-width:   1140px;
  --prose-width:  680px;

  /* Radii */
  --radius-sm:  4px;
  --radius-md:  8px;
  --radius-lg: 16px;

  /* Elevation */
  --shadow-card: 0 2px 8px rgba(28,26,24,0.08), 0 1px 2px rgba(28,26,24,0.04);
  --shadow-lift: 0 8px 24px rgba(28,26,24,0.12);

  /* Motion */
  --ease-standard: cubic-bezier(0.4, 0, 0.2, 1);
  --duration-fast: 120ms;
  --duration-base: 200ms;
  --duration-slow: 320ms;
}
```

---

## 3. Global Styles

### Reset and Base

```css
*, *::before, *::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  scroll-behavior: smooth;
}

body {
  font-family: var(--font-sans);
  font-weight: 400;
  font-size: 1rem;
  line-height: 1.65;
  color: var(--color-ink);
  background-color: var(--color-bg);
}
```

### Typography Classes

| Class | Family | Weight | Size | Line Height | Letter Spacing | Text Transform |
|---|---|---|---|---|---|---|
| `.t-display` | `--font-serif` | 700 | `3.5rem` | 1.1 | `-0.02em` | none |
| `.t-h1` | `--font-serif` | 700 | `2.5rem` | 1.15 | `-0.015em` | none |
| `.t-h2` | `--font-serif` | 600 | `1.875rem` | 1.2 | `-0.01em` | none |
| `.t-h3` | `--font-sans` | 600 | `1.375rem` | 1.3 | `0` | none |
| `.t-body` | `--font-sans` | 400 | `1rem` | 1.65 | `0` | none |
| `.t-caption` | `--font-sans` | 400 | `0.8125rem` | 1.4 | `0` | none |
| `.t-eyebrow` | `--font-sans` | 500 | `0.75rem` | 1.0 | `0.12em` | uppercase |

### Typographic Correctness

All copy in this specification uses proper typographic characters. The builder MUST preserve them exactly:

- Curly quotes: `"` and `"` and `'` and `'` — never straight quotes
- Em dashes: `—` — never `--` or `-`
- Ellipsis: `...` — never three periods
- Apostrophes: `'` — never `'`

### Link Styles

```css
a {
  color: var(--color-accent);
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-thickness: 1px;
  transition: color var(--duration-base) var(--ease-standard);
}
a:hover {
  color: var(--color-ink);
}
a:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 3px;
  border-radius: 2px;
}
```

### Selection Color

```css
::selection {
  background: var(--color-warm-hi);
  color: var(--color-ink);
}
```

### Page-Level Texture

Apply a very subtle paper grain texture to `body` using a CSS noise technique. This prevents the flat-digital look and gives the warm-linen background material quality.

```css
body::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 9999;
  opacity: 0.03;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
  background-repeat: repeat;
  background-size: 256px 256px;
}
```

This grain overlay is the proprietary visual signature. It makes every surface feel like high-quality uncoated paper stock. The `0.03` opacity is critical — any higher and it becomes distracting. Any lower and it vanishes.

---

## 4. Navigation

### Structure

```html
<header role="banner" class="nav" id="nav">
  <nav aria-label="Main navigation">
    <div class="nav-inner">
      <a href="/" class="nav-logo" aria-label="SkillSpoke home">
        <span class="nav-logo-mark">S</span>
        <span class="nav-logo-text">SkillSpoke</span>
      </a>
      <ul class="nav-links" role="list">
        <li><a href="#pillars">How It Helps</a></li>
        <li><a href="#how">How It Works</a></li>
        <li><a href="#testimonial">Stories</a></li>
      </ul>
      <div class="nav-actions">
        <a href="#cta" class="btn btn-ghost">Sign In</a>
        <a href="#cta" class="btn btn-primary">Get Started</a>
      </div>
    </div>
  </nav>
</header>
```

### Logo Treatment

The logo mark is the letter `S` in `--font-serif`, weight 700, `1.25rem`, displayed inside a `28px x 28px` square with `background: var(--color-ink)`, `color: var(--color-bg)`, `border-radius: var(--radius-sm)`, centered with flexbox. The logomark and wordmark sit side by side with `var(--space-2)` gap.

The wordmark `SkillSpoke` is `--font-sans`, weight 600, `1.0625rem`, `color: var(--color-ink)`, `letter-spacing: -0.02em`.

### Sticky Behavior

The nav is `position: sticky; top: 0; z-index: 100;`.

**Default state** (page scrolled to top):
- `background: transparent`
- `border-bottom: none`
- `padding: var(--space-4) 0`

**Scrolled state** (once user scrolls past 80px — detected via JavaScript `scroll` event with `requestAnimationFrame` throttle):
- `background: rgba(237, 232, 223, 0.92)` (the bg color at 92% opacity)
- `backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);`
- `border-bottom: 1px solid var(--color-rule)`
- `padding: var(--space-3) 0`

Transition between states: `transition: background var(--duration-slow) var(--ease-standard), padding var(--duration-slow) var(--ease-standard), border-color var(--duration-slow) var(--ease-standard);`

### Nav Inner Layout

```css
.nav-inner {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 0 var(--space-6);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
```

Nav links: `display: flex; gap: var(--space-8);` — each link is `--font-sans`, weight 500, `0.875rem`, `color: var(--color-muted)`, no underline (override base link style with `text-decoration: none`). Hover: `color: var(--color-ink)`.

Nav actions: `display: flex; gap: var(--space-3); align-items: center;`

### Button Styles

**Primary button (`.btn-primary`):**
```css
.btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-accent);
  color: var(--color-white);
  font-family: var(--font-sans);
  font-weight: 500;
  font-size: 0.9rem;
  letter-spacing: 0.02em;
  padding: 10px 24px;
  border-radius: var(--radius-sm);
  border: none;
  cursor: pointer;
  text-decoration: none;
  transition: background var(--duration-base) var(--ease-standard),
              box-shadow var(--duration-base) var(--ease-standard);
}
.btn-primary:hover {
  background: #7A6548; /* accent darkened ~8% */
  box-shadow: var(--shadow-card);
}
.btn-primary:active {
  background: #6D5A40;
}
.btn-primary:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 3px;
}
```

**Ghost button (`.btn-ghost`):**
```css
.btn-ghost {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: var(--color-ink);
  font-family: var(--font-sans);
  font-weight: 500;
  font-size: 0.9rem;
  letter-spacing: 0.02em;
  padding: 10px 24px;
  border-radius: var(--radius-sm);
  border: 1.5px solid var(--color-ink);
  cursor: pointer;
  text-decoration: none;
  transition: background var(--duration-base) var(--ease-standard),
              color var(--duration-base) var(--ease-standard);
}
.btn-ghost:hover {
  background: var(--color-ink);
  color: var(--color-bg);
}
.btn-ghost:active {
  background: #333028;
  color: var(--color-bg);
}
.btn-ghost:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 3px;
}
```

---

## 5. Hero Section

### The Design Commitment

The hero is NOT a standard 50/50 split. It is an **editorial magazine spread**. The image placeholder occupies the left 45% of the viewport as a tall vertical panel from the top of the hero to its bottom — like a full-page photograph in a book gutter. The text content sits on the right 55%, vertically centered, with generous left margin creating a wide breathing channel between image and text.

This layout communicates: "We are a publication, not a dashboard."

### Structure

```html
<section id="hero" aria-labelledby="hero-heading">
  <div class="hero-layout">
    <div class="hero-image" role="img" aria-label="Warm desk workspace with leather notebook, brass pen, and morning light casting long shadows across a dark walnut surface">
      <!-- Image placeholder -->
      <div class="img-placeholder">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>
      </div>
    </div>
    <div class="hero-content">
      <p class="t-eyebrow hero-eyebrow">For people navigating what comes next</p>
      <h1 id="hero-heading" class="t-display hero-heading">Find Where<br>You Belong</h1>
      <p class="hero-body t-body">Job seeking is one of life's most stressful journeys. SkillSpoke exists to make you feel in command of it — never contained by it. We bring clarity to chaos, warmth to a cold process, and real momentum to the search for meaningful work.</p>
      <div class="hero-cta-group">
        <a href="#cta" class="btn btn-primary btn-lg">Start Your Journey</a>
        <a href="#how" class="hero-learn-link">See how it works <span aria-hidden="true">&darr;</span></a>
      </div>
    </div>
  </div>
</section>
```

### Hero Layout

```css
.hero-layout {
  display: grid;
  grid-template-columns: 45fr 55fr;
  min-height: calc(100vh - 60px); /* viewport minus nav */
  max-width: none; /* full bleed */
}
```

### Hero Image Panel (Left)

```css
.hero-image {
  position: relative;
  overflow: hidden;
}
```

The image placeholder fills this entire panel:

```css
.img-placeholder {
  width: 100%;
  height: 100%;
  min-height: 500px;
  background: var(--color-surface);
  border-right: 1px solid var(--color-rule);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-muted);
}
.img-placeholder svg {
  width: 48px;
  height: 48px;
  opacity: 0.4;
}
```

The placeholder is an intentional design element — a `--color-surface` rectangle with a `1px --color-rule` right border and a centered Lucide `Image` icon (the SVG in the markup above) rendered at `48px` in `--color-muted` at `40%` opacity. This is NOT a "TODO" or "coming soon" — it is a designed empty state that communicates photographic intent through its proportions and placement.

### Hero Content (Right)

```css
.hero-content {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: var(--space-24) var(--space-16) var(--space-24) var(--space-16);
  max-width: 620px;
}
```

### Hero Eyebrow

```css
.hero-eyebrow {
  color: var(--color-accent);
  margin-bottom: var(--space-6);
}
```

### Hero Heading

The display heading `Find Where You Belong` is rendered at `3.5rem`, weight 700, `--font-serif`, `line-height: 1.1`, `letter-spacing: -0.02em`, `color: var(--color-ink)`.

**The proprietary touch:** The word "Belong" has a decorative underline — a `2px` thick line in `var(--color-warm-hi)` positioned `4px` below the baseline, spanning the full width of the word. Implement with a `<span>` wrapping "Belong" and a `::after` pseudo-element:

```css
.hero-heading .underline-accent {
  position: relative;
  display: inline;
}
.hero-heading .underline-accent::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -4px;
  height: 2px;
  background: var(--color-warm-hi);
}
```

Update the heading markup:
```html
<h1 id="hero-heading" class="t-display hero-heading">Find Where<br>You <span class="underline-accent">Belong</span></h1>
```

### Hero Body Text

`margin-top: var(--space-6);` — `max-width: 480px;` — `color: var(--color-muted);`

### Hero CTA Group

```css
.hero-cta-group {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  margin-top: var(--space-8);
}
```

The large primary button (`.btn-lg`) has `padding: 14px 32px; font-size: 1rem;` — slightly larger than the nav button.

The "See how it works" link: `--font-sans`, weight 500, `0.875rem`, `color: var(--color-muted)`, `text-decoration: none`. The down arrow is `--color-accent`. On hover: `color: var(--color-ink)`. This is not a button — it is a text link with an arrow.

### Hero Entrance Animation

On page load (not scroll — this is the first thing visible), the hero content animates in with staggered timing. Each element fades up from `translateY(24px), opacity: 0` to `translateY(0), opacity: 1`.

| Element | Delay |
|---|---|
| Eyebrow | 200ms |
| Heading | 350ms |
| Body text | 500ms |
| CTA group | 650ms |

Duration for all: `600ms`. Easing: `var(--ease-standard)`.

The hero image panel fades in from `opacity: 0` to `opacity: 1` over `800ms` with a `100ms` delay.

Implement with CSS `@keyframes` and `animation` properties. Set initial state with `opacity: 0; transform: translateY(24px);` on each element, then apply the animation with appropriate `animation-delay`.

```css
@keyframes fadeUp {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
@keyframes fadeIn {
  to {
    opacity: 1;
  }
}
```

---

## 6. Social Proof Strip

### Design Intent

A thin horizontal band that breaks the hero's editorial gravity with a quiet credibility signal. This is NOT a logo carousel. It is a single-line typographic statement flanked by thin rules.

### Structure

```html
<section id="proof" aria-labelledby="proof-heading">
  <div class="proof-strip">
    <hr class="proof-rule" aria-hidden="true">
    <p id="proof-heading" class="t-caption proof-text">
      Trusted by 12,000+ job seekers who refused to settle
    </p>
    <div class="proof-stats">
      <div class="proof-stat">
        <span class="proof-stat-number">12k+</span>
        <span class="proof-stat-label">Active seekers</span>
      </div>
      <span class="proof-divider" aria-hidden="true"></span>
      <div class="proof-stat">
        <span class="proof-stat-number">89%</span>
        <span class="proof-stat-label">Land interviews within 30 days</span>
      </div>
      <span class="proof-divider" aria-hidden="true"></span>
      <div class="proof-stat">
        <span class="proof-stat-number">4.8</span>
        <span class="proof-stat-label">Average user rating</span>
      </div>
    </div>
    <hr class="proof-rule" aria-hidden="true">
  </div>
</section>
```

### Layout

```css
.proof-strip {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--space-16) var(--space-6);
  text-align: center;
}
```

### Proof Rules

`hr.proof-rule`: `border: none; height: 1px; background: var(--color-rule); margin: 0 auto; max-width: 480px;`

### Proof Text

The trust statement sits between the two rules. `color: var(--color-muted);` — `margin: var(--space-8) 0;`

### Proof Stats

```css
.proof-stats {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--space-8);
  margin: var(--space-6) 0;
}
```

Each `.proof-stat`:
- `.proof-stat-number`: `--font-serif`, weight 700, `1.5rem`, `color: var(--color-ink)`, `line-height: 1.2`
- `.proof-stat-label`: `--font-sans`, weight 400, `0.8125rem`, `color: var(--color-muted)`, `line-height: 1.4`, displayed as block element below the number

`.proof-divider`: `width: 1px; height: 32px; background: var(--color-rule);`

### Scroll Reveal

The entire proof strip gets the `[data-reveal]` attribute and animates as one unit (no stagger). Fade up from `translateY(16px)`.

---

## 7. Three Pillars Section

### Design Intent

Three vertical editorial columns — not cards. Think of a newspaper's three-column layout where each column is a self-contained story. The columns are separated by thin vertical rules, not gutters or card edges. This reinforces the editorial identity.

### Copy

**Section eyebrow:** `WHAT DRIVES US`

**Section heading:** `Nurture. Illuminate. Transform.`

**Section intro:** `Three commitments that shape every feature we build, every line of code we write, and every interaction you'll ever have with SkillSpoke.`

**Pillar 1 — Nurture**
- Icon: Lucide `Heart` (24x24, 1.5px stroke, rounded caps)
- Heading: `Nurture`
- Subhead: `The Caregiver`
- Body: `Job seeking bruises. Applications vanish into voids. Rejections arrive without explanation. We built SkillSpoke to be the steady hand through all of it — guiding you forward when the path gets rough, celebrating every small victory, protecting your confidence when it wavers.`

**Pillar 2 — Illuminate**
- Icon: Lucide `Lightbulb` (24x24, 1.5px stroke, rounded caps)
- Heading: `Illuminate`
- Subhead: `The Sage`
- Body: `Most platforms show you jobs. We show you yourself — your real strengths, your hidden gaps, the patterns in your career you haven't noticed yet. Honest insight delivered with warmth, because understanding where you stand is the first step to getting where you belong.`

**Pillar 3 — Transform**
- Icon: Lucide `Sparkles` (24x24, 1.5px stroke, rounded caps)
- Heading: `Transform`
- Subhead: `The Magician`
- Body: `Resumes rewritten with your authentic voice. Cover letters that feel like you wrote them on your best day. Interview prep that turns anxiety into articulation. We take the mundane, repetitive work of job seeking and make it feel meaningful.`

### Structure

```html
<section id="pillars" aria-labelledby="pillars-heading">
  <div class="pillars-container">
    <div class="pillars-header">
      <p class="t-eyebrow pillars-eyebrow">What Drives Us</p>
      <h2 id="pillars-heading" class="t-h1 pillars-heading">Nurture. Illuminate. Transform.</h2>
      <p class="t-body pillars-intro">Three commitments that shape every feature we build, every line of code we write, and every interaction you'll ever have with SkillSpoke.</p>
    </div>
    <div class="pillars-grid">
      <article class="pillar" data-reveal data-reveal-delay="0">
        <!-- SVG icon inline -->
        <div class="pillar-icon"><!-- Lucide Heart SVG --></div>
        <h3 class="t-h2 pillar-title">Nurture</h3>
        <p class="t-eyebrow pillar-archetype">The Caregiver</p>
        <p class="t-body pillar-body"><!-- Body text --></p>
      </article>
      <div class="pillar-rule" aria-hidden="true"></div>
      <article class="pillar" data-reveal data-reveal-delay="1">
        <!-- ... Illuminate ... -->
      </article>
      <div class="pillar-rule" aria-hidden="true"></div>
      <article class="pillar" data-reveal data-reveal-delay="2">
        <!-- ... Transform ... -->
      </article>
    </div>
  </div>
</section>
```

### Layout

```css
.pillars-container {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--space-24) var(--space-6);
}
.pillars-header {
  max-width: var(--prose-width);
  margin: 0 auto var(--space-16);
  text-align: center;
}
.pillars-heading {
  margin-top: var(--space-4);
}
.pillars-intro {
  color: var(--color-muted);
  margin-top: var(--space-4);
}
.pillars-grid {
  display: grid;
  grid-template-columns: 1fr auto 1fr auto 1fr;
  gap: 0;
  align-items: start;
}
```

### Pillar Column

```css
.pillar {
  padding: var(--space-8) var(--space-8);
}
.pillar-icon {
  color: var(--color-accent);
  margin-bottom: var(--space-4);
}
.pillar-title {
  margin-bottom: var(--space-2);
}
.pillar-archetype {
  color: var(--color-warm-hi);
  margin-bottom: var(--space-6);
}
.pillar-body {
  color: var(--color-muted);
}
```

### Vertical Rules

```css
.pillar-rule {
  width: 1px;
  background: var(--color-rule);
  align-self: stretch;
  margin: var(--space-8) 0;
}
```

### Lucide SVG Icons

Inline the SVG for each icon. All icons: `width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"`.

**Heart:**
```html
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/></svg>
```

**Lightbulb:**
```html
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>
```

**Sparkles:**
```html
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>
```

### Scroll Reveal

Each pillar article gets `data-reveal` and a staggered delay. They fade up from `translateY(20px)` with `100ms` stagger between them. The section header (eyebrow + heading + intro) also reveals as a unit before the pillars.

---

## 8. How It Works Section

### Design Intent

A vertical stepped flow with a thin connecting line — like a timeline in an annual report. Each step has a large numeral on the left, content on the right. The connecting line runs between the numerals. This is NOT a horizontal step-by-step carousel.

### Copy

**Section eyebrow:** `THE PROCESS`

**Section heading:** `Four steps to clarity`

**Section intro:** `No setup wizards. No 47-field profile forms. SkillSpoke meets you where you are and moves at your pace.`

**Step 1**
- Number: `01`
- Heading: `Tell us what you know`
- Body: `Upload a resume, paste a LinkedIn URL, or just start talking. SkillSpoke maps your skills, experience, and strengths — then shows you the picture you can't see from inside your own career.`

**Step 2**
- Number: `02`
- Heading: `See what fits`
- Body: `Our matching engine doesn't just scan keywords. It understands context — what you've done, what you're capable of, and what will actually make you happy. Roles surface because they make sense, not because they paid to appear.`

**Step 3**
- Number: `03`
- Heading: `Apply with confidence`
- Body: `Every application gets a tailored resume and cover letter written in your voice. We handle the formatting, the keywords, the ATS optimization — so you can focus on the human parts of the conversation.`

**Step 4**
- Number: `04`
- Heading: `Prepare and land`
- Body: `Interview coaching built from real data about the role, the company, and the questions they actually ask. Walk in prepared. Walk out knowing you gave your best.`

### Structure

```html
<section id="how" aria-labelledby="how-heading">
  <div class="how-container">
    <div class="how-header">
      <p class="t-eyebrow how-eyebrow">The Process</p>
      <h2 id="how-heading" class="t-h1 how-heading">Four steps to clarity</h2>
      <p class="t-body how-intro">No setup wizards. No 47-field profile forms. SkillSpoke meets you where you are and moves at your pace.</p>
    </div>
    <div class="how-steps">
      <div class="how-step" data-reveal data-reveal-delay="0">
        <div class="how-step-number-col">
          <span class="how-step-number">01</span>
          <div class="how-step-line" aria-hidden="true"></div>
        </div>
        <div class="how-step-content">
          <h3 class="t-h2 how-step-title">Tell us what you know</h3>
          <p class="t-body how-step-body">Upload a resume, paste a LinkedIn URL, or just start talking. SkillSpoke maps your skills, experience, and strengths — then shows you the picture you can't see from inside your own career.</p>
        </div>
      </div>
      <!-- Steps 02, 03, 04 follow the same pattern -->
      <!-- The LAST step (04) does NOT have the .how-step-line element -->
    </div>
  </div>
</section>
```

### Layout

```css
.how-container {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--space-24) var(--space-6);
}
.how-header {
  max-width: var(--prose-width);
  margin-bottom: var(--space-16);
  /* Left-aligned, not centered — a deliberate asymmetry */
}
.how-intro {
  color: var(--color-muted);
  margin-top: var(--space-4);
}
.how-steps {
  max-width: 800px;
}
.how-step {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: var(--space-6);
}
```

### Step Number Column

```css
.how-step-number-col {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.how-step-number {
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: 1.5rem;
  color: var(--color-warm-hi);
  line-height: 1;
}
.how-step-line {
  width: 1px;
  flex: 1;
  background: var(--color-rule);
  margin-top: var(--space-4);
  min-height: 40px;
}
```

### Step Content

```css
.how-step-content {
  padding-bottom: var(--space-12);
}
.how-step-title {
  margin-bottom: var(--space-3);
}
.how-step-body {
  color: var(--color-muted);
  max-width: 520px;
}
```

### Scroll Reveal

Each step reveals independently with `150ms` stagger between them. Fade up from `translateY(20px)`. The section header reveals first as a unit.

---

## 9. Testimonial Section

### Design Intent

A single, large-format pull quote — not a carousel, not a grid of testimonial cards. One voice, given room to breathe. The quote occupies a full-width band with a subtle background shift to `--color-surface` to differentiate it from surrounding sections. Think of a featured pull quote in a magazine spread — large italic serif text, a thin rule above, a compact attribution below.

### Copy

**Quote:** `"I'd been applying to jobs for four months and getting nowhere. SkillSpoke didn't just find me better roles — it helped me understand why I was stuck. Within three weeks, I had two interviews that actually excited me. For the first time in months, I felt like I was moving forward."`

**Attribution:** `Sarah Chen, Product Designer`
**Context:** `Placed at Figma after 4 months of searching`

### Structure

```html
<section id="testimonial" aria-labelledby="testimonial-heading">
  <div class="testimonial-container">
    <hr class="testimonial-rule" aria-hidden="true">
    <blockquote class="testimonial-quote">
      <p id="testimonial-heading" class="testimonial-text">"I'd been applying to jobs for four months and getting nowhere. SkillSpoke didn't just find me better roles — it helped me understand why I was stuck. Within three weeks, I had two interviews that actually excited me. For the first time in months, I felt like I was moving forward."</p>
      <footer class="testimonial-attribution">
        <div class="testimonial-avatar">
          <!-- 48x48 circle placeholder -->
          <div class="avatar-placeholder" aria-hidden="true">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          </div>
        </div>
        <div class="testimonial-meta">
          <cite class="testimonial-name">Sarah Chen, Product Designer</cite>
          <span class="testimonial-context">Placed at Figma after 4 months of searching</span>
        </div>
      </footer>
    </blockquote>
  </div>
</section>
```

### Layout

```css
.testimonial-container {
  max-width: var(--prose-width);
  margin: 0 auto;
  padding: var(--space-24) var(--space-6);
}
```

Full section background: `background: var(--color-surface);` applied to the `<section>` element itself, not the container. This creates a full-bleed background band.

### Testimonial Rule

`hr.testimonial-rule`: `border: none; height: 1px; background: var(--color-rule); margin-bottom: var(--space-12);`

### Quote Text

```css
.testimonial-text {
  font-family: var(--font-serif);
  font-weight: 400;
  font-style: italic;
  font-size: 1.5rem;
  line-height: 1.5;
  color: var(--color-ink);
  letter-spacing: -0.01em;
}
```

Note: The quote uses typographically correct curly double quotes `"` and `"` — these are already in the copy above. Do NOT replace them with straight quotes.

### Avatar Placeholder

```css
.avatar-placeholder {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--color-bg);
  border: 1px solid var(--color-rule);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-muted);
}
```

The Lucide `User` icon SVG (20x20) is centered inside.

### Attribution

```css
.testimonial-attribution {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-top: var(--space-8);
}
.testimonial-name {
  font-family: var(--font-sans);
  font-weight: 600;
  font-size: 0.9rem;
  font-style: normal;
  color: var(--color-ink);
  display: block;
}
.testimonial-context {
  font-family: var(--font-sans);
  font-weight: 400;
  font-size: 0.8125rem;
  color: var(--color-muted);
  display: block;
  margin-top: 2px;
}
```

### Scroll Reveal

The testimonial section reveals as one unit: the rule fades in first, then the quote text fades up from `translateY(16px)`, then the attribution follows `200ms` later.

---

## 10. Final CTA Section

### Design Intent

An inverted section — `--color-ink` background with `--color-bg` text. This creates the strongest visual break on the page and signals finality. The CTA is centered, typographic, and confident. No decoration, no imagery. Just words and a button.

### Copy

**Eyebrow:** `READY?`

**Heading:** `Your next chapter starts with one click`

**Body:** `No credit card. No 30-minute onboarding. Just you, your experience, and a platform built to find where you belong.`

**Primary CTA button:** `Get Started — It's Free`

**Secondary link:** `Have questions? Let's talk.`

### Structure

```html
<section id="cta" aria-labelledby="cta-heading">
  <div class="cta-container">
    <p class="t-eyebrow cta-eyebrow">Ready?</p>
    <h2 id="cta-heading" class="t-h1 cta-heading">Your next chapter starts<br>with one click</h2>
    <p class="t-body cta-body">No credit card. No 30-minute onboarding. Just you, your experience, and a platform built to find where you belong.</p>
    <div class="cta-actions">
      <a href="#" class="btn btn-primary btn-lg btn-inverted">Get Started — It's Free</a>
      <a href="#" class="cta-secondary-link">Have questions? Let's talk.</a>
    </div>
  </div>
</section>
```

### Section Background

```css
#cta {
  background: var(--color-ink);
  color: var(--color-bg);
}
```

### Layout

```css
.cta-container {
  max-width: var(--prose-width);
  margin: 0 auto;
  padding: var(--space-24) var(--space-6);
  text-align: center;
}
```

### Typography Overrides

```css
.cta-eyebrow {
  color: var(--color-warm-hi);
  margin-bottom: var(--space-6);
}
.cta-heading {
  color: var(--color-bg);
}
.cta-body {
  color: rgba(237, 232, 223, 0.7); /* --color-bg at 70% */
  margin-top: var(--space-4);
  max-width: 480px;
  margin-left: auto;
  margin-right: auto;
}
```

### Inverted Button

```css
.btn-inverted {
  background: var(--color-bg);
  color: var(--color-ink);
}
.btn-inverted:hover {
  background: var(--color-white);
  box-shadow: 0 4px 16px rgba(237, 232, 223, 0.2);
}
```

### CTA Actions

```css
.cta-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-4);
  margin-top: var(--space-8);
}
.cta-secondary-link {
  color: rgba(237, 232, 223, 0.6);
  font-size: 0.875rem;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.cta-secondary-link:hover {
  color: var(--color-bg);
}
```

### Scroll Reveal

The CTA section reveals as a staggered unit: eyebrow, then heading (+150ms), then body (+300ms), then actions (+450ms). All fade up from `translateY(20px)`.

---

## 11. Footer

### Design Intent

A quiet, utilitarian footer. Not massive, not showy. Two rows: the top row has four columns of links; the bottom row has copyright and social icons, separated by a thin rule.

### Copy

**Column 1 — Product**
- Features
- Pricing
- How It Works
- Changelog

**Column 2 — Company**
- About
- Careers
- Blog
- Press

**Column 3 — Support**
- Help Center
- Contact Us
- Status
- Privacy Policy

**Column 4 — Legal**
- Terms of Service
- Privacy Policy
- Cookie Policy
- GDPR

**Copyright:** `&copy; 2026 SkillSpoke. All rights reserved.`

**Social icons (4):** LinkedIn, X (Twitter), GitHub, RSS

### Structure

```html
<footer role="contentinfo">
  <div class="footer-container">
    <div class="footer-grid">
      <div class="footer-col">
        <h4 class="t-eyebrow footer-col-title">Product</h4>
        <ul role="list">
          <li><a href="#">Features</a></li>
          <li><a href="#">Pricing</a></li>
          <li><a href="#">How It Works</a></li>
          <li><a href="#">Changelog</a></li>
        </ul>
      </div>
      <!-- Repeat for Company, Support, Legal -->
    </div>
    <hr class="footer-rule" aria-hidden="true">
    <div class="footer-bottom">
      <p class="footer-copyright">&copy; 2026 SkillSpoke. All rights reserved.</p>
      <div class="footer-social" aria-label="Social media links">
        <a href="#" aria-label="LinkedIn"><!-- LinkedIn SVG --></a>
        <a href="#" aria-label="X (Twitter)"><!-- X SVG --></a>
        <a href="#" aria-label="GitHub"><!-- GitHub SVG --></a>
        <a href="#" aria-label="RSS"><!-- RSS SVG --></a>
      </div>
    </div>
  </div>
</footer>
```

### Layout

```css
.footer-container {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--space-16) var(--space-6) var(--space-8);
}
.footer-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-8);
}
```

### Footer Column

```css
.footer-col-title {
  color: var(--color-ink);
  margin-bottom: var(--space-4);
}
.footer-col ul {
  list-style: none;
}
.footer-col li {
  margin-bottom: var(--space-2);
}
.footer-col a {
  font-size: 0.875rem;
  color: var(--color-muted);
  text-decoration: none;
}
.footer-col a:hover {
  color: var(--color-ink);
}
```

### Footer Bottom

```css
.footer-rule {
  border: none;
  height: 1px;
  background: var(--color-rule);
  margin: var(--space-8) 0;
}
.footer-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.footer-copyright {
  font-size: 0.8125rem;
  color: var(--color-muted);
}
```

### Social Icons

Each social link: `display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px;`

Icon SVGs: `20px x 20px`, `stroke="currentColor"`, `stroke-width="1.5"`, `fill="none"`.

Color: `var(--color-muted)`. Hover: `var(--color-ink)`. Transition: `color var(--duration-base) var(--ease-standard)`.

`.footer-social`: `display: flex; gap: var(--space-3);`

**Social icon SVGs** (inline, Lucide icon set):

**LinkedIn:**
```html
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/></svg>
```

**X (Twitter) — use a simple X mark:**
```html
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 4l11.733 16h4.267l-11.733 -16h-4.267z"/><path d="M4 20l6.768 -6.768"/><path d="M20 4l-6.768 6.768"/></svg>
```

**GitHub:**
```html
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/></svg>
```

**RSS:**
```html
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 11a9 9 0 0 1 9 9"/><path d="M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/></svg>
```

---

## 12. Scroll Reveal System

### JavaScript Implementation

Use a single `IntersectionObserver` instance. No scroll event listeners for reveals (only the nav uses a scroll listener).

```javascript
document.addEventListener('DOMContentLoaded', () => {

  // --- Nav scroll state ---
  const nav = document.getElementById('nav');
  let ticking = false;
  window.addEventListener('scroll', () => {
    if (!ticking) {
      requestAnimationFrame(() => {
        if (window.scrollY > 80) {
          nav.classList.add('nav--scrolled');
        } else {
          nav.classList.remove('nav--scrolled');
        }
        ticking = false;
      });
      ticking = true;
    }
  });

  // --- Scroll reveal ---
  const revealElements = document.querySelectorAll('[data-reveal]');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const delay = parseInt(entry.target.dataset.revealDelay || '0', 10);
        entry.target.style.transitionDelay = `${delay * 100}ms`;
        entry.target.classList.add('revealed');
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.15,
    rootMargin: '0px 0px -40px 0px'
  });

  revealElements.forEach(el => observer.observe(el));
});
```

### CSS for Reveal

```css
[data-reveal] {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 600ms var(--ease-standard),
              transform 600ms var(--ease-standard);
}
[data-reveal].revealed {
  opacity: 1;
  transform: translateY(0);
}
```

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }

  [data-reveal] {
    opacity: 1;
    transform: none;
  }
}
```

### Where to Apply `data-reveal`

| Element | `data-reveal-delay` |
|---|---|
| Proof strip (entire section inner) | `0` |
| Pillars header (eyebrow + heading + intro as one wrapper) | `0` |
| Pillar 1 | `0` |
| Pillar 2 | `1` |
| Pillar 3 | `2` |
| How-it-works header | `0` |
| How step 1 | `0` |
| How step 2 | `1` |
| How step 3 | `2` |
| How step 4 | `3` |
| Testimonial rule | `0` |
| Testimonial quote | `1` |
| Testimonial attribution | `2` |
| CTA eyebrow | `0` |
| CTA heading | `1` |
| CTA body | `2` |
| CTA actions | `3` |

---

## 13. Responsive Behavior

### Breakpoint

One breakpoint: `768px`. Below 768px is mobile. At and above 768px is desktop.

### Mobile Adjustments (max-width: 767px)

**Navigation:**
- Hide `.nav-links` entirely (`display: none`). The three internal page links are discoverable via scrolling.
- Hide `.btn-ghost` (Sign In). Keep only the primary CTA button.
- `.nav-inner` becomes: logo on left, primary button on right.
- Nav padding: `var(--space-3) 0`

**Hero:**
- `.hero-layout` becomes `grid-template-columns: 1fr` (single column).
- The image panel comes first in DOM order but collapses to `height: 280px` (no longer full-viewport-height).
- `.hero-content` padding changes to `var(--space-12) var(--space-6)`.
- Display heading size: `2.5rem` (down from `3.5rem`).
- Hero body max-width: `100%`.

**Social Proof:**
- `.proof-stats` becomes `flex-direction: column; gap: var(--space-6);`
- `.proof-divider` becomes `width: 48px; height: 1px;` (horizontal rule instead of vertical).

**Three Pillars:**
- `.pillars-grid` becomes `grid-template-columns: 1fr` (single column stack).
- `.pillar-rule` elements become horizontal: `width: 100%; height: 1px; margin: var(--space-4) 0;`
- Pillar padding: `var(--space-6) 0`

**How It Works:**
- `.how-step` grid becomes `grid-template-columns: 48px 1fr` (narrower number column).
- Step number font-size: `1.25rem`.

**Testimonial:**
- Quote font-size: `1.25rem` (down from `1.5rem`).

**CTA:**
- Heading size: `2rem` (down from `2.5rem`).
- Padding: `var(--space-16) var(--space-6)`.

**Footer:**
- `.footer-grid` becomes `grid-template-columns: repeat(2, 1fr)` (2x2 grid).
- `.footer-bottom` becomes `flex-direction: column; align-items: center; gap: var(--space-4); text-align: center;`

### Container Padding

At mobile: all containers use `padding-left: var(--space-6); padding-right: var(--space-6);`
This is already the case in the desktop specs (using `var(--space-6)` for gutters), so no change is needed. The `max-width` constraint on containers handles the desktop sizing.

---

## 14. Accessibility Requirements

### Semantic HTML

- Use `<header>`, `<main>`, `<footer>`, `<section>`, `<nav>`, `<article>`, `<blockquote>`, `<cite>` correctly as specified in the structures above.
- Every `<section>` has `aria-labelledby` pointing to its heading.
- The nav has `aria-label="Main navigation"`.
- Footer social links container has `aria-label="Social media links"`.
- Each social icon link has an individual `aria-label` (e.g., `aria-label="LinkedIn"`).
- All decorative SVGs have `aria-hidden="true"`.
- All image placeholders have a meaningful `role="img"` and `aria-label` describing the intended photograph.

### Focus Management

- All interactive elements (links, buttons) have visible `:focus-visible` styles: `outline: 2px solid var(--color-accent); outline-offset: 3px; border-radius: 2px;`
- Tab order follows DOM order (no `tabindex` manipulation needed).
- Skip link: Add a visually hidden skip link as the very first element in `<body>`:

```html
<a href="#hero" class="skip-link">Skip to main content</a>
```

```css
.skip-link {
  position: absolute;
  top: -100%;
  left: var(--space-4);
  background: var(--color-ink);
  color: var(--color-bg);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-sm);
  font-size: 0.875rem;
  z-index: 200;
  text-decoration: none;
}
.skip-link:focus {
  top: var(--space-2);
}
```

### Color Contrast

All text/background combinations in this design system meet WCAG AA (4.5:1 for body text, 3:1 for large text):

| Foreground | Background | Ratio | Pass |
|---|---|---|---|
| `--color-ink` (#1C1A18) on `--color-bg` (#EDE8DF) | — | ~12.3:1 | AA |
| `--color-muted` (#6B6560) on `--color-bg` (#EDE8DF) | — | ~4.6:1 | AA |
| `--color-white` (#FFFFFF) on `--color-accent` (#8B7355) | — | ~4.0:1 | AA Large |
| `--color-bg` (#EDE8DF) on `--color-ink` (#1C1A18) | — | ~12.3:1 | AA |

The `--color-muted` on `--color-surface` is the tightest ratio (~4.2:1). It passes AA for body text (4.5:1 threshold applies at 16px and below; at the sizes we use it, this is acceptable). If the builder measures it at below 4.5:1, darken `--color-muted` to `#635E58`.

### Reduced Motion

Already specified in Section 12. The `prefers-reduced-motion: reduce` media query disables all animations and transitions and makes all `[data-reveal]` elements immediately visible.

### Reduced Transparency

```css
@media (prefers-reduced-transparency: reduce) {
  body::before {
    display: none; /* Remove grain overlay */
  }
  .nav--scrolled {
    background: var(--color-bg); /* Solid instead of translucent */
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
  }
}
```

---

## 15. Anti-Slop Rules

The builder MUST NOT do any of the following. These are hard rejections — if any appear in the output, the page has failed.

### Visual

1. **No gradients** — anywhere. No linear-gradient, no radial-gradient (except the SVG noise texture). All fills are solid.
2. **No glassmorphism** — no frosted glass panels, no layered blurs on content cards.
3. **No neon or glow effects** — no `box-shadow` with bright saturated colors, no `text-shadow` glow.
4. **No parallax scroll-jacking** — the page scrolls natively. No scroll hijacking, no momentum modification, no scroll-snap on the body.
5. **No stock photo services** — no Unsplash URLs, no Pexels embeds, no `picsum.photos`. Image placeholders are the designed `--color-surface` rectangles with Lucide icons as specified.
6. **No dark mode** — not in V1. No `prefers-color-scheme` media query. No theme toggle.
7. **No blue-tinted tech aesthetic** — no `#0066FF`, no `#6366F1`, no indigo, no violet, no cyan.
8. **No purple/violet as accent** — this is the most common AI design cliche. The accent is `--color-accent` (#8B7355) and nothing else.
9. **No emoji** in any copy or UI element.
10. **No decorative blobs or abstract shapes** floating in the background.
11. **No mesh gradients or aurora effects**.

### Typographic

12. **No Inter as the display/heading font** — headings use Lora (serif). Inter is for body and UI only.
13. **No straight quotes** — every quote mark must be typographically correct curly quotes.
14. **No double hyphens** where em dashes belong.
15. **No ALL CAPS on headings** — only eyebrow text is uppercase.

### Structural

16. **No component libraries** — no shadcn, no MagicUI, no 21st.dev, no Tailwind UI, no Chakra, no MUI. Everything is hand-written CSS.
17. **No Tailwind CSS** — no utility classes. Write semantic CSS.
18. **No CSS frameworks** — no Bootstrap, no Bulma, no Foundation.
19. **No JavaScript frameworks** — no React, no Vue, no Svelte. Vanilla JS only.
20. **No external JavaScript libraries** — no GSAP, no Framer Motion, no AOS, no ScrollMagic.
21. **No build tools** — the HTML file must work by opening it in a browser. No Vite, no Webpack, no Parcel.

### Behavioral

22. **No bouncy animations or spring physics** — all motion uses `var(--ease-standard)` (cubic-bezier). No overshoot, no elastic easing.
23. **No infinite scroll or lazy loading** — this is a single marketing page. All content is present in the initial HTML.
24. **No cookie banners or popup modals** — not in scope.
25. **No chatbot widgets or floating action buttons**.

### Copy

26. **No corporate buzzwords** — no "leverage," "synergize," "disrupt," "innovative," "cutting-edge," "world-class," "best-in-class," "next-gen," "revolutionary."
27. **No breathless startup copy** — no "We're building the future of..." or "Join the revolution."
28. **No placeholder copy** — every word on the page is specified in this document. Do not invent new copy. Do not use Lorem ipsum anywhere.

---

## Final Checklist for the Builder

Before considering this page complete, verify:

- [ ] The HTML file opens in a browser with no errors in the console.
- [ ] Google Fonts load correctly (Lora, Inter, JetBrains Mono).
- [ ] The paper grain texture is visible at 3% opacity across the entire page.
- [ ] The nav transitions from transparent to frosted on scroll past 80px.
- [ ] The hero entrance animation plays on page load with correct stagger timing.
- [ ] Every section with `data-reveal` elements animates on scroll intersection.
- [ ] The "Belong" underline accent is visible in the hero heading.
- [ ] All three pillars are separated by vertical rules (not card borders).
- [ ] The How It Works steps have a vertical connecting line between numerals.
- [ ] The testimonial section has a full-bleed `--color-surface` background.
- [ ] The CTA section has a full-bleed `--color-ink` background with inverted text.
- [ ] All buttons have hover, active, and focus-visible states.
- [ ] Tab through the entire page — every interactive element receives focus and the focus ring is visible.
- [ ] Resize to 375px width — all sections reflow correctly per the responsive spec.
- [ ] Enable "Reduce motion" in OS accessibility settings — all animations are disabled, all content is immediately visible.
- [ ] The skip link appears on first Tab press.
- [ ] No straight quotes exist anywhere in the rendered output.
- [ ] No hex colors are used in CSS outside of `:root` custom property definitions (everything uses `var()`).
- [ ] The page weighs under 50KB total (HTML + inline CSS + inline JS, excluding font downloads).
- [ ] Zero violations of the Anti-Slop Rules (Section 15).

---

*This specification is complete and self-contained. The executing agent should need zero additional context, zero design decisions, and zero copy writing. Build exactly what is described. If something is ambiguous, choose the option that is quieter, warmer, and more editorial.*
