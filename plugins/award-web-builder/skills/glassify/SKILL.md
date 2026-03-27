---
Name: glassify
name: glassify
description: >-
  Convert logo images (PNG, SVG) into glass-effect versions or place them on
  glassmorphism cards. Use when the user wants to make a logo look like it is
  made of glass, apply frosted/liquid glass material to a graphic, place a logo
  on a glass card, or generate glass-styled brand assets. Supports PNG input
  (Canvas API compositing, outputs PNG) and SVG input (native SVG filter
  injection, outputs SVG). Trigger on keywords: glassify, glass logo, logo on
  glass, glass card logo, frosted logo, glass effect logo, make it glass,
  glass material logo, glass brand asset.
Category: Frontend Design
Tier: STANDARD
Dependencies: "canvas (npm, for PNG pipeline)"
Author: mark-satterfield
Version: 1.0.0
---

# Glassify — Glass Effect Generator for Logos and Brand Assets

## Name

glassify

## Description

Converts PNG and SVG logos, lettermarks, combomarks, and icons into
glass-material versions or places them on glassmorphism card compositions.

## Features

- "Made of glass" — logo becomes translucent glass with refraction highlights
- "On glass" — logo placed on a glassmorphism card background
- "Glass on glass" — both logo and card get glass treatment
- SVG pipeline with native filter injection (no dependencies)
- PNG pipeline via Canvas API compositing
- Five presets: subtle, standard, frosted, crystal, colored
- Configurable parameters: blur, opacity, tint, highlight, shadow, refraction

---

## 1. Capabilities

**"Made of glass"** — The logo itself becomes translucent glass material with
refraction highlights, specular gloss, inner shadows, and frosted fill. The
output is a standalone asset with glass properties baked in.

**"On glass"** — The logo (unchanged) is placed on a glassmorphism card
background. The card gets the blur/tint/shadow treatment; the logo sits
on top.

**"Glass on glass"** — The logo is glassified AND placed on a glass card.
Both layers get the treatment.

---

## 2. Input Requirements

- PNG: must have transparency (alpha channel). Opaque regions become glass.
  Minimum 256x256px recommended. Larger source = better quality output.
- SVG: vector paths are preserved. Filter is applied to shape groups.
  Text elements should be converted to paths before processing.
- Output matches input format: PNG in → PNG out, SVG in → SVG out.
- For "on glass card" compositions, output is always HTML or SVG
  (card + logo together).

---

## 3. Glass Effect Parameters

All parameters have sensible defaults. Override any for creative control.

| Parameter        | Type    | Default | Range    | Description                           |
|------------------|---------|---------|----------|---------------------------------------|
| blur             | number  | 3       | 0–15     | Internal frosting intensity (px)      |
| tint             | string  | "#ffffff"| any hex  | Glass tint color                      |
| tintOpacity      | number  | 0.15    | 0–0.5    | Tint fill opacity                     |
| highlightAngle   | number  | 135     | 0–360    | Gradient highlight direction (deg)    |
| highlightOpacity | number  | 0.4     | 0–1      | Peak highlight brightness             |
| specularX        | number  | 0.3     | 0–1      | Specular dot X position (fraction)    |
| specularY        | number  | 0.25    | 0–1      | Specular dot Y position (fraction)    |
| specularRadius   | number  | 0.15    | 0–0.5    | Specular dot size (fraction of width) |
| specularOpacity  | number  | 0.5     | 0–1      | Specular dot brightness               |
| innerShadow      | number  | 4       | 0–20     | Inner shadow blur radius (px)         |
| innerShadowAlpha | number  | 0.3     | 0–1      | Inner shadow opacity                  |
| saturation       | number  | 1.2     | 0.5–2    | Color saturation multiplier           |
| edgeHighlight    | number  | 0.5     | 0–1      | Edge rim light intensity              |

### Presets

| Preset     | blur | tintOpacity | highlightOpacity | specularOpacity | Use Case              |
|------------|------|-------------|------------------|-----------------|-----------------------|
| subtle     | 2    | 0.08        | 0.25             | 0.3             | Professional, minimal |
| standard   | 3    | 0.15        | 0.4              | 0.5             | Balanced default      |
| frosted    | 8    | 0.22        | 0.3              | 0.35            | Heavy frost, diffused |
| crystal    | 1    | 0.05        | 0.55             | 0.7             | Clear glass, sharp    |
| colored    | 4    | 0.25        | 0.35             | 0.4             | Tinted brand glass    |

---

## 4. SVG Pipeline

SVG is the preferred format. Native SVG filters produce resolution-independent
glass that scales cleanly with no rasterization artifacts.

### Filter Definition

Inject this `<defs>` block into the SVG. Apply `filter="url(#glassify)"` to
the target `<g>`, `<path>`, or top-level shape group.

```xml
<defs>
  <filter id="glassify" x="-10%" y="-10%" width="120%" height="120%"
          color-interpolation-filters="sRGB">

    <!-- 1. Preserve original shape as alpha mask -->
    <feFlood flood-color="{tint}" flood-opacity="{tintOpacity}" result="tint"/>
    <feComposite in="tint" in2="SourceAlpha" operator="in" result="tintedFill"/>

    <!-- 2. Inner frosting blur (clipped to shape) -->
    <feGaussianBlur in="SourceAlpha" stdDeviation="{blur}" result="innerBlur"/>
    <feComposite in="innerBlur" in2="SourceAlpha" operator="in" result="frost"/>

    <!-- 3. Inner shadow (depth) -->
    <feOffset in="SourceAlpha" dx="2" dy="2" result="shadowOffset"/>
    <feGaussianBlur in="shadowOffset" stdDeviation="{innerShadow}" result="shadowBlur"/>
    <feFlood flood-color="#000000" flood-opacity="{innerShadowAlpha}" result="shadowColor"/>
    <feComposite in="shadowColor" in2="shadowBlur" operator="in" result="innerShadow"/>
    <feComposite in="innerShadow" in2="SourceAlpha" operator="in" result="clippedShadow"/>

    <!-- 4. Specular highlight -->
    <feSpecularLighting in="frost" surfaceScale="5" specularConstant="0.8"
                        specularExponent="20" lighting-color="#ffffff" result="specRaw">
      <fePointLight x="{specularX * width}" y="{specularY * height}" z="200"/>
    </feSpecularLighting>
    <feComposite in="specRaw" in2="SourceAlpha" operator="in" result="specular"/>

    <!-- 5. Saturation adjustment -->
    <feColorMatrix in="SourceGraphic" type="saturate" values="{saturation}"
                   result="saturated"/>
    <feComposite in="saturated" in2="SourceAlpha" operator="in" result="saturatedClipped"/>

    <!-- 6. Composite all layers -->
    <feMerge>
      <feMergeNode in="saturatedClipped"/>  <!-- base shape with saturation -->
      <feMergeNode in="tintedFill"/>        <!-- glass tint -->
      <feMergeNode in="frost"/>             <!-- frosting -->
      <feMergeNode in="clippedShadow"/>     <!-- inner shadow -->
      <feMergeNode in="specular"/>          <!-- specular highlight -->
    </feMerge>
  </filter>

  <!-- Edge highlight gradient (apply as stroke to shape group) -->
  <linearGradient id="glassify-edge" x1="0%" y1="0%"
                  x2="{cos(highlightAngle)}%" y2="{sin(highlightAngle)}%">
    <stop offset="0%" stop-color="#ffffff" stop-opacity="{edgeHighlight}"/>
    <stop offset="50%" stop-color="#ffffff" stop-opacity="0"/>
    <stop offset="100%" stop-color="#ffffff" stop-opacity="{edgeHighlight * 0.3}"/>
  </linearGradient>
</defs>
```

### Application

```xml
<!-- Wrap existing paths in a group, apply filter -->
<g filter="url(#glassify)" stroke="url(#glassify-edge)" stroke-width="1">
  <!-- original <path>, <circle>, <rect>, etc. elements here -->
</g>
```

### Implementation Steps (Agent Workflow)

1. Read source SVG file
2. Parse XML (DOMParser or xml2js)
3. Locate the root `<svg>` element, read width/height/viewBox
4. Find or create `<defs>` block
5. Generate filter XML with parameter values substituted
6. Inject filter and gradient into `<defs>`
7. Wrap all visible shape elements in a `<g>` with filter applied
8. If "on glass card" requested: wrap the entire SVG in a card SVG
   with glassmorphism rect behind it (see section 7)
9. Write output SVG

---

## 5. PNG Pipeline

Uses HTML Canvas API. Reads the alpha channel to isolate opaque regions,
composites glass layers only onto those regions.

### Implementation Steps (Agent Workflow)

1. Load PNG into an offscreen canvas
2. Extract ImageData, build alpha mask (pixels where alpha > 0)
3. Create output canvas at same dimensions

Layer compositing order (bottom to top):

```
Layer 1: Base shape with saturation adjustment
  - Draw source image
  - Apply globalCompositeOperation + feColorMatrix equivalent via
    canvas filter: `ctx.filter = 'saturate({saturation})'`

Layer 2: Glass tint fill
  - Fill canvas with tint color at tintOpacity
  - Clip to alpha mask using 'destination-in' composite

Layer 3: Inner frosting
  - Draw source onto temp canvas with `ctx.filter = 'blur({blur}px)'`
  - Composite with alpha mask
  - Blend onto output at reduced opacity

Layer 4: Inner shadow
  - Set ctx.shadowColor, ctx.shadowBlur, ctx.shadowOffsetX/Y
  - Draw alpha mask shape inward
  - Clip to original alpha

Layer 5: Gradient highlight
  - Create linear gradient at highlightAngle
  - From rgba(255,255,255,highlightOpacity) to transparent
  - Fill, clip to alpha mask

Layer 6: Specular dot
  - Create radial gradient at (specularX, specularY)
  - White center fading to transparent
  - Fill, clip to alpha mask

Layer 7: Edge highlight
  - Stroke the alpha contour with semi-transparent white
  - 1px stroke, edgeHighlight opacity
```

4. Export canvas as PNG via `canvas.toBuffer('image/png')` (Node) or
   `canvas.toDataURL('image/png')` (browser)

### Node.js Dependencies

```bash
npm install canvas   # node-canvas for server-side rendering
# or use sharp for initial load + canvas for compositing
```

### Browser Alternative

For browser-based execution (artifacts, client-side tools), use
OffscreenCanvas or standard `<canvas>` element. No npm dependencies
required.

---

## 6. Glass Card Composition

When "on glass" or "glass on glass" is requested, generate a card
background with glassmorphism properties and place the logo on it.

### SVG Card

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="{cardWidth}" height="{cardHeight}"
     viewBox="0 0 {cardWidth} {cardHeight}">
  <defs>
    <filter id="card-frost" x="-5%" y="-5%" width="110%" height="110%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="20" result="blur"/>
    </filter>

    <clipPath id="card-clip">
      <rect width="{cardWidth}" height="{cardHeight}" rx="20" ry="20"/>
    </clipPath>
  </defs>

  <!-- Card background -->
  <g clip-path="url(#card-clip)">
    <!-- Frosted background (consumer provides background image or gradient) -->
    <rect width="100%" height="100%" fill="rgba(255,255,255,0.15)"
          filter="url(#card-frost)"/>

    <!-- Glass tint -->
    <rect width="100%" height="100%" fill="rgba(255,255,255,0.12)"/>

    <!-- Top edge highlight -->
    <line x1="{cardWidth*0.1}" y1="0.5" x2="{cardWidth*0.9}" y2="0.5"
          stroke="rgba(255,255,255,0.4)" stroke-width="1"/>

    <!-- Inner highlight gradient -->
    <rect width="100%" height="50%" fill="url(#card-highlight)" opacity="0.1"/>
  </g>

  <!-- Border -->
  <rect width="{cardWidth}" height="{cardHeight}" rx="20" ry="20"
        fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="1"/>

  <!-- Logo centered -->
  <g transform="translate({centerX},{centerY})">
    <!-- insert logo SVG content or PNG <image> here -->
  </g>
</svg>
```

### HTML Card (for web use)

```html
<div class="glass glass--prominent" style="
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  width: {cardWidth}px;
  height: {cardHeight}px;
">
  <img src="{logoPath}" alt="{logoAlt}" style="
    max-width: 70%;
    max-height: 70%;
    object-fit: contain;
  "/>
</div>
```

Requires `liquid-glass.css` from the Liquid Glass Design System skill.

---

## 7. Card Sizing Rules

| Logo Type    | Card Aspect | Logo Scale | Padding |
|--------------|-------------|------------|---------|
| Lettermark   | 1:1         | 60%        | 20%     |
| Logomark     | 1:1         | 65%        | 17.5%   |
| Combomark    | 16:9        | 55%        | 22.5%   |
| Wordmark     | 3:1         | 50%        | 25%     |
| Icon/Favicon | 1:1         | 70%        | 15%     |

Logo Scale = percentage of card dimension the logo occupies.
Padding = remaining space distributed evenly around logo.

---

## 8. Agent Workflow Summary

When the user provides a PNG or SVG and requests a glass effect:

1. **Identify input format** — check file extension and content
2. **Identify request type** — "made of glass", "on glass card", or both
3. **Select preset or accept custom parameters**
4. **Route to pipeline:**
   - SVG → Section 4 (filter injection)
   - PNG → Section 5 (canvas compositing)
5. **If card requested** → Section 6 (card composition)
6. **Generate output file(s)**
7. **Present to user** — output file + parameter summary

### Output Files

| Request              | SVG Input Output        | PNG Input Output       |
|----------------------|-------------------------|------------------------|
| Made of glass        | `{name}-glass.svg`      | `{name}-glass.png`     |
| On glass card        | `{name}-card.svg`       | `{name}-card.html`     |
| Glass on glass       | `{name}-glass-card.svg` | `{name}-glass-card.html`|

---

## 9. Constraints

- Source PNGs without alpha channel cannot be processed. The agent MUST
  check for transparency and reject fully opaque PNGs with guidance to
  provide a version with transparent background.
- SVG text elements should be converted to `<path>` before processing.
  `feSpecularLighting` and displacement do not render well on `<text>`.
- Very complex SVGs (>500 path elements) may produce slow filter rendering.
  Consider simplifying or applying the filter to a grouped `<g>` wrapper
  rather than individual elements.
- PNG output quality depends on source resolution. Upscaling a 32x32 favicon
  to glass will look bad. Recommend minimum 256x256 source.
- Canvas `blur()` filter is not supported in all environments. Fallback:
  use StackBlur.js or pre-blur via sharp before canvas compositing.
- The glass effect is purely visual / decorative. It does not modify the
  semantic content of the logo. Alt text and accessibility labels remain
  the responsibility of the consumer.

---

## 10. Dependencies

### SVG Pipeline
- No runtime dependencies. Pure XML manipulation.
- Parser: DOMParser (browser), xml2js or fast-xml-parser (Node)

### PNG Pipeline (Node.js)
- `canvas` (node-canvas) — Canvas API for server-side rendering
- `sharp` (optional) — fast image load/resize/saturation
- `stackblur-canvas` (optional fallback) — Gaussian blur polyfill

### PNG Pipeline (Browser)
- No dependencies. Native Canvas API + OffscreenCanvas.

### Glass Card (HTML)
- `liquid-glass.css` from the Liquid Glass Design System skill

---

## Usage

Invoke this skill when converting a logo or brand asset into a glass-effect version.
Provide the input image (PNG or SVG) and specify the desired mode: "made of glass",
"on glass", or "glass on glass". Optionally select a preset (subtle, standard, frosted,
crystal, colored) or provide custom parameters.

## Examples

- "Glassify our logo" — applies the standard preset to make the logo look like glass material
- "Put the logo on a glass card" — places the logo on a glassmorphism card background
- "Create a frosted glass version of this SVG" — uses the SVG pipeline with the frosted preset
