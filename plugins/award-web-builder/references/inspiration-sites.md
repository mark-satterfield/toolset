# Inspiration Sites — Design Reference

> **Date**: 2026-03-27
> **Purpose**: Provide an agentic web designer with detailed, actionable design specifications derived from five high-quality SaaS marketing sites.

---

## 1. Webflow (webflow.com)

### Overall Design Language
Premium SaaS marketing site. Dark-mode dominant with selective light sections for contrast. The aesthetic is editorial and spacious — generous whitespace, large type, and a magazine-like rhythm of text and media blocks.

### Color Palette
- **Hero background**: Dark blue gradient (deep navy-blue transitioning darker toward the top)
- **Background progression through the full page**:
  1. **Hero**: Dark blue gradient
  2. **Webflow editor showcase / platform features / customer stories / audience switcher / AI section**: Pure black (#000 or near-black)
  3. **Bottom CTA ("Make your website your competitive edge")**: Medium gray background with blurred/muted overlay
  4. **Showcase gallery**: Colorful abstract blobs/blurs (pink, green gradients) as decorative background elements behind stacked site screenshots
  5. **Footer**: Dark near-black
- The page is NOT one uniform dark tone — it has at least four distinct background phases.
- **Text**: White and off-white on dark backgrounds
- **Accent**: Brand blue for primary CTAs
- **Logos**: Monochrome SVG variants (dark-mode adapted)

### Typography
- **Family**: Custom or geometric sans-serif, clean, tight letter-spacing
- **H1**: Oversized, statement-level (48–72px+ range), bold weight
- **Body**: Medium-weight, high contrast against dark backgrounds
- **Hierarchy enforcement**: Size jumps over weight variation — headings bold, body regular, subheads medium weight

### Navigation
- **Structure**: Sticky top nav, dark background
- **Layout**: Logo left, horizontal menu center, CTA buttons right ("Get started" primary, "Contact Sales" secondary)
- **Dropdowns**: Mega dropdown menus organized into columnar groups with section headers (Build, Manage, Optimize, Extend). Include thumbnail images for featured items
- **Special features**: Role-switcher (Marketer/Designer/Developer/Agency), theme toggle (Light/Dark/Auto)
- **Mobile**: Hamburger menu with slide-in panel

### Hero Section
- **Layout**: Full-width, large background image/video showing the Webflow editor UI
- **Headline style**: Short, declarative ("Make your website a growth engine")
- **CTA button style**: "Start for free" is bright blue filled, rounded corners. "Contact Sales" is plain white text link (no button border visible at this viewport).
- **Interactive element**: "How do you want to build?" chooser — three card options (AI site builder, Template, Blank site) with subtle dark borders on a dark blue background, each with a thumbnail preview image on the right side, title, description, and hover state
- **"Talk to Sales"** adjacent to the build chooser is a bordered/outlined button
- **Logo bar**: "Trusted by teams at" — monochrome SVG logos (Monday.com, Spotify, TED, Dropbox, Greenhouse, CLEAR, Orangetheory Fitness, Checkout.com, SoundCloud, Walker & Dunlop, Reddit, Docusign) in horizontal strip, white/monochrome logos on dark background, horizontally scrolling

### "From idea to impact, faster" Heading
Uses a **blue-to-white CSS gradient text effect** on the words. Not solid white text. This is a scroll-reveal section between the customer stories and the AI tabbed section.

### Social Proof Carousel
- **Type**: Horizontally scrolling, infinite loop (items duplicated in markup)
- **Card contents**: Client logo, large stat metric (e.g., "10x", "$6M", "1,170%"), brief descriptor, "Read story" arrow link
- **Styling**: Cards show **blurred photo backgrounds** (people/lifestyle imagery) with overlaid content:
  - Large stat number (white, bold)
  - Stat descriptor text
  - Pull quote in quotation marks
  - Attribution (name + title)
  - Small circular arrow button in bottom-right corner
- NOT clean cards with solid colored backgrounds. The photo blur creates depth and visual interest.

### Tabbed Content Pattern
Used in multiple sections (Build/Manage/Optimize, AI section, Rich Experiences section):
- **Tab UI**: Horizontally arranged labels; selecting a tab swaps the content panel below
- **Panel content**: Product screenshot/mockup with description and CTA link
- **Repetition**: This pattern repeats for the AI section and the "Deliver rich experiences" section

### Audience Switcher
- A section that changes content based on audience role
- Reads: "Everything [marketing teams / design teams / engineering teams / agencies] love about Webflow"
- "marketing teams" appears inside a **bordered pill/dropdown element with a chevron** — not a plain tab
- Layout is **two-column**: left column has feature links separated by thin horizontal dividers with right-arrow indicators; right column shows a large product screenshot
- Sub-section labels (Agility, Impact, Scale) appear as **left-aligned gray labels** in the left column above their respective feature link groups
- The screenshot on the right changes based on which feature link is hovered/selected

### Feature Grid Cards
- **Layout**: Rectangular cards in 2–3 column grids
- **Card structure**: Top image/screenshot, heading, 1–2 line description, arrow-link CTA
- **Hover states**: Subtle elevation/shadow changes and directional arrow indicators

### Customer Testimonial Carousel
- **Layout**: Full-width, horizontal slider
- **Slide contents**: Large background image or video (with play/pause controls), client logo (white/light variant), stat metric, pull quote, attribution (name + title)
- **Navigation**: Swipe/arrow based

### Video Section
Embedded video with poster image and play/pause controls. Framed by floating UI element overlays (screenshots of the Webflow designer interface positioned around the video).

### Bottom CTA Section
- Background shifts to **medium gray** (distinct from the black body sections above)
- Strong headline, two CTAs: "Get started — it's free" (bright blue filled button) and "Talk to sales" (dark/muted filled button, not outlined)
- Below: stacked website showcase screenshots with **up/down arrow navigation buttons** (circular, white outline)

### Showcase Gallery
- Website screenshots (e.g., Jasper AI visible) are stacked/overlapping in a card stack
- Background features **abstract color blobs** — pink and green gradient blurs as decorative elements
- Each showcase card shows the site name and a "View website" external link

### Footer
- **Structure**: Multi-column mega footer
- **Background**: Dark near-black (consistent with earlier dark sections)
- **Columns**: Product, Solutions/Resources, Company/Compare, Community/Get help
- **White text**, no accent colors in the footer itself
- **Bottom bar**: Copyright, social icons (YouTube, X, Facebook, LinkedIn, Instagram, TikTok), "Made in Webflow" badge

### Animation/Interaction
- Directional arrow indicators on card hovers
- Video play/pause toggles
- Tab content transitions (likely fade or slide)
- Infinite-scroll logo carousels
- Scroll-triggered section reveals implied by content rhythm
- Customer carousel slide transitions
- Lazy-loaded images with placeholder SVGs swapping to WebP/AVIF

### Image Formats
Heavy use of WebP and AVIF from `cdn.prod.website-files.com`. Separate desktop and tablet hero images. Logos are SVG. Product screenshots are high-res WebP.

---

## 2. Vercel (vercel.com)

### Overall Design Language
Developer-focused, minimalist, high-contrast. Light and dark mode support (system-aware). Typography-forward — enormous headlines, very little ornamentation, "less is more" philosophy. Clean geometry. Closer to a technical document than a traditional marketing site.

### Color Palette
- **Backgrounds**: Near-black (#000) or white depending on theme
- **Text**: Pure white on dark, pure black on light
- **Accent**: Minimal — used sparingly for logos, status indicators, and subtle UI chrome
- **Brand expression**: Through the triangle logo and typographic confidence, not color

### Typography
- **Family**: Geist (custom sans-serif)
- **H1**: Extremely large (60–80px+), tightly tracked
- **Body**: Small-to-medium, light weight, generous line height
- **Scale contrast**: Very high ratio between heading and body sizes

### Navigation
- **Structure**: Sticky top nav
- **Layout**: Logo (triangle + "Vercel" logotype) left, horizontal menu center-left
- **Menu items**: Products, Resources, Solutions, Enterprise, Pricing
- **Products dropdown**: Splits into "AI Cloud", "Core Platform", "Security" sub-groups
- **Right side**: Log In, Contact, Sign Up (primary filled CTA)
- **Theme**: Separate light/dark logo assets swap with system theme

### Hero Section
- **Layout**: Centered headline, centered subtitle paragraph
- **CTAs**: Two buttons (Deploy primary, Get a Demo secondary)
- **Below hero**: Scrolling "social proof ticker" — a single horizontal line of text with company logos inline ("[Company] build times went from 7m to 40s. [Company] saw a 95% reduction in page load times.") — scrolls horizontally

### Use Case Tabs
- Horizontal tab row (AI Apps, Web Apps, Ecommerce, Marketing, Platforms)
- Selecting a tab changes the content description and deploy CTA below
- Minimal styling — tab highlights/underlines on selection

### Product Cards (Bento Grid)
- **Section**: "Your product, delivered"
- **Layout**: Bento-grid with cards of different sizes
- **Cards**: Agents (large), AI Apps, Web Apps, Composable Commerce, Multi-tenant Platform
- **Card structure**: Title, one-line description, arrow link, SVG illustration (dual light/dark assets)
- **Styling**: Subtle borders, rounded corners

### Framework Logos Section
Horizontal row of framework logos (Svelte, Vite, Next.js, Nuxt, Turbopack) with heading "Framework-Defined Infrastructure." Clean, no background cards — floating logos.

### Split Statement Section
"Scale your Enterprise without compromising Security" — linked text within a large heading. "Enterprise" and "Security" are hyperlinks. Typographic-only section, no images.

### Infrastructure Globe
- "Deploy once, deliver everywhere"
- Animated globe visualization — WebGL or SVG
- Nodes on the globe send out small pulses to indicate activity
- Two CTAs below

### Fluid Compute Section
Split layout — text left, SVG diagram right. Diagram shows compute model visualization with light and dark variants. Technical illustration style.

### AI Gateway Section
- Code snippet block with tabs (AI SDK / Python / OpenAI HTTP) and syntax highlighting
- Horizontal row of model provider logos (OpenAI, xAI, Anthropic + "many more" link)
- "Top models" leaderboard table — model names, usage percentages, minimal data table styling with rank numbers

### Template Grid
"Deploy your first app in seconds" — grid of template cards by framework (Next.js, React, Astro, Svelte, Nuxt, Python). Small thumbnail blocks.

### Footer
- **Structure**: Multi-column
- **Columns**: Get Started, Build, Scale, Secure, Resources, Learn, Frameworks, SDKs, Use Cases, Company, Community
- **Bottom**: Status link, theme selector (system/light/dark)
- Dense but clean

### Animation/Interaction
- Globe with pulsing nodes (WebGL/canvas)
- Scrolling social-proof ticker
- Tab content switching
- Code block tab switching
- Theme-aware asset swapping (every illustration has light + dark variant)
- Minimal scroll animations — relies on content density and typography

### Image Formats
SVG illustrations (dual light/dark), hosted on Vercel blob storage. Very few raster images.

---

## 3. Klaviyo (klaviyo.com)

### Overall Design Language
Bold B2C SaaS. Dark theme (near-black backgrounds) with warm accent colors (orange/coral). Energetic and confident — large type, strong color blocks, product-screenshot-forward. More visually aggressive than Vercel, less editorial than Webflow.

### Color Palette
- **Backgrounds**: Very dark (#0a0a0a range)
- **Primary accent**: Warm orange/coral (Klaviyo brand color) — visible in logos, CTAs, flag icon, gradients and solid button fills
- **Text**: White on dark
- **Decorative**: Orange flag icon used as brand element throughout

### Typography
- **Family**: Geometric or neo-grotesque sans-serif
- **H1**: Massive — "AI marketing & service to grow relationships"
- **Headings**: Sentence-case
- **Body**: Medium-weight, good contrast
- **Stats**: Oversized, bold display weight for metric numbers in case study cards

### Navigation
- **Structure**: Two-tier top bar
- **Top utility bar**: Home, Help center, Enterprise, Partners, Careers, Log in
- **Main nav**: Platform, Apps & Integrations, Resources, What's New, Pricing
- **Right side**: Sign up + Get a demo CTAs
- **Platform dropdown**: Full mega-menu with columns (Overview, Solutions, Channels, Top Products + Features, Spotlight section with image cards)

### Hero Section
- **Layout**: Full-width dark section, headline centered
- **CTA**: Email input field for sign-up
- **Background**: Video element (`.webm` format) — ambient motion graphic or product animation loop
- **Logo bar below**: Brand logos (CorePower Yoga, Daily Harvest, Dollar Shave Club, Glossier, Mattel, The Body Shop, Vans, Vuori, etc.) — monochrome SVGs in infinite horizontal scroll carousel (tripled items for seamless loop)

### "Meet Composer" Feature Block
Left-right split. Left: large product screenshot (Composer AI agent building a campaign). Right: headline, description, CTA link, "Watch Video" trigger. Screenshot shows actual UI — email preview on phone, campaign builder interface.

### AI Agent Cards
Two-column cards for "Marketing Agent" and "Customer Agent." Each card: heading, multi-line description, CTA link. Accordion-style interactive list (one expanded at a time).

### Platform Tabbed Section
- "Your data, intelligence, and AI agents working as one"
- Horizontal tabs: Marketing, AI, Service, Analytics, CDP
- Each tab reveals a product screenshot and sub-feature link list
- Orange flag icon as decorative brand element
- Full-width, high-res product UI screenshots

### Rolling Stats Bar
Infinitely scrolling horizontal ticker: "8B CUSTOMER PROFILES", "1.6B AVERAGE API CALLS PROCESSED DAILY", "3.7B AVERAGE EVENTS PROCESSED DAILY." Stock-ticker-style, oversized numbers, loops continuously.

### Customer Case Study Carousel
- Horizontally scrolling cards (infinite loop)
- Each card: large lifestyle photo background, brand logo, stat metric (large, bold), "Read their story" CTA
- Orange flag icon as decorative interstitial between some cards

### Integration Logos Bar
Infinite horizontal scroll — partner logos (Meta, Shopify, OpenAI, Salesforce, etc.) in monochrome SVG. "350+ pre-built integrations" headline, CTA to marketplace.

### Awards Section
G2 and Capterra badge images in a horizontal row.

### FAQ Accordion
Expandable FAQ items. Click-to-toggle pattern. Standard questions about product, pricing, integrations, channels, enterprise.

### Footer
- **Structure**: Multi-column mega footer
- **Columns**: Company, Platform, Channels, Top Products + Features
- **Secondary**: Klaviyo for (Enterprise, Partners, etc.), Why Klaviyo (comparison pages), Tools + Resources
- **Extras**: Locale selector (US/DE/AU/UK/SG/ES/FR/IT), social links, legal links

### Animation/Interaction
- Hero background video (`.webm`)
- Multiple infinite-scroll horizontal carousels (logos, stats, case studies)
- Tab content transitions
- Accordion FAQ
- Product screenshots likely lazy-load with fade-in

### Image Formats
WebP for product screenshots and photos (Astro `/_astro/` paths). SVG for logos and icons. Video for hero background. Sanity CDN for spotlight content images.

---

## 4. Huly (huly.io)

### Overall Design Language
Developer/productivity tool aesthetic. The hero section is dark-mode, but the page transitions to light/white backgrounds as you scroll into the feature sections. Rich, immersive hero, then clean and readable product content below. Reads as a modern open-source project homepage — confident, slightly playful, community-oriented.

### Color Palette
- **Hero area**: Deep dark backgrounds (near-black with blue/purple undertones), white text
- **Body sections**: White or very light gray backgrounds with dark text (confirmed via visual scroll)
- **Accents**: Muted blues and greens for UI highlights. Warm orange in flag/pin imagery
- **Virtual office section**: Light, frosted-glass aesthetic with blue/cyan glow effects
- **Overall**: Moody dark hero transitioning to clean, bright feature sections

### Typography
- **Family**: Clean sans-serif
- **H1**: Large, centered ("Everything App for your teams"), bold
- **Section headings**: Medium-large, confident ("Unmatched productivity", "Work together. Like in the office.")
- **Body**: Regular weight, good line-height, concise and feature-oriented

### Navigation
- Simple top nav. Logo left
- Center links: Pricing, Resources (dropdown: Blog, Docs), Community (dropdown: X, LinkedIn, YouTube, Slack, GitHub, Telegram), Download
- Right: Star Us (GitHub CTA), Sign In, Sign Up
- Compact, not over-stuffed
- Dropdowns include icons next to each community platform link

### Hero Section
- Centered layout on dark background
- Large H1, tagline paragraph ("Huly, an open-source platform, serves as an all-in-one replacement of Linear, Jira, Slack, and Notion.")
- Primary CTA: "See in Action" links to live demo instance
- Large hero illustration below (JPG, high-quality product UI composite)
- Two decorative SVG elements flanking the illustration
- Horizontal strip of feature tags: "Team Planner", "Project Management", "Virtual Office", "Chat", "Documents", "Inbox" — likely animated/scrolling

### "Unmatched productivity" Section
- Text-only feature list on light/white background
- Features: Keyboard shortcuts, Team Planner, Notifications, Time-blocking
- Descriptive cards, no imagery

### "Work together. Like in the office." Section
- Light background with frosted-glass/blue-glow aesthetic
- Interactive-looking UI mockup of a video call: participant avatars, camera controls (mute, screen share, expand, leave), participant name labels
- Room labels visible: "Meeting Room", "Design Weekly", "Lounge", "All hands", "Office Hours"
- Below: three feature cards with small icons (Customize workspace, Audio and video calls, Invite guests)

### "Sync with GitHub" Section
- Six feature cards in grid layout (2x3 or 3x2)
- Each card: SVG icon, heading, one-line description
- Icon-forward design
- Features: Two-way sync, Private tasks, Multiple repositories, Milestone migration, Track progress, Advanced filtering

### MetaBrain Section (Bento Grid)
- "Huly MetaBrain" — asymmetric bento-grid layout
- Cards of varying sizes: "Create tasks" (with screenshot), "Plan your work" (planner screenshot), "Take notes" (notes screenshot), "Sync in real time" (team screenshot), "Chat with team", "Manage projects"
- Each card has desktop and mobile variant images
- Magazine-like masonry layout, high visual density

### Knowledge/Documents Section
- "Knowledge at Your Fingertips"
- Visual rich text editor toolbar representation (Link, Bold, Italic, Underline, Strikethrough, Mention, Highlight)
- Paragraph of text rendered multiple times (showing collaborative editing/formatting)
- Large product screenshot
- Two feature cards: "Collaborate" and "Version History"
- Decorative SVG divider + background image

### CTA Section
- "Join the Movement" — centered text
- "See in Action" primary CTA, "Join our Slack" secondary CTA with icon
- Dark atmospheric illustration background (subtle lighting effects)
- Separate desktop and mobile background images

### Footer
- Minimal. Copyright, Terms of Service, Privacy Policy links
- "Made with passion and Huly" tagline with SVG icon

### Animation and Interaction
- Feature tag strip likely scrolls/animates
- Virtual office mockup may have subtle pulse/glow on avatar states
- Lazy-loaded images via Next.js Image component (srcsets, quality settings)
- Smooth scroll with intersection-observer-triggered section reveals implied
- Content-dense but structurally animated rather than heavily JS-driven

### Image Formats
- JPG for hero and large illustrations (Next.js optimized, quality settings)
- PNG for smaller feature screenshots
- SVG for icons and decorative elements
- All served through Next.js image optimization (`/_next/image?url=...&w=...&q=...`)

---

## 5. Rootly (rootly.com)

### Overall Design Language
Dark SaaS, incident management/DevOps positioning. Professional and serious but not cold — warm touches via customer photos and conversational quotes. Layout is structured and product-feature-centric. Built on Webflow.

### Color Palette
- **Backgrounds**: Very dark (charcoal/near-black)
- **Text**: White and light gray
- **Accents**: Muted blue or teal for primary CTA buttons (minimal accent usage)
- **Color variation**: Comes mostly from product screenshots and customer photos
- **Logo bar**: Full color in case studies, grayscale in trust bar

### Typography
- **Family**: Clean sans-serif throughout
- **H1**: Large but measured (not as oversized as Vercel): "AI SRE agents that resolve your hardest incidents."
- **Subheadings**: Medium-weight
- **Body**: Regular weight, well-spaced
- **Quotes**: Styled distinctly — larger, italic or serif-differentiated
- **Attribution**: Smaller, lighter weight

### Navigation
- Sticky top nav. Logo left
- Main links: Product (dropdown), Solutions (dropdown), Resources (dropdown), Pricing
- Product dropdown sub-sections: On-Call, Incident Response, AI SRE, Retrospectives, Status Page + Platform (Integrations, On-Call Health, Changelog with latest entry preview)
- Solutions dropdown: Size (Startup), Compare (PagerDuty/Opsgenie/JSM), Teams (Security) + customer story thumbnail cards
- Resources dropdown: Engineering docs + Guides + Resources + latest blog post preview
- Right: Log in, Book a demo
- Dropdowns include live content previews (latest changelog, latest blog, customer thumbnails)

### Announcement Banner
- Top-of-page banner with promotional message ("Introducing Rootly Academy...") and arrow link
- Global component with page-tracking metadata

### Hero Section
- Large centered headline, subtitle paragraph
- Two CTA buttons: "Get started for free" (primary), "Book a demo" (secondary)
- Dual-row infinite-scroll logo bar:
  - Row 1: trivago, Tripadvisor, Affirm, Sailpoint, Nvidia, Figma, Mistral AI, Replit, Glean, Elastic
  - Row 2: Poshmark, StackOverflow, Dropbox, LinkedIn, Canva, Grammarly, The Weather Channel, Okta, Cisco, MIT
- Logos: full-color PNGs
- Below logos: three stacked/overlapping product screenshots showing on-call UI

### Repeating Product Feature Section Pattern (x4)
The page has four major product sections (AI SRE, On-Call, Incident Response, Retrospectives), each following an identical structure:

1. **Section label tag** (e.g., "AI SRE", "On-Call")
2. **Section headline** + description paragraph
3. **CTA link** to product page
4. **Four tab-triggers** with arrow indicators:
   - e.g., "Investigate ->", "Find root cause ->", "Suggestions ->", "Rootly MCP server ->"
   - Each has a short description underneath
5. **Four corresponding product screenshots** (AVIF) that swap based on selected tab
6. **Customer testimonial**:
   - Quote text (conversational style)
   - Attribution: name + title
   - Circular-cropped customer photo
   - Customer company logo (color)

This pattern repeats identically for all four product areas.

### Status Page Section
- Simpler layout: headline, description, CTA
- Single large product screenshot (laptop mockup showing status page)

### Philosophy Section
- "The Rootly Philosophy" — grid of five value proposition cards
- Cards: "Opinionated defaults", "Purpose-built", "Rooted in reliability", "Scales as you do", "Extensible by design"
- Text-only (heading + short description), no icons
- "Extensible" card includes CTA to integrations page + integration logo image

### Awards Carousel
- Horizontally scrolling row of G2 badge images (Momentum Leader, High Performer, etc.)
- Infinite loop carousel

### Customer Stories Grid
- Card-based grid layout
- Each card: customer logo, description sentence, circular customer photo, person's name
- Links to full case studies

### Final CTA Section
- "You and your teams deserve modern incident management."
- Two CTA buttons, centered

### Footer
- Multi-column: Product, Company, Resources, Community
- Bottom: copyright, privacy policy, terms of use

### Animation and Interaction
- Dual-row infinite-scroll logo carousels
- Tabbed product screenshot switching (4 tabs x 4 sections = 16 tab interactions)
- Awards badge carousel (infinite loop)
- Hero screenshots stacked/overlapping — possibly parallax or scroll-triggered depth
- Lazy-loaded AVIF product screenshots

### Image Formats
- AVIF for all product screenshots (high compression, Webflow CDN)
- PNG for customer logos and photos
- SVG for icons/UI elements
- Aggressively optimized via Webflow asset pipeline

---

## Cross-Site Pattern Summary

### Common Patterns Across All Five Sites
1. **Dark hero, structured body**: Every site uses a dark hero section. Body sections may shift to light.
2. **Infinite-scroll logo bars**: All five use horizontally scrolling trust/client logo strips with duplicated items for seamless looping.
3. **Tabbed content switching**: All use tabs to swap product screenshots/descriptions without page navigation.
4. **Large stat metrics**: Customer proof sections use oversized numbers (10x, $6M, 1,170%, 67%) as visual anchors.
5. **Sticky navigation**: All five have sticky top navs with mega-dropdown menus.
6. **Dual CTA pattern**: Hero sections consistently use two buttons — primary action + secondary (sales/demo).
7. **Customer testimonial carousels**: All include quote + photo + attribution + company logo.
8. **Modern image formats**: AVIF and WebP dominate, with SVG for logos/icons.

### Differentiators
- **Webflow**: Most complex page — deeply nested tab-within-tab audience switcher, editorial rhythm
- **Vercel**: Most minimal — typography-dominant, globe animation, code snippets, dual-theme asset system
- **Klaviyo**: Most energetic — orange accent color, video hero, rolling stats ticker, highest integration count
- **Huly**: Dark-to-light transition, bento-grid MetaBrain section, virtual office mockup, open-source community emphasis
- **Rootly**: Most structured/repetitive — identical 4-section product pattern, announcement banner, dual-row logo bars

---

## Cross-Site Patterns

Techniques shared across multiple inspiration sites:

| Technique | Webflow | Vercel | Klaviyo | Huly | Rootly |
|-----------|---------|--------|---------|------|--------|
| CSS custom properties for theming | Y | Y | Y | Y | Y |
| Light/dark mode support | Y | Y | - | Y | - |
| GSAP / scroll-triggered animation | Y | - | - | - | Y |
| Staggered entrance reveals | Y | - | - | Y | Y |
| Marquee / infinite scroll | - | - | Y | Y | Y |
| Video backgrounds | - | - | - | Y | Y |
| Responsive typography scaling | Y | Y | - | Y | Y |
| Accessibility-first (ARIA, focus, keyboard) | Y | Y | Y | - | Y |
| Gradient text effects | Y | - | - | Y | - |
| Blend modes for depth | - | - | - | Y | - |
| Custom scrollbar styling | - | - | - | - | Y |
| `color-mix()` for computed colors | Y | - | Y | - | - |
| Tab/card cycling with progress | - | - | - | - | Y |
| Procedural noise/texture | Y | - | - | - | - |

### Quality Bar Summary
These sites share: **intentional motion** (every animation has a purpose), **systematic theming** (CSS variables, not hardcoded values), **responsive sophistication** (not just "it works on mobile" but truly adapted), and **depth through layering** (shadows, z-index, blend modes, blur — not flat surfaces).
