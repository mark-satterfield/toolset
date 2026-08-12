export const meta = {
  name: 'cds-render-proof',
  description: 'Regenerate the CDS visual render-proof from the live config and reference tree: real stylesheets, one markup fragment per Component entry, one artifact per Shape entry, and a sample landing page; then verify (deterministic checks) and assemble the browsable galleries. The Component and Shape lists are ENUMERATED from reference/libraries/ every run — never hardcoded, never read from an index file — so every entry in the library is rendered, and a new entry is covered the day it lands. All output lands in the gitignored test/visual-proof-out/. This is the single entry: regenerate -> verify -> assemble.',
  phases: [
    { title: 'Enumerate', detail: 'Glob reference/libraries/{components,shapes}/ -> the full entry list; nothing hardcoded' },
    { title: 'Foundation', detail: 'Execute generate-css on the live YAML -> tokens/components/themes.css + switcher.js + manifest.json' },
    { title: 'Components', detail: 'One real markup fragment per Component entry, using the generated classes' },
    { title: 'Shapes', detail: 'One artifact per Shape entry: real component arrangement with realistic sample content' },
    { title: 'Landing', detail: 'Compose a full sample landing page from the primary-landing Page entry' },
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
CONTEXT — the Configurable Design System (CDS), a brand-neutral design system plugin. Absolute paths:
- Plugin root: ${P}
- Normative entity model: ${P}/reference/model/entity-catalog.md — read it in full before resolving any Building Blocks term.
- The library (authoritative source of truth for entries): ${P}/reference/libraries/{components,shapes,sections,pages}/ and ${P}/reference/rules/{shape-selection,page-constraints}/ — one .md file per entry, format in ${P}/reference/libraries/FORMAT.md
- Foundations: ${P}/reference/foundations/*.md  ·  Build pipeline: ${P}/reference/pipeline.md  ·  Compliance: ${P}/reference/compliance.md
- Generated stylesheets (already written by the Foundation phase): ${R}/styles/tokens.css, components.css, themes.css
RULES that apply to every artifact you write:
- Read only the library entries your own task names. Do not survey the library.
- Use ONLY the real kebab-case class names that exist in ${R}/styles/components.css and the role/token names in tokens.css. Read those files first. Never invent a class or hardcode a hex/color — colors come from role tokens only.
- Content must be brand-neutral and realistic (no real company/product names). Plausible placeholder copy, not lorem ipsum.
- Honor the accessibility contracts (ARIA roles/labels, keyboard semantics) from ${P}/reference/foundations/accessibility.md and the Component entries.
- Do NOT embed provenance/metadata comments in the markup, and do NOT write any GAPS/notes/audit file. Clean markup only.
- If an entry is too thin to build something correctly, build the best minimal sensible version AND report it in your returned gaps[] (which is orchestration data, never written to a file).`

const ENTRY_LIST = { type:'object', additionalProperties:false, required:['name','description'], properties:{ name:{type:'string'}, description:{type:'string'} } }
const CATALOG_SCHEMA = {
  type:'object', additionalProperties:false, required:['components','shapes'],
  properties:{ components:{type:'array',items:ENTRY_LIST}, shapes:{type:'array',items:ENTRY_LIST} },
}
const FOUNDATION_SCHEMA = {
  type:'object', additionalProperties:false,
  required:['files','theme_selectors','gaps'],
  properties:{
    files:{type:'array',items:{type:'string'}},
    theme_selectors:{type:'array',items:{type:'object',additionalProperties:false,required:['name','modes'],properties:{name:{type:'string'},modes:{type:'array',items:{type:'string'}}}}},
    token_summary:{type:'string'},
    gaps:{type:'array',items:{type:'string'}},
  },
}
const COMP_SCHEMA = { type:'object', additionalProperties:false, required:['written','gaps'], properties:{ written:{type:'array',items:{type:'object',additionalProperties:false,required:['className','file'],properties:{className:{type:'string'},file:{type:'string'}}}}, gaps:{type:'array',items:{type:'string'}} } }
const SHAPE_SCHEMA = { type:'object', additionalProperties:false, required:['name','file','components_used','gaps'], properties:{ name:{type:'string'}, file:{type:'string'}, sections_using:{type:'array',items:{type:'string'}}, components_used:{type:'array',items:{type:'string'}}, gaps:{type:'array',items:{type:'string'}} } }
const LANDING_SCHEMA = { type:'object', additionalProperties:false, required:['file','section_sequence','gaps'], properties:{ file:{type:'string'}, section_sequence:{type:'array',items:{type:'object',additionalProperties:false,required:['section','shape','theme'],properties:{section:{type:'string'},shape:{type:'string'},theme:{type:'string'}}}}, notes:{type:'string'}, gaps:{type:'array',items:{type:'string'}} } }
const VERIFY_SCHEMA = { type:'object', additionalProperties:false, required:['checks_passed','assemble_ok','output'], properties:{ checks_passed:{type:'boolean'}, assemble_ok:{type:'boolean'}, output:{type:'string'} } }

function chunk(a,n){ const o=[]; for(let i=0;i<a.length;i+=n) o.push(a.slice(i,i+n)); return o }

// ---------- Phase 1: Enumerate (the library IS the list) ----------
// Both lists come from a directory listing, so every entry in the library is
// rendered every run and a new entry needs no script edit. No index file is
// consulted — an index would be a second source of truth that goes stale.
phase('Enumerate')
const catalog = await agent(`List the CDS library entries by globbing the filesystem — do not read an index file and do not use any remembered list.

1. Glob ${P}/reference/libraries/components/*.md — EVERY file is one Component entry. Skip only FORMAT.md and CONVENTIONS.md if present.
2. Glob ${P}/reference/libraries/shapes/*.md — EVERY file is one Shape entry. Skip only FORMAT.md and CONVENTIONS.md if present.

For each entry return its \`name:\` frontmatter value (fall back to the basename without .md) and a one-line description taken from its frontmatter description or its first body sentence.
Return every entry found, in filename order. The counts you return must equal the number of .md files in each directory.`,
  { schema: CATALOG_SCHEMA, phase:'Enumerate', label:'library enumeration' })

const COMPONENTS = catalog.components || []
const SHAPES = catalog.shapes || []
log(`library: ${COMPONENTS.length} Components, ${SHAPES.length} Shapes — every entry gets an artifact`)

// ---------- Phase 2: Foundation ----------
phase('Foundation')
const foundation = await agent(`You are executing the CDS plugin's generate-css skill against its live config. The skill is Markdown instructions — executing them faithfully IS running the skill. Do NOT write a Python/JS program that recomputes CSS; read the YAML + reference and emit CSS by following the instructions.

Follow step by step: ${P}/skills/generate-css/SKILL.md
Elements YAML: ${YAML}
Reference: ${P}/reference/ (read foundations/* and the ${P}/reference/libraries/components/ entries as the skill directs)
Schema: ${P}/validation/customizable-design-elements.schema.json
OUTPUT DIR (create, write here): ${R}/styles/

Emit exactly what the skill's Pipeline specifies: tokens.css, components.css, themes.css, switcher.js, and manifest.json (use generated_at = "1970-01-01T00:00:00Z"; clock access is forbidden). One class per Component entry, kebab-case identifiers mirroring role/component names; each class declares only what its entry specifies. Alias themes ({ alias: <target> }, no modes) emit no standalone block — graft the alias selector onto every rule of its target as a grouped selector.

Do NOT write a GAPS.md or any other notes/audit file. Report gaps ONLY in the returned gaps[] field.
CRITICAL: Do NOT halt on MISSING_SPEC. Emit the best correct CSS you can for everything; for thin entries emit a minimal sensible class and record it in gaps[].

Return: files written; theme_selectors with modes; a one-line token_summary; gaps[].`, { schema: FOUNDATION_SCHEMA, phase:'Foundation', label:'generate-css' })

// ---------- Phase 3: Components (one fragment per entry, all of them) ----------
phase('Components')
const comps = await parallel(chunk(COMPONENTS, 5).map((g,i)=> ()=> agent(`${COMMON}

TASK: For each Component entry below, produce ONE self-contained markup FRAGMENT (inner HTML only — no <html>/<head>/<body>/<style>; the gallery inlines the CSS). Write each to ${R}/components/<entry-name>.html .
Entries:
${g.map(c=>`- ${c.name} — ${c.description}`).join('\n')}

For each: read ${P}/reference/libraries/components/<name>.md (its slots, sizing rules, behavior contract, accessibility contract, and token bindings) and the real class in ${R}/styles/components.css. Render it with realistic neutral sample content. Where the entry defines variants or states, show each side by side so they can be reviewed. Wrap each fragment in <div class="cds-specimen" data-component="<name>"> and put nothing else outside that.
Return written[] ({className,file}) and gaps[].`, { schema: COMP_SCHEMA, phase:'Components', label:'components '+(i+1) })))

// ---------- Phase 4: Shapes (one artifact per entry, all of them) ----------
phase('Shapes')
const shapes = await parallel(SHAPES.map(s=> ()=> agent(`${COMMON}

TASK: Build the render artifact for the Shape "${s.name}" — ${s.description}.
A Shape is a template layout positioning Components and Elements inside one Frame — any Section, on any page family, or a Shell region. It is an arrangement, not a page-family-specific asset. Read:
- ${P}/reference/libraries/shapes/${s.name}.md — its slots, arrangement (STATIC or ORDERED), variants, self_contained flag, and its Determinations
- ${R}/styles/components.css + the fragments already in ${R}/components/ — reuse the real component classes so the Shape is consistent with the atoms
- ${P}/reference/foundations/layout.md + responsive.md for grid/spacing/breakpoints

Output: ONE self-contained markup FRAGMENT (inner HTML only, no <html>/<style>) at ${R}/shapes/${s.name}.html, filled with realistic neutral sample content so it renders meaningfully. Wrap it in <section class="cds-shape" data-shape="${s.name}"> ... </section> and nothing else outside that. Use role tokens for every color; never hardcode a hex.
Return name ("${s.name}"), file, sections_using[] (Section entries whose rule can select it, if any), components_used[], gaps[].`, { schema: SHAPE_SCHEMA, phase:'Shapes', label:s.name })))

// ---------- Phase 5: Sample landing page ----------
phase('Landing')
const okShapes = shapes.filter(Boolean)
const landing = await agent(`${COMMON}

TASK: Compose ONE full, self-contained standalone landing page at ${R}/landing.html that demonstrates the system end to end.
Read:
- ${P}/reference/libraries/pages/primary-landing.md — its ordered \`sections\` list, its page family, and the constraints it references
- ${P}/reference/rules/page-constraints/ — the constraint entries scoped to the landing family (the post-selection rejection loop)
- ${P}/reference/rules/shape-selection/ — the rule for each lazily-assigned Section in that list
- ${P}/reference/pipeline.md — the Shape-assignment waterfall
- The shape fragments already in ${R}/shapes/ (reuse them): ${okShapes.map(s=>s.name).join(', ')}

Build the page from the Page entry's own Section sequence — do not invent a different one. For each Section resolve its Shape (eager \`shape:\` frontmatter, else its ShapeSelectionRule validated against the constraints) and place it. Include the top-nav Section with at least ONE primary-nav dropdown trigger (aria-haspopup="menu" + aria-expanded) opening a role="menu" panel, so the artifact exercises the dropdown contract. This is a FULL standalone HTML document: in <head> inline ${R}/styles/tokens.css, components.css, themes.css inside one <style>, then inline ${R}/styles/switcher.js, and add a fixed top switch-bar with a button per theme (${(foundation.theme_selectors||[]).map(t=>t.name).join(', ')}) plus a light/dark toggle, so the whole page re-skins on click. No provenance metadata and no notes files.
Return file, section_sequence[] ({section, shape, theme}), notes, gaps[].`, { schema: LANDING_SCHEMA, phase:'Landing', label:'landing' })

// ---------- Phase 6: Verify & assemble (the single entry does everything) ----------
phase('Verify & assemble')
const verify = await agent(`Run these commands in order in a shell and report the results. Do NOT edit any files — you are only verifying and assembling.
1. python3 ${TEST}/check-plugin.py
2. python3 ${P}/validation/lint-elements.py ${YAML}
3. python3 ${TEST}/assemble.py
Command 3 (assemble.py) is a viewer-only script: it reads the artifacts just generated in ${R}/ and builds the browsable galleries (index.html, components.html, shapes.html) next to them.
Return: checks_passed (true ONLY if commands 1 AND 2 both exit 0), assemble_ok (true if command 3 exits 0), and output (the tail of combined stdout/stderr — include every FAILURE/✗ line verbatim).`, { schema: VERIFY_SCHEMA, phase:'Verify & assemble', label:'verify+assemble' })

// Coverage is reported, never silently trimmed: a rendered count below the
// enumerated count means entries failed, not that the library is smaller.
const renderedComponents = comps.filter(Boolean).flatMap(c=>c.written)
if (renderedComponents.length < COMPONENTS.length) log(`WARNING: ${COMPONENTS.length - renderedComponents.length} Component entries produced no fragment`)
if (okShapes.length < SHAPES.length) log(`WARNING: ${SHAPES.length - okShapes.length} Shape entries produced no artifact`)

return {
  output_dir: R,
  coverage: { components: `${renderedComponents.length}/${COMPONENTS.length}`, shapes: `${okShapes.length}/${SHAPES.length}` },
  foundation: { files: foundation.files, themes: foundation.theme_selectors, gaps: foundation.gaps },
  components: renderedComponents,
  component_gaps: comps.filter(Boolean).flatMap(c=>c.gaps),
  shapes: okShapes.map(s=>({name:s.name, file:s.file, sections:s.sections_using, gaps:s.gaps})),
  landing,
  verify,
}
