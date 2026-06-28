export const meta = {
  name: 'cds-render-proof',
  description: 'Regenerate the CDS visual render-proof from the live config and reference tree: real stylesheets, one markup fragment per component family, one artifact per semantic shape (read from shapes.md Part A — never hardcoded), and a sample landing page; then verify (deterministic checks) and assemble the browsable galleries. All output lands in the gitignored test/visual-proof-out/. This is the single entry: regenerate -> verify -> assemble.',
  phases: [
    { title: 'Catalog', detail: 'Read shapes.md Part A -> the semantic shape list (name + one-line description); no hardcoded shape ids' },
    { title: 'Foundation', detail: 'Execute generate-stylesheets on the live YAML -> tokens/components/themes.css + switcher.js + manifest.json; return the class vocabulary' },
    { title: 'Components', detail: 'One real markup fragment per component family, using the generated classes' },
    { title: 'Shapes', detail: 'One pregenerated artifact per semantic shape: real component arrangement with realistic sample content' },
    { title: 'Landing', detail: 'Compose a full sample landing page with alternating sections and the variety principle' },
    { title: 'Verify & assemble', detail: 'Run the deterministic checks, then assemble.py to build the browsable galleries' },
  ],
}

// Caller passes absolute paths only. The output directory is DERIVED from the
// test dir so it can never drift from where assemble.py / run-tests.sh look:
// the gitignored test/visual-proof-out/.
const P = args && args.plugin     // plugins/cds (plugin root)
const YAML = args && args.yaml    // live elements YAML
const TEST = args && args.test    // plugins/cds/test (holds assemble.py, check-plugin.py, checks/)
// Fail loudly if args arrived malformed (e.g. passed as a JSON STRING instead of
// a JSON value — then args.* are all undefined). Without this the paths become
// "undefined/..." and agents silently write output to the wrong place.
if (!P || !YAML || !TEST) {
  throw new Error(`cds-render-proof: args must be a JSON OBJECT with absolute {plugin, yaml, test} paths. Got plugin=${P}, yaml=${YAML}, test=${TEST}. (Pass args as a JSON value, not a stringified JSON.)`)
}
const R = `${TEST}/visual-proof-out`

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
- Do NOT embed provenance/metadata comments in the markup, and do NOT write any GAPS/notes/audit file. Clean markup only.
- If a spec in the reference is too thin to build something correctly, build the best minimal sensible version AND report it in your returned gaps[] (which is orchestration data, never written to a file).`

const CATALOG_SCHEMA = {
  type:'object', additionalProperties:false, required:['shapes'],
  properties:{ shapes:{type:'array',items:{type:'object',additionalProperties:false,required:['name','description'],properties:{name:{type:'string'},description:{type:'string'}}}} },
}
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
const SHAPE_SCHEMA = { type:'object', additionalProperties:false, required:['name','file','sections_using','components_used','gaps'], properties:{ name:{type:'string'}, file:{type:'string'}, sections_using:{type:'array',items:{type:'string'}}, components_used:{type:'array',items:{type:'string'}}, gaps:{type:'array',items:{type:'string'}} } }
const LANDING_SCHEMA = { type:'object', additionalProperties:false, required:['file','section_sequence','gaps'], properties:{ file:{type:'string'}, section_sequence:{type:'array',items:{type:'object',additionalProperties:false,required:['section','shape','theme'],properties:{section:{type:'string'},shape:{type:'string'},theme:{type:'string'}}}}, notes:{type:'string'}, gaps:{type:'array',items:{type:'string'}} } }
const VERIFY_SCHEMA = { type:'object', additionalProperties:false, required:['checks_passed','assemble_ok','output'], properties:{ checks_passed:{type:'boolean'}, assemble_ok:{type:'boolean'}, output:{type:'string'} } }

function chunk(a,n){ const o=[]; for(let i=0;i<a.length;i+=n) o.push(a.slice(i,i+n)); return o }

// ---------- Phase 1: Catalog (derive the shape list from the reference) ----------
// The shape vocabulary is read from shapes.md Part A, never hardcoded — so adding
// or renaming a shape in the reference flows through with no script edit, and the
// retired S0-S28 ids can never creep back in.
phase('Catalog')
const catalog = await agent(`Read ${P}/reference/shapes.md and return its "Part A — Catalog" table as data.
Part A is a markdown table. Each data row's first cell is the shape's semantic kebab-case name (e.g. heading-strip, centered-stack, split-text-media) and the second cell is its one-line name/description. Return EVERY data row in document order.
Do NOT include the table header row. Do NOT invent or include any S#/numeric ids — those are retired; only the semantic names exist now. Return exactly what Part A lists.`, { schema: CATALOG_SCHEMA, phase:'Catalog', label:'shape catalog' })
const SHAPES = catalog.shapes || []
log(`shape catalog: ${SHAPES.length} semantic shapes (${SHAPES.map(s=>s.name).slice(0,4).join(', ')}, ...)`)

// ---------- Phase 2: Foundation ----------
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

Do NOT write a GAPS.md or any other notes/audit file. Report gaps ONLY in the returned gaps[] field below.

CRITICAL: Do NOT halt on MISSING_SPEC. This system is WIP and specs will be thin. Emit the best correct CSS you can for everything; for thin specs emit a minimal sensible class and record it in the returned gaps[].

Return: files written; the full component_families list (name as in components.md, the kebab className you emitted, and its section like "§12"); theme_selectors with modes; a one-line token_summary; gaps[].`, { schema: FOUNDATION_SCHEMA, phase:'Foundation', label:'generate-stylesheets' })

// ---------- Phase 3: Components ----------
phase('Components')
const fams = foundation.component_families || []
const groups = chunk(fams, 5)
const comps = await parallel(groups.map((g,i)=> ()=> agent(`${COMMON}

TASK: For each component family below, produce ONE self-contained markup FRAGMENT (inner HTML only — no <html>/<head>/<body>/<style>; the gallery inlines the CSS). Write each to ${R}/components/<className>.html .
Families (name | className | section in components.md):
${g.map(c=>`- ${c.name} | ${c.className} | ${c.section}`).join('\n')}

For each: read its entry in ${P}/reference/components.md (locate by section + name) and the real class in ${R}/styles/components.css. Render the component with realistic neutral sample content. Where the reference defines variants/states (e.g. primary/secondary/disabled, hover, active, sizes), show each variant side by side so they can be reviewed. Wrap each component's fragment in a <div class="cds-specimen" data-component="<className>"> so the gallery can label it; put nothing else outside that.
Return written[] ({className,file}) and gaps[].`, { schema: COMP_SCHEMA, phase:'Components', label:'components '+(i+1) })))

// ---------- Phase 4: Shapes (one artifact per semantic shape) ----------
phase('Shapes')
const shapes = await parallel(SHAPES.map(s=> ()=> agent(`${COMMON}

TASK: Build the PREGENERATED SHAPE ARTIFACT for "${s.name}" — ${s.description}.
A shape is an organized, content-agnostic spatial arrangement of components for one landing-page section. Read:
- ${P}/reference/shapes.md  (find the "${s.name}" section; honor its per-shape layout detail: slots, column counts, padding, alignment, responsive-collapse, radius, and its Determinations)
- ${P}/skills/compose-page/reference/landing-sections-shape-rules.md  (Part C decision table — which section types pick "${s.name}", and what content_meta triggers it)
- ${R}/styles/components.css + the fragments already in ${R}/components/  (reuse the real component classes/markup so the shape is consistent with the atoms)
- ${P}/reference/foundations/layout.md + responsive.md for grid/spacing/breakpoints.

Output: ONE self-contained markup FRAGMENT (inner HTML only, no <html>/<style>) at ${R}/shapes/${s.name}.html, filled with realistic neutral sample content so it renders meaningfully. It must be content-agnostic in structure (a real arrangement, not a one-off). Wrap it in <section class="cds-shape" data-shape="${s.name}"> ... </section> and nothing else outside that. Use role tokens for every color; never hardcode a hex.
Return name ("${s.name}"), file, sections_using[] (the section types whose picker can select "${s.name}"), components_used[] (classNames), gaps[].`, { schema: SHAPE_SCHEMA, phase:'Shapes', label:s.name })))

// ---------- Phase 5: Sample landing page ----------
phase('Landing')
const okShapes = shapes.filter(Boolean)
const landing = await agent(`${COMMON}

TASK: Compose ONE full, self-contained standalone landing page at ${R}/landing.html that demonstrates the system end to end.
Read:
- ${P}/reference/page-types.md  (Primary Landing Page: section sequence, layout, typography, component, theme/mode rules, and the alternating-background rules)
- ${P}/skills/compose-page/reference/landing-sections-shape-rules.md  (Variety Principle, the first/second section background rule, Part C picker)
- The pregenerated shape fragments in ${R}/shapes/  (reuse them; these shapes already exist: ${okShapes.map(s=>s.name).join(', ')})

Build a realistic multi-section landing page (at minimum: Hero, Trust Strip, Capability Showcase, a Workflow or Demo, Pricing, FAQ, Final CTA, Footer). For each section pick an appropriate shape via the picker and place it. Include the §12.1 topbar with the nav right-aligned (logo left; nav + CTA grouped right; never centered, never justify-content: space-between) and at least ONE primary-nav dropdown trigger (aria-haspopup="menu" + aria-expanded) opening a §12.2 role="menu" panel, so the artifact exercises the dropdown contract. APPLY the variety principle (no two adjacent sections look alike) and the alternating-background rule (carry themes per section). This is a FULL standalone HTML document: in <head> inline ${R}/styles/tokens.css, components.css, themes.css inside one <style>, then inline ${R}/styles/switcher.js, and add a fixed top switch-bar with a button per theme_selector (${(foundation.theme_selectors||[]).map(t=>t.name).join(', ')}) plus light/dark toggle, so the whole page re-skins on click. No provenance metadata or notes files in the output.
Return file, section_sequence[] ({section, shape, theme}), notes, gaps[].`, { schema: LANDING_SCHEMA, phase:'Landing', label:'landing' })

// ---------- Phase 6: Verify & assemble (the single entry does everything) ----------
phase('Verify & assemble')
const verify = await agent(`Run these commands in order in a shell and report the results. Do NOT edit any files — you are only verifying and assembling.
1. python3 ${TEST}/check-plugin.py
2. python3 ${P}/validation/lint-elements.py ${YAML}
3. python3 ${TEST}/assemble.py
Command 3 (assemble.py) is a viewer-only script: it reads the artifacts just generated in ${R}/ and builds the browsable galleries (index.html, components.html, shapes.html) next to them.
Return: checks_passed (true ONLY if commands 1 AND 2 both exit 0), assemble_ok (true if command 3 exits 0), and output (the tail of combined stdout/stderr — include every FAILURE/✗ line verbatim).`, { schema: VERIFY_SCHEMA, phase:'Verify & assemble', label:'verify+assemble' })

return {
  output_dir: R,
  shape_catalog: SHAPES.map(s=>s.name),
  foundation: { files: foundation.files, families: (foundation.component_families||[]).length, themes: foundation.theme_selectors, gaps: foundation.gaps },
  components: comps.filter(Boolean).flatMap(c=>c.written),
  component_gaps: comps.filter(Boolean).flatMap(c=>c.gaps),
  shapes: okShapes.map(s=>({name:s.name, file:s.file, sections:s.sections_using, gaps:s.gaps})),
  landing,
  verify,
}
