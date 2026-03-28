# Design Styles Reference

A unified catalog of web design styles the agent can work in. Each entry includes a description, key characteristics, machine-readable design tokens and component manifests, visual effects, recommended stack, bundle considerations, and representative repos. The agent should be able to work in any of these styles based on user preference — not default to any single one.

---

## 1. Material / Professional

Enterprise-grade, card/grid system, strong theming and accessibility.

**Characteristics:** Elevation via shadow, consistent spacing scale, color theming with primary/secondary/error surfaces, ripple interactions, dense and comfortable density modes.

**Representative repo:** mui/material-ui

**Manifest:**

```json
{
  "style": "Material",
  "description": "Enterprise, card/grid system with strong theming and accessibility",
  "repo": "https://github.com/mui/material-ui",
  "license": "MIT",
  "designTokens": {
    "colors": ["primary","secondary","error","warning","info","success","background","surface"],
    "typography": ["fontFamily","h1","h2","body1","caption"],
    "spacing": ["0","4","8","16","24","32"],
    "radii": ["0","4","8"],
    "elevation": ["0","1","2","3","4","8","16"]
  },
  "coreComponents": [
    {"name":"Button","role":"atomic","props":["variant","size","color","disabled"],"defaultStyles":"css-in-js","exampleImport":"import Button from '@mui/material/Button';","notes":"supports keyboard focus, aria-labels"},
    {"name":"Card","role":"composite","props":["elevation","variant"],"defaultStyles":"css-in-js","exampleImport":"import Card from '@mui/material/Card';","notes":"layout primitives for media and actions"},
    {"name":"Table","role":"composite","props":["columns","data","pagination"],"defaultStyles":"css-in-js","exampleImport":"import Table from '@mui/material/Table';","notes":"rich features via subcomponents"}
  ],
  "visualEffects": ["elevation","ripple"],
  "recommendedStack": ["React","Vite/Next.js","emotion or styled-components","TypeScript"],
  "bundleConsiderations": "Tree-shakeable but CSS-in-JS runtime cost; prefer selective imports",
  "exampleUsageSnippet": "<Button variant='contained' color='primary'>Save</Button>"
}
```

---

## 2. Ant Design / Enterprise

Comprehensive enterprise components, i18n, tables, forms.

**Characteristics:** Data-dense layouts, structured form systems, table-heavy interfaces, internationalization-ready, blue primary palette by default but fully themeable.

**Representative repo:** ant-design/ant-design

**Manifest:**

```json
{
  "style": "Ant Design",
  "description": "Comprehensive enterprise components for forms, tables, and i18n",
  "repo": "https://github.com/ant-design/ant-design",
  "license": "MIT",
  "designTokens": {
    "colors": ["primary","success","warning","error","info"],
    "typography": ["heading","body"],
    "spacing": ["4","8","16","24"],
    "radii": ["2","4"],
    "elevation": []
  },
  "coreComponents": [
    {"name":"Form","role":"composite","props":["onFinish","initialValues"],"defaultStyles":"less/css","exampleImport":"import { Form } from 'antd';","notes":"rich validation and layout features"},
    {"name":"Table","role":"composite","props":["columns","dataSource","pagination"],"defaultStyles":"less/css","exampleImport":"import { Table } from 'antd';","notes":"server-side pagination patterns common"}
  ],
  "visualEffects": ["none"],
  "recommendedStack": ["React","Next.js","less","TypeScript"],
  "bundleConsiderations": "Includes CSS; use modular imports to reduce size",
  "exampleUsageSnippet": "<Form onFinish={handleSubmit}><Form.Item name='email'><Input/></Form.Item></Form>"
}
```

---

## 3. Tailwind Utility + Component Kits

Utility-first CSS with copy-paste component blocks for landing pages.

**Characteristics:** Composable utility classes, no runtime CSS, rapid prototyping, design via class composition rather than component APIs.

**Representative repo:** shadcn-ui/ui

**Manifest:**

```json
{
  "style": "Tailwind Utility + Component Kits",
  "description": "Utility-first CSS with copy-paste component blocks for rapid pages",
  "repo": "https://github.com/shadcn/ui",
  "license": "MIT",
  "designTokens": {
    "colors": ["--tw-primary","--tw-secondary","--tw-bg"],
    "typography": ["base","sm","lg"],
    "spacing": ["1","2","4","6","8"],
    "radii": ["rounded-none","rounded-sm","rounded-md","rounded-full"],
    "elevation": ["shadow-sm","shadow-md","shadow-lg"]
  },
  "coreComponents": [
    {"name":"Button","role":"atomic","props":["variant","size","className"],"defaultStyles":"tailwind-classes","exampleImport":"import { Button } from 'ui';","notes":"unstyled variant available; copy into project to customize"},
    {"name":"Dialog","role":"composite","props":["open","onClose","title"],"defaultStyles":"tailwind-classes","exampleImport":"import { Dialog } from 'ui';","notes":"often paired with headless primitives for accessibility"}
  ],
  "visualEffects": ["none","glass optional"],
  "recommendedStack": ["React","Next.js","Tailwind CSS","TypeScript"],
  "bundleConsiderations": "Zero runtime CSS; purge unused classes for small CSS footprint",
  "exampleUsageSnippet": "<Button className='bg-primary text-white px-4 py-2'>Get started</Button>"
}
```

---

## 4. Headless / Primitives (Radix / Headless UI)

Unstyled, accessible primitives you style yourself.

**Characteristics:** Zero visual opinion, full accessibility built in (keyboard nav, ARIA, focus management), bring-your-own styling, composable patterns.

**Representative repo:** radix-ui/primitives

**Manifest:**

```json
{
  "style": "Headless Primitives",
  "description": "Unstyled, accessible building blocks you style yourself",
  "repo": "https://github.com/radix-ui/primitives",
  "license": "MIT",
  "designTokens": {
    "colors": ["token-driven"],
    "typography": ["token-driven"],
    "spacing": ["token-driven"],
    "radii": ["token-driven"],
    "elevation": ["token-driven"]
  },
  "coreComponents": [
    {"name":"Dialog","role":"primitive","props":["open","onOpenChange","aria-label"],"defaultStyles":"unstyled","exampleImport":"import * as Dialog from '@radix-ui/react-dialog';","notes":"provides accessibility and focus management"},
    {"name":"Popover","role":"primitive","props":["open","onOpenChange","side","align"],"defaultStyles":"unstyled","exampleImport":"import * as Popover from '@radix-ui/react-popover';","notes":"positioning via floating-ui"}
  ],
  "visualEffects": ["none"],
  "recommendedStack": ["React","Tailwind or CSS-in-JS","TypeScript"],
  "bundleConsiderations": "Minimal; you supply styles so bundle impact is project-dependent",
  "exampleUsageSnippet": "<Dialog.Root><Dialog.Trigger>Open</Dialog.Trigger><Dialog.Content>...</Dialog.Content></Dialog.Root>"
}
```

---

## 5. Glassmorphism / Liquid Glass

Frosted, refractive glass effects (WebGL/SVG displacement).

**Characteristics:** `backdrop-filter: blur()`, semi-transparent backgrounds, layered depth, highlight/shadow/illumination composition, SVG `feDisplacementMap` for refraction, performance-constrained (max blur layers).

**Representative repo:** rdev/liquid-glass-react

**Manifest:**

```json
{
  "style": "Glassmorphism / Liquid Glass",
  "description": "Frosted, refractive glass effects using backdrop-filter or WebGL displacement",
  "repo": "https://github.com/rdev/liquid-glass-react",
  "license": "MIT",
  "designTokens": {
    "colors": ["glass-tint","accent"],
    "typography": ["display","body"],
    "spacing": ["sm","md","lg"],
    "radii": ["md","lg"],
    "elevation": ["blur-levels"]
  },
  "coreComponents": [
    {"name":"Glass","role":"visual","props":["intensity","tint","radius"],"defaultStyles":"css or canvas","exampleImport":"import { Glass } from 'liquid-glass-react';","notes":"may fallback to static blur on unsupported browsers"}
  ],
  "visualEffects": ["glass","blur","displacement"],
  "recommendedStack": ["React","Vite/Next.js","postcss","optional WebGL libs"],
  "bundleConsiderations": "Includes shaders or heavy runtime; test performance on mobile",
  "exampleUsageSnippet": "<Glass intensity={0.6} tint='#ffffff33'><Content/></Glass>"
}
```

---

## 6. Neumorphism (Soft UI)

Soft shadows, subtle extrusions for tactile minimal UIs.

**Characteristics:** Dual shadow (light + dark) creating embossed/debossed surfaces, monochromatic or near-monochromatic palette, soft rounded shapes, tactile feel. Background color matches element color with shadow differentiation.

**Representative repo:** ui-neumorphism / neumorphism-react

**Manifest:**

```json
{
  "style": "Neumorphism",
  "description": "Soft, extruded surfaces using paired shadows and subtle highlights",
  "repo": "https://github.com/username/neumorphism-react (community kits)",
  "license": "MIT or community",
  "designTokens": {
    "colors": ["surface","highlight","shadow"],
    "typography": ["body","caption"],
    "spacing": ["sm","md","lg"],
    "radii": ["rounded","pill"],
    "elevation": ["soft-low","soft-medium","soft-high"]
  },
  "coreComponents": [
    {"name":"NeumorphicCard","role":"composite","props":["depth","radius","color"],"defaultStyles":"css or css-in-js","exampleImport":"import { NeumorphicCard } from 'neumorphism-react';","notes":"use sparingly for accessibility concerns"},
    {"name":"SoftButton","role":"atomic","props":["variant","size"],"defaultStyles":"css","exampleImport":"import { SoftButton } from 'neumorphism-react';","notes":"contrast must be tested for a11y"}
  ],
  "visualEffects": ["soft-shadows","emboss"],
  "recommendedStack": ["React","Vite/Next.js","CSS-in-JS or SCSS","TypeScript optional"],
  "bundleConsiderations": "Small; CSS heavy",
  "exampleUsageSnippet": "<NeumorphicCard depth={6}>Content</NeumorphicCard>"
}
```

---

## 7. Brutalism / Neo-Brutal

High-contrast, blocky, intentionally raw UI kits and templates.

**Characteristics:** Thick borders, hard shadows (no blur), monospace or display typography, stark color contrasts, intentionally rough edges, no gradients, anti-polished aesthetic.

**Representative repo:** community templates / brutalist React repos

**Manifest:**

```json
{
  "style": "Brutalism",
  "description": "Raw, unapologetic layouts with bold borders, high contrast, and minimal polish",
  "repo": "https://github.com/username/react-brutalist-ui (community examples)",
  "license": "MIT or community",
  "designTokens": {
    "colors": ["black","white","accent"],
    "typography": ["mono","display"],
    "spacing": ["tight","normal","loose"],
    "radii": ["none"],
    "elevation": ["flat"]
  },
  "coreComponents": [
    {"name":"Block","role":"atomic","props":["border","bg","padding"],"defaultStyles":"css or tailwind","exampleImport":"import { Block } from 'react-brutalist-ui';","notes":"often implemented as small community kits"},
    {"name":"RawButton","role":"atomic","props":["onClick","style"],"defaultStyles":"unstyled","exampleImport":"import { RawButton } from 'react-brutalist-ui';","notes":"high-contrast focus styles encouraged"}
  ],
  "visualEffects": ["none"],
  "recommendedStack": ["React","Vite/Next.js","Tailwind or plain CSS","TypeScript optional"],
  "bundleConsiderations": "Tiny; mostly CSS",
  "exampleUsageSnippet": "<Block style={{border:'4px solid #000'}}>Hello</Block>"
}
```

---

## 8. Modern Component Systems (Chakra / Mantine)

Themeable, accessible systems with good defaults for SaaS.

**Characteristics:** Style props API, built-in dark mode, responsive styles via array/object syntax, composable components, sensible defaults that look good without customization.

**Representative repo:** chakra-ui/chakra-ui; mantinedev/mantine

**Manifest:**

```json
{
  "style": "Modern Component Systems",
  "description": "Themeable, accessible systems with good defaults for SaaS",
  "repo": "https://github.com/chakra-ui/chakra-ui",
  "license": "MIT",
  "designTokens": {
    "colors": ["brand.50..900"],
    "typography": ["fonts","sizes"],
    "spacing": ["1","2","3","4","5"],
    "radii": ["sm","md","lg"],
    "elevation": ["shadows"]
  },
  "coreComponents": [
    {"name":"Box","role":"primitive","props":["as","sx","children"],"defaultStyles":"css-in-js","exampleImport":"import { Box } from '@chakra-ui/react';","notes":"primitive building block"},
    {"name":"Button","role":"atomic","props":["variant","size","colorScheme"],"defaultStyles":"css-in-js","exampleImport":"import { Button } from '@chakra-ui/react';","notes":"themeable via ThemeProvider"}
  ],
  "visualEffects": ["none","subtle"],
  "recommendedStack": ["React","Next.js","emotion or styled-system","TypeScript"],
  "bundleConsiderations": "CSS-in-JS runtime; tree-shakeable components",
  "exampleUsageSnippet": "<Button colorScheme='teal' size='md'>Submit</Button>"
}
```

---

## 9. Fluent / Microsoft Style

Microsoft 365 look, enterprise controls and tokens.

**Characteristics:** Acrylic material (translucent layers), reveal highlight on hover, depth via shadow and layering, motion system with easing curves, token-based theming.

**Representative repo:** microsoft/fluentui

**Manifest:**

```json
{
  "style": "Fluent",
  "description": "Microsoft Fluent design language for enterprise apps and Office-like experiences",
  "repo": "https://github.com/microsoft/fluentui",
  "license": "MIT",
  "designTokens": {
    "colors": ["themePrimary","themeSecondary","neutralLight","neutralLighter","neutralDark"],
    "typography": ["fontFamily","sizeScale","weights"],
    "spacing": ["s1","s2","s3","s4"],
    "radii": ["none","small","medium","large"],
    "elevation": ["z0","z1","z2"]
  },
  "coreComponents": [
    {"name":"Button","role":"atomic","props":["appearance","disabled","icon"],"defaultStyles":"css-in-js","exampleImport":"import { PrimaryButton } from '@fluentui/react';","notes":"focus on accessibility and keyboard navigation"},
    {"name":"CommandBar","role":"composite","props":["items","overflowItems"],"defaultStyles":"css-in-js","exampleImport":"import { CommandBar } from '@fluentui/react';","notes":"used for top-level app commands"}
  ],
  "visualEffects": ["acrylic","depth"],
  "recommendedStack": ["React","Next.js","TypeScript","emotion"],
  "bundleConsiderations": "Modular imports recommended to reduce bundle size",
  "exampleUsageSnippet": "<PrimaryButton text='Save' onClick={save}/>"
}
```

---

## 10. Motion-First / Framer Motion

Motion, gestures, micro-interactions for polished UIs.

**Characteristics:** Declarative animation API, layout animations, gesture handlers (drag, tap, hover), AnimatePresence for exit animations, shared layout transitions, variant-based animation orchestration.

**Representative repo:** framer-motion (motion/react)

**Manifest:**

```json
{
  "style": "Motion-First",
  "description": "Motion, gestures, and micro-interactions as first-class UI elements",
  "repo": "https://github.com/framer/motion",
  "license": "MIT",
  "designTokens": {
    "colors": [],
    "typography": [],
    "spacing": [],
    "radii": [],
    "elevation": []
  },
  "coreComponents": [
    {"name":"motion.div","role":"primitive","props":["initial","animate","exit","transition"],"defaultStyles":"unstyled","exampleImport":"import { motion } from 'framer-motion';","notes":"works with layout animations and gestures"}
  ],
  "visualEffects": ["motion","spring","keyframe"],
  "recommendedStack": ["React","Next.js","TypeScript"],
  "bundleConsiderations": "Small to moderate; tree-shakable but animations add runtime cost",
  "exampleUsageSnippet": "<motion.div initial={{opacity:0}} animate={{opacity:1}}>Hello</motion.div>"
}
```

---

## 11. Spring / Physics Animation

Natural spring physics for UI motion.

**Characteristics:** Spring-based interpolation (mass, tension, friction), no fixed durations, natural feel, chainable animations, gesture-responsive, imperative and declarative APIs.

**Representative repo:** pmndrs/react-spring

**Manifest:**

```json
{
  "style": "Physics-based Motion",
  "description": "Natural, physics-driven motion primitives for UI interactions",
  "repo": "https://github.com/pmndrs/react-spring",
  "license": "MIT",
  "designTokens": {
    "motion": ["spring-stiffness","damping","mass"],
    "timing": ["short","medium","long"]
  },
  "coreComponents": [
    {"name":"useSpring","role":"primitive","props":["to","config"],"defaultStyles":"unstyled","exampleImport":"import { useSpring, animated } from 'react-spring';","notes":"works well for interactive components"},
    {"name":"useTransition","role":"primitive","props":["items","keys","from","enter","leave"],"defaultStyles":"unstyled","exampleImport":"import { useTransition } from 'react-spring';","notes":"list transitions and mounting animations"}
  ],
  "visualEffects": ["spring","physics"],
  "recommendedStack": ["React","Next.js","TypeScript"],
  "bundleConsiderations": "Small to moderate; runtime for physics calculations",
  "exampleUsageSnippet": "const props = useSpring({ opacity: 1, from: { opacity: 0 } });"
}
```

---

## 12. 3D / Immersive Interfaces

WebGL + React renderer for immersive scenes.

**Characteristics:** Three.js via React component model, 3D scenes embedded in web UI, shader materials, camera controls, physics integration, post-processing effects.

**Representative repo:** pmndrs/react-three-fiber

**Manifest:**

```json
{
  "style": "3D / Immersive",
  "description": "WebGL scenes and 3D UIs rendered in React",
  "repo": "https://github.com/pmndrs/react-three-fiber",
  "license": "MIT",
  "designTokens": {},
  "coreComponents": [
    {"name":"Canvas","role":"container","props":["camera","shadows"],"defaultStyles":"canvas","exampleImport":"import { Canvas } from '@react-three/fiber';","notes":"use with drei helpers and gltf loaders"}
  ],
  "visualEffects": ["3d","shaders","postprocessing"],
  "recommendedStack": ["React","Vite/Next.js","three.js","GLTF loaders"],
  "bundleConsiderations": "High; large runtime and GPU cost; lazy-load heavy scenes",
  "exampleUsageSnippet": "<Canvas><mesh><boxGeometry/><meshStandardMaterial/></mesh></Canvas>"
}
```

---

## 13. Headless Tailwind (Headless UI)

Tailwind-friendly unstyled components (menus, dialogs).

**Characteristics:** Designed to pair with Tailwind, render prop / slot pattern, accessible by default, zero styling included, transition support built in.

**Representative repo:** tailwindlabs/headlessui

**Manifest:**

```json
{
  "style": "Headless Tailwind",
  "description": "Unstyled interactive primitives designed to pair with Tailwind CSS",
  "repo": "https://github.com/tailwindlabs/headlessui",
  "license": "MIT",
  "designTokens": {
    "colors": ["tailwind tokens"],
    "typography": ["tailwind tokens"],
    "spacing": ["tailwind tokens"],
    "radii": ["tailwind tokens"],
    "elevation": ["tailwind shadows"]
  },
  "coreComponents": [
    {"name":"Menu","role":"primitive","props":["as","open","onChange"],"defaultStyles":"unstyled","exampleImport":"import { Menu } from '@headlessui/react';","notes":"works seamlessly with Tailwind classes"},
    {"name":"Transition","role":"primitive","props":["show","enter","leave"],"defaultStyles":"unstyled","exampleImport":"import { Transition } from '@headlessui/react';","notes":"animation helper for UI transitions"}
  ],
  "visualEffects": ["none"],
  "recommendedStack": ["React","Next.js","Tailwind CSS","TypeScript"],
  "bundleConsiderations": "Minimal; styling is project-supplied",
  "exampleUsageSnippet": "<Menu><Menu.Button>Options</Menu.Button><Menu.Items>...</Menu.Items></Menu>"
}
```

---

## 14. Design System Foundations (Radix + Tokens)

Low-level building blocks + token systems for design systems.

**Characteristics:** Primitive components as foundation layer, design token architecture (W3C spec compatible), semantic naming, platform-agnostic token definitions, theme generation.

**Representative repo:** radix-ui/primitives; design token repos

**Manifest:**

```json
{
  "style": "Design System Foundations",
  "description": "Token-first systems combined with headless primitives for robust DS implementations",
  "repo": "https://github.com/radix-ui/primitives",
  "license": "MIT",
  "designTokens": {
    "colors": ["brand","neutral","accent","semantic"],
    "typography": ["scale","weights","lineHeights"],
    "spacing": ["xs","sm","md","lg","xl"],
    "radii": ["none","sm","md","lg"],
    "elevation": ["none","low","medium","high"]
  },
  "coreComponents": [
    {"name":"TokenRegistry","role":"foundation","props":["setToken","getToken"],"defaultStyles":"none","exampleImport":"import tokens from 'design-tokens';","notes":"centralized token management"},
    {"name":"PrimitiveWrappers","role":"primitive","props":["as","className"],"defaultStyles":"unstyled","exampleImport":"import * as Primitives from '@radix-ui/react-*';","notes":"used to build DS components"}
  ],
  "visualEffects": ["none","optional"],
  "recommendedStack": ["React","TypeScript","Style Dictionary","Tailwind or CSS-in-JS"],
  "bundleConsiderations": "Tokens are tiny; component libraries determine bundle size",
  "exampleUsageSnippet": "tokens.set('color.primary','#0ea5a4')"
}
```

---

## 15. Classic Design Systems (Carbon, Primer, Polaris, Evergreen)

Large organization systems for consistent product UIs.

**Characteristics:** Opinionated component libraries reflecting org brand, extensive documentation, strict usage guidelines, accessibility built in, often tied to specific design tools (Figma kits).

**Representative repos:**
- carbon-design-system/carbon (IBM)
- primer/react (GitHub)
- shopify/polaris (Shopify)
- segmentio/evergreen (Segment)

**Manifest:**

```json
{
  "style": "Classic Org Design Systems",
  "description": "Large organization design systems with strict patterns and governance",
  "repo": "https://github.com/carbon-design-system/carbon",
  "license": "Apache-2.0 or MIT depending on project",
  "designTokens": {
    "colors": ["brand","support","danger","warning","success"],
    "typography": ["display","heading","body","caption"],
    "spacing": ["scale-1","scale-2","scale-3"],
    "radii": ["sm","md","lg"],
    "elevation": ["none","low","medium"]
  },
  "coreComponents": [
    {"name":"LayoutGrid","role":"composite","props":["columns","gap"],"defaultStyles":"scss/css","exampleImport":"import { Grid } from 'carbon-components-react';","notes":"strict layout rules"},
    {"name":"Notification","role":"composite","props":["type","message","duration"],"defaultStyles":"scss/css","exampleImport":"import { Notification } from 'carbon-components-react';","notes":"enterprise-grade patterns"}
  ],
  "visualEffects": ["none"],
  "recommendedStack": ["React","Webpack/Vite","Sass/SCSS","TypeScript"],
  "bundleConsiderations": "Large CSS footprint; use modular imports",
  "exampleUsageSnippet": "<Grid><Column>...</Column></Grid>"
}
```

---

## 16. UI Kits & Themed Component Registries

Curated blocks, templates, and registries for rapid page building.

**Characteristics:** Pre-built page sections (hero, pricing, features, testimonials), copy-paste ready, theme-aware, optimized for landing pages and marketing sites.

**Representative repo:** shadcn-ui/ui; community registries

---

## 17. Minimalist / Scandinavian

Whitespace-first, restrained palettes, and typographic focus for clarity.

**Characteristics:** Large whitespace, limited color palette (often monochrome with a single accent), strong typographic hierarchy, clean lines, functional simplicity.

**Manifest:**

```json
{
  "style": "Minimalist",
  "description": "Whitespace-first, restrained palettes, and typographic focus for clarity",
  "repo": "https://github.com/username/minimal-react-ui (community kits and templates)",
  "license": "MIT or community",
  "designTokens": {
    "colors": ["muted","accent","bg"],
    "typography": ["large-body","small-body","caption"],
    "spacing": ["base","loose"],
    "radii": ["small"],
    "elevation": ["none","subtle"]
  },
  "coreComponents": [
    {"name":"Hero","role":"composite","props":["title","subtitle","cta"],"defaultStyles":"tailwind or css","exampleImport":"import { Hero } from 'minimal-react-ui';","notes":"focus on typography and spacing"},
    {"name":"SimpleNav","role":"composite","props":["links","logo"],"defaultStyles":"css","exampleImport":"import { SimpleNav } from 'minimal-react-ui';","notes":"lightweight navigation patterns"}
  ],
  "visualEffects": ["none"],
  "recommendedStack": ["React","Next.js","Tailwind CSS or plain CSS","TypeScript optional"],
  "bundleConsiderations": "Very small",
  "exampleUsageSnippet": "<Hero title='Product' subtitle='Simple and clean'/>"
}
```

---

## 18. Retro / Vintage UI

Nostalgic palettes, pixel or print textures, and retro typography.

**Characteristics:** Muted or pastel color schemes, grain/texture overlays, serif or display typefaces, print-inspired layouts, intentional nostalgia.

**Manifest:**

```json
{
  "style": "Retro Vintage",
  "description": "Nostalgic palettes, pixel or print textures, and retro typography",
  "repo": "https://github.com/username/react-retro-ui (community themes)",
  "license": "MIT or community",
  "designTokens": {
    "colors": ["muted-pastel","sepia","ink"],
    "typography": ["display-retro","mono"],
    "spacing": ["compact","normal"],
    "radii": ["small","rounded"],
    "elevation": ["flat"]
  },
  "coreComponents": [
    {"name":"Badge","role":"atomic","props":["variant","label"],"defaultStyles":"css","exampleImport":"import { Badge } from 'react-retro-ui';","notes":"texture overlays common"},
    {"name":"Poster","role":"composite","props":["image","title","cta"],"defaultStyles":"css","exampleImport":"import { Poster } from 'react-retro-ui';","notes":"used for hero sections"}
  ],
  "visualEffects": ["grain","texture"],
  "recommendedStack": ["React","Vite/Next.js","SCSS or CSS Modules","TypeScript optional"],
  "bundleConsiderations": "Small; images may increase payload",
  "exampleUsageSnippet": "<Poster title='Vintage' image='/img/poster.jpg'/>"
}
```

---

## 19. Maximalist / Experimental

Layered visuals, bold color clashes, and dense information layouts.

**Characteristics:** Multiple overlapping layers, vivid contrasting colors, mix-blend-mode effects, dense grids, editorial or art-driven aesthetic, intentionally overwhelming.

**Manifest:**

```json
{
  "style": "Maximalist",
  "description": "Layered visuals, bold color clashes, and dense information layouts",
  "repo": "https://github.com/username/react-maximalist-ui (community examples)",
  "license": "MIT or community",
  "designTokens": {
    "colors": ["vivid1","vivid2","contrast"],
    "typography": ["display-large","display-small"],
    "spacing": ["tight","normal","expanded"],
    "radii": ["varied"],
    "elevation": ["layered"]
  },
  "coreComponents": [
    {"name":"LayeredCard","role":"composite","props":["layers","blendMode"],"defaultStyles":"css or canvas","exampleImport":"import { LayeredCard } from 'react-maximalist-ui';","notes":"often uses mix-blend-mode and complex layouts"},
    {"name":"DenseGrid","role":"composite","props":["columns","gutter"],"defaultStyles":"css","exampleImport":"import { DenseGrid } from 'react-maximalist-ui';","notes":"used for editorial or art sites"}
  ],
  "visualEffects": ["blend-modes","overlays","motion"],
  "recommendedStack": ["React","Vite/Next.js","CSS-in-JS or SCSS","TypeScript optional"],
  "bundleConsiderations": "Moderate; heavy visuals may require optimization",
  "exampleUsageSnippet": "<LayeredCard layers={[...]} />"
}
```

---

## 20. Dark Mode First

Design systems built primarily for dark themes with careful contrast and token swaps.

**Characteristics:** Dark backgrounds as default, glow and soft-shadow effects, careful WCAG contrast management, token-based light/dark switching, localStorage persistence for preference.

**Manifest:**

```json
{
  "style": "Dark Mode First",
  "description": "Design systems built primarily for dark themes with careful contrast and token swaps",
  "repo": "https://github.com/username/dark-mode-ui (community patterns)",
  "license": "MIT or community",
  "designTokens": {
    "colors": ["bg-dark","surface-dark","muted-light","accent"],
    "typography": ["body","caption"],
    "spacing": ["sm","md","lg"],
    "radii": ["sm","md"],
    "elevation": ["glow","soft"]
  },
  "coreComponents": [
    {"name":"DarkCard","role":"composite","props":["elevation","radius"],"defaultStyles":"css-in-js","exampleImport":"import { DarkCard } from 'dark-mode-ui';","notes":"ensure WCAG contrast for text"},
    {"name":"ThemeToggle","role":"atomic","props":["value","onChange"],"defaultStyles":"css","exampleImport":"import { ThemeToggle } from 'dark-mode-ui';","notes":"persist preference in localStorage"}
  ],
  "visualEffects": ["glow","soft-shadows"],
  "recommendedStack": ["React","Next.js","CSS-in-JS or Tailwind","TypeScript"],
  "bundleConsiderations": "Small; token swaps are lightweight",
  "exampleUsageSnippet": "<DarkCard elevation='soft'>Content</DarkCard>"
}
```

---

## 21. Accessibility-First / Inclusive Design

Design systems and libraries prioritizing ARIA, keyboard, and screen reader support.

**Characteristics:** High-contrast defaults, readable type scales, focus traps, skip navigation, screen reader announcements, WCAG 2.1+ compliance as primary design constraint.

**Manifest:**

```json
{
  "style": "Accessibility-First",
  "description": "Design systems and libraries prioritizing ARIA, keyboard, and screen reader support",
  "repo": "https://github.com/username/a11y-react-kits (examples and patterns)",
  "license": "MIT or community",
  "designTokens": {
    "colors": ["high-contrast","muted","accent"],
    "typography": ["readable-scale","lineHeight"],
    "spacing": ["comfortable","compact"],
    "radii": ["small"],
    "elevation": ["none","subtle"]
  },
  "coreComponents": [
    {"name":"AccessibleDialog","role":"primitive","props":["open","onOpenChange","ariaLabel"],"defaultStyles":"unstyled","exampleImport":"import { AccessibleDialog } from 'a11y-react-kits';","notes":"focus trap and screen reader announcements"},
    {"name":"SkipNav","role":"atomic","props":["targetId"],"defaultStyles":"css","exampleImport":"import { SkipNavLink } from 'a11y-react-kits';","notes":"improves keyboard navigation"}
  ],
  "visualEffects": ["none"],
  "recommendedStack": ["React","Next.js","Radix/Headless UI","TypeScript"],
  "bundleConsiderations": "Minimal; focus on semantics over visuals",
  "exampleUsageSnippet": "<AccessibleDialog open={open} onOpenChange={setOpen}>...</AccessibleDialog>"
}
```

---

## 22. 3D + WebXR / AR

Immersive 3D scenes and WebXR experiences integrated into React.

**Characteristics:** WebXR session management, gaze and controller interaction, spatial UI, combined with react-three-fiber for rendering, progressive enhancement for non-XR browsers.

**Manifest:**

```json
{
  "style": "3D + AR/VR",
  "description": "Immersive 3D scenes and WebXR experiences integrated into React",
  "repo": "https://github.com/pmndrs/react-three-fiber",
  "license": "MIT",
  "designTokens": {
    "scene": ["cameraFov","ambientLight","toneMapping"],
    "interaction": ["gaze","controller"]
  },
  "coreComponents": [
    {"name":"Canvas","role":"container","props":["camera","shadows"],"defaultStyles":"canvas","exampleImport":"import { Canvas } from '@react-three/fiber';","notes":"combine with @react-three/drei and react-xr"},
    {"name":"XRCanvas","role":"container","props":["sessionInit"],"defaultStyles":"canvas","exampleImport":"import { XR } from '@react-three/xr';","notes":"WebXR session helpers"}
  ],
  "visualEffects": ["3d","postprocessing","xr"],
  "recommendedStack": ["React","Vite/Next.js","three.js","GLTF loaders","TypeScript"],
  "bundleConsiderations": "High; lazy-load and code-split heavy scenes",
  "exampleUsageSnippet": "<Canvas><mesh><boxGeometry/><meshStandardMaterial/></mesh></Canvas>"
}
```

---

## 23. Data Visualization (D3 wrappers, Recharts, Visx)

Charts, graphs, and dashboards with React wrappers around D3 and canvas/SVG libs.

**Characteristics:** Composable chart primitives, scale-based positioning, axis/label systems, responsive SVG/canvas rendering, animation support for data transitions.

**Manifest:**

```json
{
  "style": "Data Visualization",
  "description": "Charts, graphs, and dashboards with React wrappers around D3 and canvas/SVG libs",
  "repo": "https://github.com/airbnb/visx",
  "license": "MIT",
  "designTokens": {
    "colors": ["chartPalette","accent","muted"],
    "typography": ["axis","label"],
    "spacing": ["axisPadding","tickSpacing"]
  },
  "coreComponents": [
    {"name":"Axis","role":"primitive","props":["scale","orient","tickFormat"],"defaultStyles":"svg/css","exampleImport":"import { Axis } from '@visx/axis';","notes":"composable chart primitives"},
    {"name":"Bar","role":"primitive","props":["x","y","width","height"],"defaultStyles":"svg","exampleImport":"import { Bar } from '@visx/shape';","notes":"use with scales and layouts"}
  ],
  "visualEffects": ["svg","canvas","animated"],
  "recommendedStack": ["React","Vite/Next.js","visx/d3/recharts","TypeScript"],
  "bundleConsiderations": "Moderate; heavy datasets affect runtime",
  "exampleUsageSnippet": "<Bar x={...} y={...} />"
}
```

---

## 24. E-commerce / Commerce UI

Components and patterns optimized for product catalogs, carts, and checkout flows.

**Characteristics:** Product cards, pricing displays, cart interactions, checkout flows, localization-ready, image-heavy layouts, trust signals (badges, reviews).

**Manifest:**

```json
{
  "style": "E-commerce",
  "description": "Components and patterns optimized for product catalogs, carts, and checkout flows",
  "repo": "https://github.com/Shopify/polaris-react",
  "license": "MIT",
  "designTokens": {
    "colors": ["brand","sale","muted","bg"],
    "typography": ["productTitle","price","meta"],
    "spacing": ["compact","normal","spacious"],
    "radii": ["sm","md"],
    "elevation": ["card"]
  },
  "coreComponents": [
    {"name":"ProductCard","role":"composite","props":["image","title","price","cta"],"defaultStyles":"scss/css","exampleImport":"import { Card } from '@shopify/polaris';","notes":"accessibility and localization built-in"},
    {"name":"Cart","role":"composite","props":["items","onUpdate","onCheckout"],"defaultStyles":"scss/css","exampleImport":"import { Cart } from 'commerce-kit';","notes":"server-side and client-side patterns"}
  ],
  "visualEffects": ["none","subtle"],
  "recommendedStack": ["React","Next.js","Shopify Storefront API or Commerce APIs","TypeScript"],
  "bundleConsiderations": "Moderate; images and product data dominate payload",
  "exampleUsageSnippet": "<ProductCard title='Sneakers' price='$99' image='/img/sneakers.jpg'/>"
}
```

---

## 25. Content-First / CMS Themes

Themeable React themes optimized for CMS-driven content and editorial layouts.

**Characteristics:** Rich text rendering, image optimization, editorial typography, content rhythm spacing, headless CMS integration, SEO-optimized markup.

**Manifest:**

```json
{
  "style": "Content-First / CMS Themes",
  "description": "Themeable React themes optimized for CMS-driven content and editorial layouts",
  "repo": "https://github.com/vercel/next.js/tree/canary/examples/cms-contentful (example themes)",
  "license": "MIT or project-specific",
  "designTokens": {
    "colors": ["content-bg","text","muted"],
    "typography": ["lead","body","caption"],
    "spacing": ["content-gutter","rhythm"],
    "radii": ["small"],
    "elevation": ["none"]
  },
  "coreComponents": [
    {"name":"Article","role":"composite","props":["title","body","author","date"],"defaultStyles":"css or tailwind","exampleImport":"import Article from 'theme/article';","notes":"rich text rendering and image optimization"},
    {"name":"AuthorCard","role":"atomic","props":["name","avatar","bio"],"defaultStyles":"css","exampleImport":"import { AuthorCard } from 'theme/components';","notes":"used in editorial footers"}
  ],
  "visualEffects": ["none","subtle"],
  "recommendedStack": ["Next.js/Gatsby","Headless CMS (Contentful/Strapi)","Tailwind or CSS Modules","TypeScript optional"],
  "bundleConsiderations": "Small; images and markdown processing affect build",
  "exampleUsageSnippet": "<Article title='Post' body={html} />"
}
```

---

## 26. Low-Code / No-Code Component Integrations

React components and wrappers designed for low-code builders and visual editors.

**Characteristics:** Block-based editing, JSON-serializable state, property panels for visual configuration, drag-and-drop composition, schema-driven rendering.

**Manifest:**

```json
{
  "style": "Low-Code Integrations",
  "description": "React components and wrappers designed for low-code builders and visual editors",
  "repo": "https://github.com/stackblitz/low-code-examples (community examples)",
  "license": "MIT or community",
  "designTokens": {
    "colors": ["builder-bg","control","accent"],
    "typography": ["label","body"],
    "spacing": ["control-gap","row-gap"],
    "radii": ["small"],
    "elevation": ["none"]
  },
  "coreComponents": [
    {"name":"BlockEditor","role":"composite","props":["blocks","onChange"],"defaultStyles":"css","exampleImport":"import { BlockEditor } from 'low-code-kit';","notes":"serializes to JSON for persistence"},
    {"name":"PropertyPanel","role":"atomic","props":["schema","value","onChange"],"defaultStyles":"css","exampleImport":"import { PropertyPanel } from 'low-code-kit';","notes":"used by visual editors"}
  ],
  "visualEffects": ["none"],
  "recommendedStack": ["React","Vite/Next.js","TypeScript","JSON schema"],
  "bundleConsiderations": "Moderate; editor tooling adds runtime",
  "exampleUsageSnippet": "<BlockEditor blocks={blocks} onChange={setBlocks} />"
}
```

---

## How the Agent Should Use This

- **Never default to a single style.** Ask the user what they want or infer from context.
- **Ingest each repo's README + examples** to extract component names, props, tokens, and usage patterns when working in that style.
- **Map tokens to canonical design tokens** (color, spacing, typography) so the agent can translate between styles.
- **Prioritize by project type** (landing page, SaaS dashboard, immersive demo) and by constraints (bundle size, accessibility, browser support).
- **Styles can be combined.** A project might use Headless primitives + Spring animation + Glassmorphism surfaces. The agent should understand how styles compose.
