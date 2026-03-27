---
name: liquid-glass
description: >-
  Implement Apple-inspired Liquid Glass and Glassmorphism design systems.
  Use when building translucent UI components, frosted glass cards, navigation
  bars, modals, or any interface requiring depth through transparency, blur,
  refraction, and dynamic light behavior. Covers CSS design tokens, React
  component patterns, SVG distortion filters, WebGL refraction via liquidGL,
  accessibility constraints, performance optimization, and anti-patterns.
  Trigger on keywords: liquid glass, glassmorphism, frosted glass, translucent
  UI, glass card, glass effect, backdrop blur, refraction, glass material,
  glass design system, liquidGL, WebGL glass.
---

# Liquid Glass Design System

A comprehensive design system for implementing Apple-style Liquid Glass and
Glassmorphism effects across web platforms. Derived from Apple's WWDC 2025
Liquid Glass introduction, Microsoft Fluent Design Acrylic materials, and
established glassmorphism patterns refined since 2020.

---

## 1. Design Philosophy

Liquid Glass is a **digital meta-material** that dynamically bends and shapes
light while moving fluidly. It is NOT static frosted blur — it is an
interactive surface that responds to content, light, and user intent.

### Core Principles

**Depth through translucency.** Glass elements reveal what is underneath,
establishing spatial hierarchy between foreground controls and background
content. The user perceives layers suspended in space.

**Light as material.** Elements refract, reflect, and respond to light
sources. Edges catch highlights. Shadows provide separation. Illumination
adapts to context.

**Restraint over decoration.** Glass is most effective on the navigation
layer — toolbars, tab bars, modals, floating action buttons, and contextual
menus. It is NOT a background treatment. Never apply glass to everything.

**Content supremacy.** The glass surface exists to serve content, not to
compete with it. If the effect reduces legibility or distracts from the
task, reduce or remove it.

---

## 2. Three-Layer Composition Model

Apple describes Liquid Glass as composed of three distinct layers. All
implementations MUST respect this model.

### Layer 1: Highlight
Light casting and movement. Simulated via gradient borders, edge highlights,
and specular reflections that shift based on interaction or scroll position.
CSS: border with semi-transparent white gradients, `::before` pseudo-element
with inset box-shadows.

### Layer 2: Shadow
Depth separation between foreground glass and background content. Provides
the "floating" perception. CSS: `box-shadow` with translucent dark values,
often layered (outer shadow + subtle inner shadow).

### Layer 3: Illumination
The flexible optical properties of the material itself — blur, saturation,
tint, and refraction. CSS: `backdrop-filter` (blur + saturate), semi-transparent
`background-color`, optional SVG displacement filters for refraction.

---

## 3. Design Tokens

All glass properties MUST be tokenized for consistency across components.
Store in CSS custom properties at `:root` or in a design token JSON file.

### Token Definitions

```css
:root {
  /* --- Glass Material --- */
  --glass-blur-light:       12px;
  --glass-blur-medium:      20px;
  --glass-blur-heavy:       30px;

  --glass-bg-light:         rgba(255, 255, 255, 0.12);
  --glass-bg-medium:        rgba(255, 255, 255, 0.18);
  --glass-bg-heavy:         rgba(255, 255, 255, 0.25);

  --glass-bg-dark-light:    rgba(0, 0, 0, 0.15);
  --glass-bg-dark-medium:   rgba(0, 0, 0, 0.25);
  --glass-bg-dark-heavy:    rgba(0, 0, 0, 0.35);

  --glass-saturation:       180%;
  --glass-brightness:       1.05;

  /* --- Borders / Highlight Layer --- */
  --glass-border-light:     1px solid rgba(255, 255, 255, 0.25);
  --glass-border-prominent: 1px solid rgba(255, 255, 255, 0.45);
  --glass-border-dark:      1px solid rgba(255, 255, 255, 0.08);

  /* --- Shadow Layer --- */
  --glass-shadow-sm:        0 2px 8px rgba(0, 0, 0, 0.12);
  --glass-shadow-md:        0 8px 32px rgba(31, 38, 135, 0.20);
  --glass-shadow-lg:        0 16px 48px rgba(0, 0, 0, 0.25);
  --glass-shadow-inset:     inset 0 0 20px -5px rgba(255, 255, 255, 0.4);

  /* --- Shape --- */
  --glass-radius-sm:        12px;
  --glass-radius-md:        20px;
  --glass-radius-lg:        28px;
  --glass-radius-pill:      999px;

  /* --- Tint Colors --- */
  --glass-tint-primary:     rgba(0, 123, 255, 0.15);
  --glass-tint-success:     rgba(52, 199, 89, 0.15);
  --glass-tint-warning:     rgba(255, 159, 10, 0.15);
  --glass-tint-danger:      rgba(255, 69, 58, 0.15);
  --glass-tint-neutral:     rgba(142, 142, 147, 0.12);

  /* --- Motion --- */
  --glass-transition:       all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  --glass-transition-fast:  all 0.15s cubic-bezier(0.4, 0, 0.2, 1);

  /* --- Accessibility Overrides --- */
  --glass-a11y-fallback-bg: rgba(255, 255, 255, 0.92);
  --glass-a11y-fallback-bg-dark: rgba(28, 28, 30, 0.95);
}
```

### Token JSON (for Style Dictionary / Tokens Studio)

```json
{
  "glass": {
    "blur": {
      "light":  { "value": "12px" },
      "medium": { "value": "20px" },
      "heavy":  { "value": "30px" }
    },
    "bg": {
      "light":  { "value": "rgba(255, 255, 255, 0.12)" },
      "medium": { "value": "rgba(255, 255, 255, 0.18)" },
      "heavy":  { "value": "rgba(255, 255, 255, 0.25)" }
    },
    "radius": {
      "sm": { "value": "12px" },
      "md": { "value": "20px" },
      "lg": { "value": "28px" }
    },
    "saturation": { "value": "180%" }
  }
}
```

---

## 4. CSS Implementation

### Base Glass Class

```css
.glass {
  position: relative;
  background: var(--glass-bg-medium);
  backdrop-filter: blur(var(--glass-blur-medium)) saturate(var(--glass-saturation));
  -webkit-backdrop-filter: blur(var(--glass-blur-medium)) saturate(var(--glass-saturation));
  border: var(--glass-border-light);
  border-radius: var(--glass-radius-md);
  box-shadow: var(--glass-shadow-md);
  transition: var(--glass-transition);
  isolation: isolate;
}
```

### Highlight Layer (::before)

```css
.glass::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 0;
  border-radius: inherit;
  box-shadow: var(--glass-shadow-inset);
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.12) 0%,
    transparent 50%
  );
  pointer-events: none;
}
```

### Top Edge Highlight

```css
.glass::after {
  content: '';
  position: absolute;
  top: 0;
  left: 10%;
  right: 10%;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.4),
    transparent
  );
  pointer-events: none;
}
```

### Component Variants

```css
/* Frosted — high blur, subtle tint */
.glass--frosted {
  --glass-bg-medium: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(var(--glass-blur-heavy)) saturate(var(--glass-saturation));
  -webkit-backdrop-filter: blur(var(--glass-blur-heavy)) saturate(var(--glass-saturation));
}

/* Translucent — low blur, strong background visibility */
.glass--translucent {
  --glass-bg-medium: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(var(--glass-blur-light)) saturate(120%);
  -webkit-backdrop-filter: blur(var(--glass-blur-light)) saturate(120%);
}

/* Prominent — higher opacity, thick border, strong shadow */
.glass--prominent {
  background: var(--glass-bg-heavy);
  border: var(--glass-border-prominent);
  box-shadow: var(--glass-shadow-lg), var(--glass-shadow-inset);
}

/* Tinted — brand color overlay */
.glass--tinted {
  background:
    linear-gradient(135deg, var(--glass-tint-primary), transparent),
    var(--glass-bg-medium);
}

/* Dark mode */
.glass--dark {
  background: var(--glass-bg-dark-medium);
  border: var(--glass-border-dark);
}
```

### Interactive States

```css
.glass:hover {
  background: rgba(255, 255, 255, 0.22);
  box-shadow: var(--glass-shadow-lg);
  transform: translateY(-1px);
}

.glass:active {
  transform: translateY(0) scale(0.98);
  box-shadow: var(--glass-shadow-sm);
  transition: var(--glass-transition-fast);
}

.glass:focus-visible {
  outline: 2px solid rgba(0, 123, 255, 0.6);
  outline-offset: 2px;
}
```

### Progressive Enhancement

```css
/* Fallback for browsers without backdrop-filter */
.glass {
  background: var(--glass-a11y-fallback-bg);
}

@supports (backdrop-filter: blur(1px)) {
  .glass {
    background: var(--glass-bg-medium);
    backdrop-filter: blur(var(--glass-blur-medium)) saturate(var(--glass-saturation));
    -webkit-backdrop-filter: blur(var(--glass-blur-medium)) saturate(var(--glass-saturation));
  }
}
```

---

## 5. SVG Distortion Filter (Refraction)

True Liquid Glass uses refraction (light bending at edges), not just blur.
CSS has no native distortion property. Use SVG `feDisplacementMap` filters
applied via `backdrop-filter: url(#filter-id)`.

**Browser support: Chromium-based browsers only.** Safari and Firefox do NOT
reliably support SVG filters inside `backdrop-filter`. Always provide a
non-distortion fallback.

### SVG Filter Definition

```html
<svg xmlns="http://www.w3.org/2000/svg" width="0" height="0"
     style="position:absolute; overflow:hidden">
  <defs>
    <filter id="glass-refraction" x="0%" y="0%" width="100%" height="100%">
      <!-- Noise texture for organic distortion -->
      <feTurbulence
        type="fractalNoise"
        baseFrequency="0.008 0.008"
        numOctaves="2"
        seed="42"
        result="noise"
      />
      <!-- Soften the noise -->
      <feGaussianBlur
        in="noise"
        stdDeviation="2"
        result="softNoise"
      />
      <!-- Apply displacement -->
      <feDisplacementMap
        in="SourceGraphic"
        in2="softNoise"
        scale="60"
        xChannelSelector="R"
        yChannelSelector="G"
      />
    </filter>
  </defs>
</svg>
```

### Applying to Glass Element

```css
.glass--refracted::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  border-radius: inherit;
  backdrop-filter: blur(8px) url(#glass-refraction);
  -webkit-backdrop-filter: blur(8px);  /* Safari fallback: blur only */
}
```

### Tuning Displacement

| Parameter       | Low (subtle) | Medium | High (dramatic) |
|-----------------|-------------|--------|-----------------|
| baseFrequency   | 0.005       | 0.008  | 0.015           |
| numOctaves      | 1           | 2      | 3               |
| stdDeviation    | 3           | 2      | 1               |
| scale           | 30          | 60     | 100             |

---

## 6. WebGL Refraction — liquidGL

When you need real-time optical refraction with full cross-browser support
(including Safari and Firefox), the CSS and SVG approaches in sections 4-5
are insufficient. `liquidGL` uses a WebGL shader pipeline with `html2canvas`
snapshots to produce actual light bending, bevel depth, specular highlights,
and magnification — none of which are achievable in pure CSS.

**Use liquidGL when:** you need refraction (not just blur), you need it to
work in Safari/Firefox, you need dynamic content refraction (video, live
text animations), or you need bevel/specular/tilt interactions.

**Do NOT use liquidGL when:** simple frosted glassmorphism (blur + tint) is
sufficient, or you cannot accept the `html2canvas` dependency.

### Dependencies

```html
<!-- html2canvas — DOM snapshotter (required) -->
<script
  src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"
  defer
></script>

<!-- liquidGL library -->
<script src="/scripts/liquidGL.js" defer></script>
```

### HTML Structure

The target element receives the glass effect. Child content sits on top.

```html
<div class="liquidGL">
  <div class="content" style="position:relative; z-index:3;">
    <h2>Glass Content</h2>
    <p>Visible above the refraction layer.</p>
  </div>
</div>
```

Target element MUST have a high `z-index` to sit over page content. Content
inside the target needs `z-index: 3` or higher to sit above the lens.

### Initialization

```js
document.addEventListener("DOMContentLoaded", () => {
  const glassEffect = liquidGL({
    snapshot:    "body",       // DOM area to snapshot for refraction
    target:      ".liquidGL",  // CSS selector for glass elements
    resolution:  2.0,          // Snapshot quality (0.1–3.0)
    refraction:  0.01,         // Base refraction strength (0–1)
    bevelDepth:  0.08,         // Edge bevel intensity (0–1)
    bevelWidth:  0.15,         // Bevel zone width as fraction of element (0–1)
    frost:       0,            // Blur radius in px. 0 = crystal clear
    shadow:      true,         // Drop-shadow under pane
    specular:    true,         // Animated specular highlights (more GPU)
    reveal:      "fade",       // "fade" or "none"
    tilt:        false,        // Hover tilt interaction
    tiltFactor:  5,            // Tilt depth in degrees (0–25)
    magnify:     1,            // Lens magnification (0.001–3.0)
    on: {
      init(instance) {
        console.log("liquidGL ready!", instance)
      },
    },
  })
})
```

### Dynamic Content Refraction

Register elements that animate or change so liquidGL monitors and
re-renders the texture. Videos are detected automatically.

```js
// Single element
liquidGL.registerDynamic(".my-animated-element")

// Array of elements (e.g., GSAP SplitText lines)
liquidGL.registerDynamic(splitText.lines)
```

### Smooth Scroll Integration

```js
const { lenis, locomotiveScroll } = liquidGL.syncWith()
```

Auto-detects Lenis or Locomotive Scroll and syncs the render loop.

### Presets

| Name        | refraction | bevelDepth | bevelWidth | frost | shadow | specular | Use Case                        |
|-------------|-----------|------------|------------|-------|--------|----------|---------------------------------|
| Default     | 0         | 0.052      | 0.211      | 2     | true   | true     | Balanced general purpose        |
| Alien       | 0.073     | 0.2        | 0.156      | 2     | true   | false    | Strong refraction, sci-fi look  |
| Pulse       | 0.03      | 0          | 0.273      | 0     | false  | false    | Flat pane, wide bevel, UI pulse |
| Frost       | 0         | 0.035      | 0.119      | 0.9   | true   | true     | Privacy glass, soft diffusion   |
| Edge        | 0.047     | 0.136      | 0.076      | 2     | true   | false    | Thin bevel, bright rim          |

### Parameters Reference

| Option       | Type     | Default       | Description                                   |
|--------------|----------|---------------|-----------------------------------------------|
| target       | string   | ".liquidGL"   | Required. CSS selector for glass elements     |
| snapshot     | string   | "body"        | Element to snapshot for refraction texture     |
| resolution   | number   | 2.0           | Snapshot quality (0.1–3.0)                    |
| refraction   | number   | 0.01          | Base refraction offset (0–1)                  |
| bevelDepth   | number   | 0.08          | Edge bevel refraction intensity (0–1)         |
| bevelWidth   | number   | 0.15          | Bevel zone as fraction of shortest side (0–1) |
| frost        | number   | 0             | Blur radius in px. 0 = clear glass            |
| shadow       | boolean  | true          | Drop-shadow under pane                        |
| specular     | boolean  | true          | Animated specular highlights                  |
| reveal       | string   | "fade"        | "fade" or "none"                              |
| tilt         | boolean  | false         | 3D tilt on cursor movement                    |
| tiltFactor   | number   | 5             | Tilt depth in degrees (0–25)                  |
| magnify      | number   | 1             | Lens magnification (0.001–3.0)                |
| on.init      | function | —             | Callback after first render                   |

### Constraints and Notes

- All target elements MUST share the same `z-index` (shared canvas optimization).
- `shadow` renders at `z-index - 2`, tilt helper at `z-index - 1`. Leave room.
- `fixed` position elements are ignored (html2canvas/mobile browser bug safety net).
- Exclude elements from snapshot with `data-liquid-ignore` attribute.
- Images inside the target must have permissive CORS headers.
- Very long pages can exceed GPU texture limits. Scope `snapshot` to a
  smaller container or reduce `resolution`.
- CSS animations inside the glass are NOT refracted in real-time. Use
  GSAP or JS-driven animations with `registerDynamic()` instead.
- Safari can be unstable when glass elements exceed 50% of viewport
  width or height. Test on target devices.
- Tested up to 30 elements per page with no WebGL context exhaustion
  (single shared canvas).

### Browser Support

All WebGL-enabled browsers on desktop, tablet, and mobile. Falls back to
CSS `backdrop-filter` frosting on devices without WebGL.

---

## 7. React Implementation

### Using liquid-glass-react (npm)

```bash
npm install liquid-glass-react
```

```tsx
import LiquidGlass from 'liquid-glass-react'

// Card
<LiquidGlass
  displacementScale={70}
  blurAmount={0.0625}
  saturation={140}
  aberrationIntensity={2}
  elasticity={0.15}
  cornerRadius={20}
  padding="24px"
>
  <h2>Card Title</h2>
  <p>Card content with full refraction.</p>
</LiquidGlass>

// Button
<LiquidGlass
  displacementScale={64}
  blurAmount={0.1}
  saturation={130}
  aberrationIntensity={2}
  elasticity={0.35}
  cornerRadius={100}
  padding="8px 24px"
  onClick={() => handleClick()}
>
  <span className="text-white font-medium">Action</span>
</LiquidGlass>
```

#### Props Reference (liquid-glass-react)

| Prop                 | Type     | Default    | Description                                    |
|----------------------|----------|------------|------------------------------------------------|
| displacementScale    | number   | 70         | Displacement intensity (0-200)                 |
| blurAmount           | number   | 0.0625     | Blur/frosting level (0-1)                      |
| saturation           | number   | 140        | Color saturation of glass                      |
| aberrationIntensity  | number   | 2          | Chromatic aberration intensity                 |
| elasticity           | number   | 0.15       | Liquid elastic feel (0=rigid, higher=elastic)  |
| cornerRadius         | number   | 999        | Border radius in px                            |
| overLight            | boolean  | false      | Optimize for light backgrounds                 |
| mode                 | string   | "standard" | "standard" / "polar" / "prominent" / "shader" |
| mouseContainer       | RefObj   | null       | Parent element for mouse tracking              |

**Browser note:** Safari and Firefox only partially support the displacement
effect. The visual will degrade to blur-only in those browsers.

### Using @developer-hub/liquid-glass (npm)

```bash
npm install @developer-hub/liquid-glass
```

```tsx
import { GlassCard } from '@developer-hub/liquid-glass'

<GlassCard
  displacementScale={100}
  blurAmount={0.01}
  cornerRadius={20}
  shadowMode={false}
>
  <div className="p-6">
    <h2>Content</h2>
  </div>
</GlassCard>
```

Set `shadowMode={true}` for light backgrounds.

### Pure CSS/React Component (No Library)

When library dependencies are not desired, implement the three-layer model
directly:

```tsx
import React from 'react'

interface GlassContainerProps {
  children: React.ReactNode
  variant?: 'frosted' | 'translucent' | 'prominent' | 'tinted'
  tintColor?: string
  blur?: 'light' | 'medium' | 'heavy'
  className?: string
  style?: React.CSSProperties
  as?: React.ElementType
}

export function GlassContainer({
  children,
  variant = 'frosted',
  tintColor,
  blur = 'medium',
  className = '',
  style,
  as: Tag = 'div',
}: GlassContainerProps) {
  const variantClass = variant ? `glass--${variant}` : ''
  const blurClass = `glass--blur-${blur}`

  return (
    <Tag
      className={`glass ${variantClass} ${blurClass} ${className}`}
      style={{
        ...(tintColor ? { '--glass-tint-primary': tintColor } as React.CSSProperties : {}),
        ...style,
      }}
    >
      {children}
    </Tag>
  )
}
```

---

## 8. Tailwind CSS Utility Classes

For projects using Tailwind, define glass utilities via plugin or @layer:

```css
@layer utilities {
  .glass-surface {
    @apply relative backdrop-blur-lg backdrop-saturate-[180%]
           bg-white/[0.15] border border-white/20
           rounded-2xl shadow-lg;
    isolation: isolate;
  }

  .glass-surface-dark {
    @apply relative backdrop-blur-lg backdrop-saturate-[180%]
           bg-black/[0.25] border border-white/[0.08]
           rounded-2xl shadow-lg;
    isolation: isolate;
  }

  .glass-surface-prominent {
    @apply relative backdrop-blur-xl backdrop-saturate-[180%]
           bg-white/25 border border-white/40
           rounded-2xl shadow-xl;
    isolation: isolate;
  }
}
```

---

## 9. Accessibility — MANDATORY

Glass effects introduce variable contrast that can destroy readability.
Every implementation MUST follow these rules.

### Contrast Requirements

- All text on glass surfaces MUST meet WCAG 2.2 AA contrast ratios:
  4.5:1 for normal text, 3:1 for large text (18px+ or 14px+ bold).
- Test contrast against WORST-CASE backgrounds, not just the demo gradient.
- Use neutral text colors (white, near-white, near-black) on glass.
  Colored text on glass rarely passes contrast.
- Apply a text-shadow or slight background tint behind text to guarantee
  readability: `text-shadow: 0 1px 3px rgba(0,0,0,0.3);`

### Reduced Transparency

Respect `prefers-reduced-transparency`. Replace glass with solid fills:

```css
@media (prefers-reduced-transparency: reduce) {
  .glass {
    background: var(--glass-a11y-fallback-bg);
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    border: 1px solid rgba(0, 0, 0, 0.12);
  }
}
```

### Reduced Motion

Respect `prefers-reduced-motion`. Disable animated glass transitions:

```css
@media (prefers-reduced-motion: reduce) {
  .glass,
  .glass::before,
  .glass::after {
    transition: none;
    animation: none;
  }
}
```

### Focus Indicators

Glass elements that are interactive MUST have visible focus rings that do
not rely on the glass effect for visibility:

```css
.glass:focus-visible {
  outline: 2px solid #007AFF;
  outline-offset: 2px;
}
```

### Screen Reader Considerations

Glass is purely decorative. Do not encode glass state in ARIA. Ensure all
interactive glass elements have proper `role`, `aria-label`, and keyboard
support independent of visual presentation.

---

## 10. Performance Optimization

### Rules

1. **Maximum 2 blur layers per viewport.** Each `backdrop-filter` composites
   a separate GPU texture. Three or more stacked blurs cause frame drops on
   mid-range devices.

2. **Never nest glass inside glass.** Apple's own guidelines say: avoid
   glass on glass. Nested backdrop-filters compound GPU cost and produce
   visual noise.

3. **Use `will-change: backdrop-filter` on elements that animate.** Remove
   it when animation completes to release GPU memory.

4. **Constrain glass to small, floating elements.** Navigation bars, cards,
   modals, FABs, tooltips. Never full-screen glass backgrounds.

5. **Cache blur textures where possible.** For static backgrounds, pre-render
   the blurred version as an image rather than computing it live.

6. **Scale blur radius to device capability.** Detect low-end devices and
   reduce blur:

```js
const isLowEnd = navigator.hardwareConcurrency <= 4
const blurAmount = isLowEnd ? '8px' : '20px'
```

7. **Use `renderToHardwareTextureAndroid={true}`** in React Native blur views.

8. **Debounce mouse-tracking** on interactive glass to ~16ms (one frame).

### Performance Budget

| Metric              | Target    |
|---------------------|-----------|
| Glass elements/view | <= 4      |
| Blur layers stacked | <= 2      |
| Frame rate          | >= 55 FPS |
| SVG filter elements | <= 1      |
| liquidGL instances  | <= 30 (shared canvas) |

---

## 11. Anti-Patterns — NEVER

- **Glass on glass.** Never nest translucent elements inside other translucent
  elements. Produces unreadable, jittery, GPU-expensive results.

- **Full-screen glass backgrounds.** Glass is for floating elements, not page
  backgrounds. A full-screen blur has no content to separate from.

- **Low blur with busy backgrounds.** If background elements remain
  distinguishable through the glass, the user's attention splits between
  foreground and background. More blur is always better than less.

- **Glass without contrast testing.** Never ship glass UI without testing
  text contrast against multiple background scenarios.

- **Animated blur radius.** Continuously animating the blur value causes
  constant GPU recompositing. Animate opacity, transform, or tint instead.

- **Ignoring `prefers-reduced-transparency`.** This is not optional.

- **Using glass on ALL interactive controls.** Buttons, toggles, and sliders
  need clear affordances. Glass reduces mechanical clarity. Use glass
  sparingly on action elements and ensure hover/active/focus states are
  unambiguous.

- **Displacement without fallback.** SVG displacement filters only work in
  Chromium. Always provide a blur-only fallback.

---

## 12. Component Catalog

Recommended glass application points and configurations:

### Navigation Bar / Header
- Variant: frosted (heavy blur)
- Fixed/sticky position
- Full width, height 48-64px
- Blur: 20-30px
- Background: rgba(255,255,255,0.12)

### Floating Card
- Variant: prominent
- Blur: 20px
- Corner radius: 20px
- Shadow: md or lg
- Max width constrained

### Modal / Dialog
- Variant: frosted (heavy blur)
- Blur: 30px
- Overlay behind modal: solid rgba(0,0,0,0.4) — NOT glass
- Corner radius: 28px

### Tab Bar
- Variant: frosted
- Bottom-fixed
- Blur: 20px
- Icons: white or system tint, 24px minimum touch target

### Tooltip / Popover
- Variant: translucent
- Blur: 12px
- Corner radius: 12px
- Shadow: sm
- Arrow/caret: solid color matching tint, not glass

### Floating Action Button
- Variant: prominent
- Blur: 16px
- Corner radius: pill (999px)
- Min size: 56x56px touch target

### Contextual Menu
- Variant: frosted (heavy blur)
- Blur: 30px (accounts for any possible background)
- Border: prominent
- Items: 44px minimum height

---

## 13. Dark Mode Adaptation

Glass in dark mode requires different token values. Light text on dark
translucent surfaces demands careful balance:

```css
@media (prefers-color-scheme: dark) {
  :root {
    --glass-bg-medium:        rgba(255, 255, 255, 0.06);
    --glass-bg-heavy:         rgba(255, 255, 255, 0.10);
    --glass-border-light:     1px solid rgba(255, 255, 255, 0.10);
    --glass-border-prominent: 1px solid rgba(255, 255, 255, 0.18);
    --glass-shadow-md:        0 8px 32px rgba(0, 0, 0, 0.45);
    --glass-shadow-inset:     inset 0 0 20px -5px rgba(255, 255, 255, 0.08);
    --glass-a11y-fallback-bg: rgba(28, 28, 30, 0.95);
  }
}
```

---

## 14. Browser Compatibility

| Feature             | Chrome 76+ | Safari 13+ | Firefox 72+ | Edge 79+ |
|---------------------|-----------|------------|-------------|----------|
| backdrop-filter     | Full      | Full       | Partial*    | Full     |
| -webkit- prefix     | No        | Required   | No          | No       |
| SVG in backdrop     | Full      | No         | No          | Full     |
| feDisplacementMap   | Full      | Partial    | Partial     | Full     |
| WebGL (liquidGL)    | Full      | Full**     | Full        | Full     |

*Firefox: backdrop-filter requires `layout.css.backdrop-filter.enabled` flag
in some versions. It has known bugs with `position: sticky` ancestors that
have `overflow` + `border-radius`.

**Safari can be unstable with liquidGL when glass elements exceed 50% of
viewport width or height.

**Always include `-webkit-backdrop-filter` alongside `backdrop-filter`.**

**Always provide `@supports` fallbacks.**

---

## 15. References

- Apple WWDC 2025 Liquid Glass Introduction
- Apple Developer: Introduction to Liquid Glass
  (developer.apple.com/documentation/technologyoverviews/liquid-glass)
- Apple Developer: Adopting Liquid Glass
  (developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass)
- Microsoft Fluent Design: Acrylic Material
  (fluent2.microsoft.design/material)
- NN/g: Glassmorphism Definition and Best Practices
  (nngroup.com/articles/glassmorphism)
- CSS-Tricks: Getting Clarity on Apple's Liquid Glass
- liquid-glass-react (npm): github.com/rdev/liquid-glass-react
- @developer-hub/liquid-glass (npm): liquid-glass-js.com
- liquidGL (WebGL): github.com/naughtyduk/liquidGL
- Josh W. Comeau: Next-level frosted glass with backdrop-filter
