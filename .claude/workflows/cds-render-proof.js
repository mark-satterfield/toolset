export const meta = {
  name: 'cds-render-proof',
  description: 'Generate real CDS stylesheets, one markup fragment per component family, a pregenerated artifact per shape S0-S28, and a sample landing page — all from the live config — as real files for rendering and review.',
  phases: [
    { title: 'Foundation', detail: 'Execute generate-stylesheets on the live YAML -> tokens/components/themes.css + switcher.js + GAPS.md; return the class vocabulary' },
    { title: 'Components', detail: 'One real markup fragment per component family, using the generated classes' },
    { title: 'Shapes', detail: 'One pregenerated artifact per shape S0-S28: real component arrangement with realistic sample content' },
    { title: 'Landing', detail: 'Compose a full sample landing page with alternating sections and the variety principle' },
  ],
}

const P = args.plugin
const YAML = args.yaml
const R = args.render

const SHAPES = [
  ['S0','Standalone heading strip'], ['S1','Centered text + visual below'], ['S2','Two-column text/visual'],
  ['S3','Centered text + embedded affordance'], ['S4','Static card grid'], ['S5','Tagged card grid'],
  ['S6','Tabs with one panel per tab'], ['S7','Alternating image+text rows'], ['S8','Horizontal carousel'],
  ['S9','Marquee strip'], ['S10','Numbered step row'], ['S11','3-up stacked pull-quotes'],
  ['S12','Quote swiper with logos'], ['S13','Single hero quote'], ['S14','Accordion list'],
  ['S15','Tier card row + segment toggle'], ['S16','Rate table'], ['S17','Banner strip'],
  ['S18','Full-width CTA panel'], ['S19','CTA panel + newsletter form'], ['S20','Path picker (2-card fork)'],
  ['S21','Pictogram + nested sub-cards'], ['S22','Pill/tag cloud columns'], ['S23','Lead card + companion carousel'],
  ['S24','Resource grid with source tags'], ['S25','Two-column prompt/artifact panel'], ['S26','Download/install button strip'],
  ['S27','Footer navigation grid'], ['S28','Sub-hero with video + CTA pair'],
]

const COMMON = `
CONTEXT — the Customizable Design System (CDS), a brand-neutral design system plugin. Absolute paths:
- Plugin root: ${P}
- Reference tree (authoritative source of truth): ${P}/reference/  (components.md, page-types.md, section-types.md, shapes.md, compliance.md, foundations/*.md)
- Shape picker: ${P}/skills/compose-page/reference/landing-sections-shape-rules.md
- Generated stylesheets (already written by the Foundation phase): ${R}/styles/tokens.css, components.css, themes.css
RULES that apply to every artifact you write:
- Use ONLY the real kebab-case class names that exist in ${R}/styles/components.css and the role/token names in tokens.css. Read those files first. Never invent a class or hardcode a hex/color — colors come from role tokens only.
- Content must be brand-neutral and realistic (no real company/product names). Plausible placeholder copy, not lorem ipsum.
- Honor the accessibility contracts (ARIA roles/labels, keyboard semantics) from ${P}/reference/foundations/accessibility.md and the component entries.
- Do NOT embed provenance/metadata comments in the markup. Clean markup only.
- If a spec in the reference is too thin to build something correctly, build the best minimal sensible version AND report it in your gaps[].`

const FOUNDATION_SCHEMA = {
  type:'object', additionalProperties:false,
  required:['files','component_families','theme_selectors','gaps'],
  properties:{
    files:{type:'array',items:{type:'string'}},
    component_families:{type:'array',items:{type:'object',additionalProperties:false,required:['name','className','section'],properties:{name:{type:'string'},className:{type:'string'},section:{type:'string'}}}},
    theme_selectors:{type:'array',items:{type:'object',additionalProperties:false,required:['name','modes'],properties:{name:{type:'string'},modes:{type:'array',items:{type:'string'}}}}},
    token_summary:{type:'string'},
    gaps:{type:'array',items:{type:'string'}},
  },
}
const COMP_SCHEMA = { type:'object', additionalProperties:false, required:['written','gaps'], properties:{ written:{type:'array',items:{type:'object',additionalProperties:false,required:['className','file'],properties:{className:{type:'string'},file:{type:'string'}}}}, gaps:{type:'array',items:{type:'string'}} } }
const SHAPE_SCHEMA = { type:'object', additionalProperties:false, required:['id','name','file','sections_using','components_used','gaps'], properties:{ id:{type:'string'}, name:{type:'string'}, file:{type:'string'}, sections_using:{type:'array',items:{type:'string'}}, components_used:{type:'array',items:{type:'string'}}, gaps:{type:'array',items:{type:'string'}} } }
const LANDING_SCHEMA = { type:'object', additionalProperties:false, required:['file','section_sequence','gaps'], properties:{ file:{type:'string'}, section_sequence:{type:'array',items:{type:'object',additionalProperties:false,required:['section','shape','theme'],properties:{section:{type:'string'},shape:{type:'string'},theme:{type:'string'}}}}, notes:{type:'string'}, gaps:{type:'array',items:{type:'string'}} } }

function chunk(a,n){ const o=[]; for(let i=0;i<a.length;i+=n) o.push(a.slice(i,i+n)); return o }

// ---------- Phase 1: Foundation ----------
phase('Foundation')
const foundation = await agent(`You are executing the CDS plugin's generate-stylesheets skill against its live config. The skill is Markdown instructions — executing them faithfully IS running the skill. Do NOT write a Python/JS program that recomputes CSS; read the YAML + reference and emit CSS by following the instructions.

Follow step by step: ${P}/skills/generate-stylesheets/SKILL.md
Elements YAML: ${YAML}
Reference: ${P}/reference/ (read foundations/* and components.md as the skill directs)
Schema: ${P}/validation/customizable-design-elements.schema.json
OUTPUT DIR (create, write here): ${R}/styles/

Emit (per the skill Pipeline):
- tokens.css — custom properties bound to YAML values through the role contract (foundations/overview.md §5); naming per the YAML $conventions block; one declaration per token.
- components.css — one class per component family in components.md; kebab-case identifiers mirroring role/component names (.button-primary, .surface-raised, .text-tertiary, ...); each class declares only what the reference specifies.
- themes.css — theme bindings (light, dark, declared modes) per foundations/implementation.md. Alias themes ({ alias: <target> }, no modes) emit no standalone block — graft the alias selector onto every rule of its target as a grouped selector. Read the alias map from data.
- switcher.js — the theme + mode resolution script from foundations/implementation.md §9 (root data-theme / data-mode toggling), as a standalone file the galleries can inline.
- manifest.json — exact shape from the skill (use generated_at = "1970-01-01T00:00:00Z"; clock access is forbidden).
- GAPS.md — bullets: every component family too thin to fully render (and what was missing), every role with no fallback, any YAML/schema mismatch.

CRITICAL: Do NOT halt on MISSING_SPEC. This system is WIP and specs will be thin. Emit the best correct CSS you can for everything; for thin specs emit a minimal sensible class and record it in GAPS.md + gaps[].

Return: files written; the full component_families list (name as in components.md, the kebab className you emitted, and its section like "§12"); theme_selectors with modes; a one-line token_summary; gaps[].`, { schema: FOUNDATION_SCHEMA, phase:'Foundation', label:'generate-stylesheets' })

// ---------- Phase 2: Components ----------
phase('Components')
const fams = foundation.component_families || []
const groups = chunk(fams, 5)
const comps = await parallel(groups.map((g,i)=> ()=> agent(`${COMMON}

TASK: For each component family below, produce ONE self-contained markup FRAGMENT (inner HTML only — no <html>/<head>/<body>/<style>; the gallery inlines the CSS). Write each to ${R}/components/<className>.html .
Families (name | className | section in components.md):
${g.map(c=>`- ${c.name} | ${c.className} | ${c.section}`).join('\n')}

For each: read its entry in ${P}/reference/components.md (locate by section + name) and the real class in ${R}/styles/components.css. Render the component with realistic neutral sample content. Where the reference defines variants/states (e.g. primary/secondary/disabled, hover, active, sizes), show each variant side by side so they can be reviewed. Wrap each component's fragment in a <div class="cds-specimen" data-component="<className>"> so the gallery can label it; put nothing else outside that.
Return written[] ({className,file}) and gaps[].`, { schema: COMP_SCHEMA, phase:'Components', label:'components '+(i+1) })))

// ---------- Phase 3: Shapes (one artifact per S0-S28) ----------
phase('Shapes')
const shapes = await parallel(SHAPES.map(([id,name])=> ()=> agent(`${COMMON}

TASK: Build the PREGENERATED SHAPE ARTIFACT for ${id} — "${name}".
A shape is an organized, content-agnostic spatial arrangement of components for one landing-page section. Read:
- ${P}/reference/shapes.md  (find the ${id} row in Part A; honor any per-shape layout detail: column counts, padding, alignment, responsive-collapse, radius)
- ${P}/skills/compose-page/reference/landing-sections-shape-rules.md  (Part C decision table — which section types pick ${id}, and what content_meta triggers it)
- ${R}/styles/components.css + the fragments already in ${R}/components/  (reuse the real component classes/markup so the shape is consistent with the atoms)
- ${P}/reference/foundations/layout.md + responsive.md for grid/spacing/breakpoints.

Output: ONE self-contained markup FRAGMENT (inner HTML only, no <html>/<style>) at ${R}/shapes/${id}.html, filled with realistic neutral sample content so it renders meaningfully. It must be content-agnostic in structure (a real arrangement, not a one-off). Wrap it in <section class="cds-shape" data-shape="${id}"> ... </section> and nothing else outside that. Use role tokens for every color; never hardcode a hex.
Return id, name, file, sections_using[] (the T# section types whose picker can select ${id}), components_used[] (classNames), gaps[].`, { schema: SHAPE_SCHEMA, phase:'Shapes', label:id })))

// ---------- Phase 4: Sample landing page ----------
phase('Landing')
const okShapes = shapes.filter(Boolean)
const landing = await agent(`${COMMON}

TASK: Compose ONE full, self-contained standalone landing page at ${R}/landing.html that demonstrates the system end to end.
Read:
- ${P}/reference/page-types.md  (Primary Landing Page: section sequence T1-T18, layout, typography, component, theme/mode rules, and the alternating-background rules)
- ${P}/skills/compose-page/reference/landing-sections-shape-rules.md  (§19.1 Variety Principle, §19.2 first/second section background rule, Part C picker)
- The pregenerated shape fragments in ${R}/shapes/  (reuse them; these shapes already exist: ${okShapes.map(s=>s.id).join(', ')})

Build a realistic multi-section landing page (at minimum: Hero, Trust Strip, Capability Showcase, a Workflow or Demo, Pricing, FAQ, Final CTA, Footer). For each section pick an appropriate shape via the picker and place it. APPLY the variety principle (no two adjacent sections look alike) and the §19.2 alternating-background rule (carry themes per section). This is a FULL standalone HTML document: in <head> inline ${R}/styles/tokens.css, components.css, themes.css inside one <style>, then inline ${R}/styles/switcher.js, and add a fixed top switch-bar with a button per theme_selector (${(foundation.theme_selectors||[]).map(t=>t.name).join(', ')}) plus light/dark toggle, so the whole page re-skins on click. No provenance metadata in the output.
Return file, section_sequence[] ({section, shape, theme}), notes, gaps[].`, { schema: LANDING_SCHEMA, phase:'Landing', label:'landing' })

return {
  foundation: { files: foundation.files, families: (foundation.component_families||[]).length, themes: foundation.theme_selectors, gaps: foundation.gaps },
  components: comps.filter(Boolean).flatMap(c=>c.written),
  component_gaps: comps.filter(Boolean).flatMap(c=>c.gaps),
  shapes: okShapes.map(s=>({id:s.id, file:s.file, sections:s.sections_using, gaps:s.gaps})),
  landing,
}
