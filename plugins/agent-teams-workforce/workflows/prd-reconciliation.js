export const meta = {
  name: 'prd-reconciliation',
  description:
    'Leaf mini — PRD Reconciliation. ONE independent read-only checker session takes an INVENTORY of the material that already exists for a PRD, and detects upstream dependency changes, in a single pass. THE PRD IS CANONICAL: what already ships is material, not authority — where it conforms to the PRD it is reused, where it contradicts the PRD it is removed, and where nothing exists it is built. No requirement is ever filtered out, narrowed, deferred, or written off because code exists, and the inventory is context for the phases downstream, never a filter on their scope. EVERY requirement the PRD states comes back with a status; a conforms/contradicts claim with no file:line, URL, endpoint or arn:aws behind it is demoted to absent, because reusing material that may not match the PRD is the expensive error. UI requirements are resolved against the cds design system, which is the authority for layout, shells, navigation, components and interaction: the hand-off bundle first (a packaged artifact carries a build-spec the app repo builds to), then the loose composed mock, then the PRD prose, and what is deployed is never authoritative — a deployed UI that differs from the packaged artifact is material to bring into line, never an open question. Read-only: it writes no document at all and returns structured output only.',
  phases: [
    { title: 'Reconciliation checks', detail: 'one independent read-only checker session inventories the material and checks upstream dependencies' },
  ],
}

// args: {
//   prd: {                      // the PRD being reconciled against reality (required)
//     id?: string,
//     title?: string,
//     body: string,             // the PRD text — required; a path alone cannot be read by a script
//     path?: string,            // where the PRD document lives
//     repoPath?: string,        // the repo the PRD nominally targets
//   },
//   repos?: string[],           // every repo the PRD may span
//   mocksDir?: string,          // cds design mocks directory; derived from repoPath when absent
//   packagesDir?: string,       // cds hand-off bundle root (holds batch-* dirs); derived likewise
//   dependencies?: string[],    // upstream contracts/schemas/libs the PRD assumes
//   awsProfile?: string,        // AWS profile for live-endpoint checks (default 'dev')
// }
//
// WHY THIS MINI EXISTS
//
// Nothing upstream of specification establishes what already exists, so the pipeline
// walks into a codebase blind: it re-specifies capabilities that already ship, and it
// leaves in place code that the PRD has since moved past. An audit of 20 Epics in one
// project found ELEVEN written as greenfield against behaviour that was already there —
// a 929-line MFA implementation that was merely disabled, a fully deployed passkey
// ceremony, three live OAuth providers, a shipped session dashboard.
//
// So the pipeline establishes what exists FIRST. It does that to spend the existing
// material well, not to shrink the ask:
//
//   - material that CONFORMS to the PRD is REUSED — the spec builds on it instead of
//     re-deriving it, and decomposition emits no task to write it again;
//   - material that CONTRADICTS the PRD is REMOVED — the PRD is the latest statement of
//     what the product is, so the deployed thing is what is wrong, and removing it is
//     real work that has to reach decomposition like any other;
//   - where nothing exists, it is built.
//
// The PRD is canonical and delivered code never subtracts from it. A requirement is
// never dropped, narrowed or deferred because something was already built, and no work
// item is closed on the grounds that code exists. When the PRD and the deployed system
// disagree, that is SETTLED BY DEFINITION in the PRD's favour: it convenes no panel, it
// raises no architecture question, and it generates removal work.
//
// The same holds one level down for the interface. A UI/UX difference is never an
// architecture decision — layout, shells, navigation shape, components, visual design
// and interaction patterns are settled by the design system, and the cds output is the
// authority for that above any other documentation. It comes in two grades: the
// `package-change` HAND-OFF BUNDLE under `design-mocks/packages/batch-*/`, where each
// artifact carries the `build-spec.md` the app repo builds to, and the loose composed
// mocks under `design-mocks/{shells,pages,views}/` for artifacts not yet packaged. So a
// deployed screen that differs from its packaged artifact is material to bring into line
// rather than a competing option to adjudicate — and an artifact missing from the bundle
// is unpackaged, not undecided, which falls back to the mock and blocks nothing.
//
// One bundle has existed since 2026-08-19 and the pipeline had never looked at it: 205
// artifacts, 23 of them the settings screens an Epic once spent 45 minutes convening an
// architecture panel to choose a shell for.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const prdInput = a.prd || {}
const prdBody = typeof prdInput === 'string' ? prdInput : prdInput.body || ''
const prdId = (typeof prdInput === 'string' ? '' : prdInput.id) || ''
const prdTitle = (typeof prdInput === 'string' ? '' : prdInput.title) || ''
const repoPath = (typeof prdInput === 'string' ? '' : prdInput.repoPath) || a.repoPath || ''
const repos = (Array.isArray(a.repos) && a.repos.length ? a.repos : [repoPath]).filter((r) => r)
const dependencies = Array.isArray(a.dependencies) ? a.dependencies : []
const awsProfile = a.awsProfile || 'dev'
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
// The design system's output is the UI authority, so the reconciler is told where to
// find it rather than left to guess. Two locations, and the ORDER between them matters:
// the cds `package-change` skill produces a HAND-OFF BUNDLE — the boundary between
// "approved in cds" and "built in the app repo" — and a bundled artifact carries a
// build-spec the loose mock does not. So the bundle outranks the mocks, and the mocks
// outrank the PRD's prose about layout. A caller may name either directory outright;
// otherwise both sit under the repo the run operates on, and the reconciler resolves the
// environment overrides (CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR, then
// CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR / _SHELLS_DIR) when they are set.
//
// The bundle ROOT holds dated `batch-*` directories; picking the most recent one is a
// directory listing, which a workflow script cannot do — so the root is threaded here and
// the reconciler selects the batch.
const repoRoot = hasText(repoPath) ? repoPath.replace(/\/+$/, '') : ''
const mocksDir = hasText(a.mocksDir) ? a.mocksDir.trim() : repoRoot ? `${repoRoot}/design-mocks` : ''
const packagesDir = hasText(a.packagesDir) ? a.packagesDir.trim() : mocksDir ? `${mocksDir}/packages` : ''

// ── Standing rulings from the project owner ─────────────────────────────────────
// Injected into JUDGMENT prompts only (never mechanical plumbing). The composite
// resolves .claude/standing-rulings.md in the repo the run operates on and threads
// the text here; absent -> empty string, zero behavior change. Capped so a bloated
// file cannot blow up every brief.
const RULINGS_CAP = 8192
const rulingsText = typeof a.standingRulings === 'string' ? a.standingRulings.trim().slice(0, RULINGS_CAP) : ''
const rulingsBlock = rulingsText
  ? `STANDING RULINGS FROM THE PROJECT OWNER — these outrank any document they contradict (PRD, SAD, TRD, spec, bead text). Where a ruling applies to your task, apply it, and CITE the ruling in your output (e.g. "dropped migration requirement per standing ruling dev-env-no-preservation") so the trace shows the ruling working.

${rulingsText}

END STANDING RULINGS

`
  : ''

// ── A DEAD DISPATCH ARRIVES AS A THROW, NOT AS A NULL ───────────────────────────
//
// This mini was written against one runtime behaviour and meets two. `agent()` hands
// back NULL when a subagent is skipped or dies on a terminal API error, and the
// `!reality` guard below was built for exactly that. But a subagent that RUNS and then
// finishes WITHOUT emitting its structured output THROWS, and the throw leaves the mini,
// leaves the composite, and aborts the whole run — the same crash bug-fix.js records at
// 1.13M tokens on ssbd-mqkq. Nothing catches it here, so every line below, including the
// entire `dispatchFailed` contract this mini owes its caller, is unreachable for the
// failure mode that actually happens. ssbd-nc8z died this way twice, at the same phase,
// and both times the supervisor was handed a bare abort with no classification.
//
// So dispatch through here. A throw and a null are the same event — "no account came
// back" — and both must reach the guards as null so the caller learns it was the
// ENVIRONMENT that failed and not the PRD.
//
// The single retry is the other half. A reconciliation cannot degrade: proceeding
// without knowing what already exists is precisely the blind assumption this phase
// exists to remove, so a dead dispatch has no fallback except to run again. One extra
// attempt is the difference between a coin-flip and a phase that completes; more than
// one turns a systematic failure into an expensive systematic failure.
const MAX_DISPATCH_ATTEMPTS = 2
const dispatchNotes = []

async function dispatch(label, prompt, opts) {
  let why = null
  for (let attempt = 1; attempt <= MAX_DISPATCH_ATTEMPTS; attempt++) {
    let out = null
    try {
      out = await agent(prompt, opts)
    } catch (e) {
      out = null
      why = `threw: ${e && e.message ? e.message : String(e)}`
    }
    if (out) return out
    if (!why) why = 'returned nothing — skipped, or died on a terminal API error'
    dispatchNotes.push(`${label} attempt ${attempt}/${MAX_DISPATCH_ATTEMPTS} — ${why}`)
    if (attempt < MAX_DISPATCH_ATTEMPTS) log(`${label}: dispatch died (${why}) — dispatching once more.`)
    why = null
  }
  log(`${label}: dispatch failed on all ${MAX_DISPATCH_ATTEMPTS} attempt(s) — ${dispatchNotes[dispatchNotes.length - 1]}`)
  return null
}

// `extra` carries `dispatchFailed` when the failure is a dead agent rather than a
// finding — see the reconciler check below. The caller reads that field to decide
// whether it holds a verdict about the PRD or an account that never came back.
const fail = (reason, extra) => ({
  ok: false,
  reason,
  requirements: [],
  conformsCount: 0,
  contradictsCount: 0,
  absentCount: 0,
  removalWork: [],
  reuseWork: [],
  repos: [],
  existingRepos: [],
  spansMultipleRepos: false,
  architectureNeeded: false,
  architectureQuestions: [],
  uiAuthority: {
    bundlePath: null,
    mocksDir: mocksDir || null,
    artifactsConsulted: [],
    shellsConsulted: [],
    pagesConsulted: [],
  },
  infraOnly: false,
  ...(extra || {}),
})

if (!hasText(prdBody)) {
  // Refuse rather than report an empty inventory. "Nothing was found" and "no PRD was
  // supplied" both reduce to zero requirements, and a caller reading the first as an
  // answer proceeds against a document nobody looked at.
  return fail('prd-reconciliation invoked with an empty PRD body — there is nothing to reconcile against reality.')
}

const prdHeader = `PRD ${prdId}${prdTitle ? `: ${prdTitle}` : ''}`.trim()
const prdBlock = `${prdHeader}\n\n${prdBody}`
const repoBlock = repos.length
  ? repos.map((r, i) => `${i + 1}. ${r}`).join('\n')
  : '(no repo paths supplied — discover the repositories this PRD touches from the PRD text)'

// ── Phase 1: Reconciliation checks — ONE independent checker session, both checks ──
// This used to be two parallel sessions, each paying a full session-start to read the
// same PRD and the same repositories. Both are read-only CHECKS on a document authored
// upstream — neither ever judged the other's output — so one session carrying both
// preserves segregation of duties, and the reduction below still judges no code: it
// applies a fixed rule to the typed findings.
phase('Reconciliation checks')

const combined = await dispatch(
  'reconcile:reality-and-dependencies',
  `${rulingsBlock}Take an INVENTORY of the material that already exists for this PRD, and detect upstream changes that invalidate what it assumes. You are READ-ONLY over the codebase, the design mocks and the cloud account: read, search and query what the inventory needs, but change nothing anywhere and write no document. Two checks, one pass — return both.

═══ THE RULE THAT GOVERNS THIS ENTIRE TASK ═══

THE PRD IS CANONICAL. It is the latest and greatest statement of what the product must
be, and it overrides whatever is deployed today. Code that already ships is MATERIAL,
not authority:

  - material that CONFORMS to the PRD is reused;
  - material that CONTRADICTS the PRD is removed;
  - where nothing exists, it gets built.

You are NOT deciding which requirements survive. EVERY requirement the PRD states comes
back in your inventory with a status. You never drop one, never narrow one, never defer
one, and never mark one no longer applicable — nothing outside the PRD has the standing
to retire a PRD requirement, and that includes you and it includes the deployed system.
If the count of requirements you return is smaller than the count of requirements the PRD
states, you have made an error.

WHEN THE PRD AND THE DEPLOYED SYSTEM DISAGREE, THE PRD WINS, AND THAT IS SETTLED. It is
not an open question, it convenes no panel, and it raises no architecture question. It
produces one thing: removal work, named precisely.

═══ CHECK 1 — the material inventory ═══

${prdBlock}

Repositories in scope:
${repoBlock}

Enumerate EVERY requirement the PRD states, and for each one classify the MATERIAL — what
exists today relative to what the PRD asks for. The status describes the material, not the
requirement's fate:

- conforms    — an implementation exists and it MATCHES what the PRD asks for. It is
                material to REUSE. Name what to reuse in \`conformingMaterial\`, cited.
- contradicts — an implementation exists but it DIFFERS from what the PRD asks for. The
                PRD wins; this is material to REMOVE or replace. Name exactly what must be
                deleted in \`removalTargets\`, cited. Being deployed, being large, or being
                recently written are not reasons to call something conforming.
- absent      — nothing exists. Say what is missing in \`missing\`. It gets built.

Also classify the SURFACE each requirement lives on, in \`surface\`:
  ui | service | infra | data | unknown
This is load-bearing — see check 1b.

EVIDENCE IS MANDATORY AND IT IS THE WHOLE POINT OF THIS CHECK. Every status must cite
concrete evidence: a \`file:line\` you actually read, a URL, a named deployed endpoint you
actually called, or an \`arn:aws\` identifier. A \`conforms\` or \`contradicts\` with nothing
concrete behind it is DISCARDED and treated as \`absent\` downstream — an unevidenced
\`conforms\` in particular would make the pipeline reuse something that may not match the
PRD at all, which is the expensive error here. Prefer several pieces of evidence over one.

You hold full AWS admin credentials. Checking a live endpoint is legitimate and is often
the decisive evidence — a capability can be fully implemented in the repository and
switched off in infrastructure, which reads as built from the code alone and as missing
from the deployed system. Look for both. EVERY aws command you run MUST pass
\`--profile ${awsProfile}\`; a command without it targets the wrong account.

Look specifically for the material that is easy to miss:
- an implementation that is complete but DISABLED by a feature flag, a commented-out
  construct, or an infrastructure switch — cite the file:line of the switch;
- a frontend fully scaffolded over a backend that does not exist, or the reverse;
- a capability live for some cases and not others (three of four identity providers);
- a route table, handler list, or CDK stack that already serves what the PRD asks for;
- code that serves a SUPERSEDED version of this behaviour — that is \`contradicts\`, and its
  removal is work somebody has to do.

Per requirement, also return:
- needsNewContract — true if satisfying it requires a NEW OR CHANGED contract: an HTTP
  route, an event, a schema, a public interface. False if the contract already exists and
  only its behaviour must change.
- repos — the repositories this requirement's work (build, reuse or removal) touches.

═══ CHECK 1b — UI REQUIREMENTS ARE RESOLVED AGAINST THE cds DESIGN SYSTEM ═══

For every requirement whose \`surface\` is \`ui\`, the design system's own output is the
AUTHORITY. Authority runs in this order, highest first, and you resolve each UI
requirement at the highest level that has an artifact for it:

  1. THE cds HAND-OFF BUNDLE — the packaged artifact: its \`spec/build-spec.md\` together
     with the composed HTML under \`design/\`. This is the boundary between "approved in
     cds" and "built in the app repo", and it is the highest authority there is for UI.
  2. THE LOOSE COMPOSED ARTIFACT under \`design-mocks/{shells,pages,views}/\` — used when
     the artifact is not in the bundle.
  3. THE PRD's PROSE about layout.
  4. WHAT IS CURRENTLY DEPLOYED — lowest, and NEVER authoritative for UI.

── Level 1: the hand-off bundle ──

Bundle root:
${packagesDir ? `  ${packagesDir}` : '  the design-mocks/packages/ directory under the repository this run operates on'}
Resolve \`CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR\` from the environment first when it is set;
otherwise use the path above. The root holds dated \`batch-*\` directories — TAKE THE MOST
RECENT ONE and record it in \`uiAuthority.bundlePath\`. Inside a batch:

  MANIFEST.tsv                      every artifact in the bundle: folder, slug, family, theme
  unpackaged.md                     composed files that are NOT in this bundle (see below)
  {shells,pages,views}/<slug>/
      design/<kind>.html            the composed artifact (shell.html | page.html | view.html)
      spec/build-spec.md            what the app repo builds — READ THIS
      spec/wireframe.txt            the structural sketch
      spec/decisions.md             the composer's recorded decisions
      state/<slug>.yaml             the composer state record
  styles/                           ONE shared stylesheet set for every artifact in the
                                    bundle (tokens.css, components.css, themes.css,
                                    manifest.json) — verified current at packaging time and
                                    NOT regenerated in the app repo
  assets/                           shared assets + artwork-manifest.yaml

START AT \`MANIFEST.tsv\`. It is the cheap index — one read tells you which slugs are
bundled, so you can match a UI requirement to its artifact without listing directories.
Then read that artifact's \`spec/build-spec.md\` and, when the requirement turns on layout
or structure, its composed HTML.

── Level 2: unpackaged artifacts ──

\`unpackaged.md\` lists composed files that have no state record and are therefore NOT in
the bundle. ABSENCE FROM THE BUNDLE MEANS "NOT YET PACKAGED" — it never means "not
decided", and it never blocks anything. Such a requirement simply falls back to authority
level 2: the loose composed artifact under
${mocksDir ? `  ${mocksDir}/{shells,pages,views}/` : '  design-mocks/{shells,pages,views}/'}
(resolve \`CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR\` / \`_SHELLS_DIR\` first when set;
\`DESIGN.md\` beside them is the exported design system: tokens, geometry, building blocks,
rules). Say in \`evidenceSummary\` that the artifact is unpackaged. It is never an
architecture question and never a reason to stop.

── Evidence and the verdict ──

CITE THE SPECIFIC ARTIFACT PATH YOU ACTUALLY USED as the evidence for every \`ui\`
requirement — a \`.../batch-<stamp>/views/<slug>/spec/build-spec.md\` or a
\`design-mocks/pages/<name>.html\` is strong evidence for a UI requirement in exactly the way
a \`file:line\` is for a service one. List every artifact path you opened in
\`uiAuthority.artifactsConsulted\`, and keep \`uiAuthority.shellsConsulted\` /
\`uiAuthority.pagesConsulted\` for the loose shells and pages you read. Record the batch you
selected in \`uiAuthority.bundlePath\` and the mocks directory in \`uiAuthority.mocksDir\`.

A UI requirement is \`conforms\` ONLY when the deployed UI matches the PACKAGED artifact
(or, for an unpackaged one, the composed artifact). Anything else is \`contradicts\`, and the
packaged artifact wins. That is not a competing option, not a design question, and NEVER an
architecture question — layout, shells, navigation shape, components, visual design and
interaction patterns are settled by the design system. Name the deployed markup or
component to bring into line in \`removalTargets\` and move on.

If neither the bundle nor the mocks directory exists, say so in \`evidenceSummary\` and
record the paths you looked for. Do not substitute the deployed UI as the authority in
their place.

═══ CHECK 1c — is architecture actually needed? ═══

Judge across the WHOLE PRD:

- infraOnly — true only if every requirement in this PRD is satisfied by an infrastructure
  change alone (a flag, a stack parameter, a permission, a provisioned resource) with no
  application code to write or remove. Judged across the whole PRD, not across a remainder.

- architectureNeeded — true if, and ONLY if, THE PRD ITSELF leaves a genuine technical
  question open that somebody must rule on before the work can be specified, in one of:
  service boundaries, persistence, transport, event contracts, the auth model, or
  deployment topology.

  List each such question in \`architectureQuestions\`, and ATTRIBUTE EVERY ONE to the
  requirement it arises from: \`{ requirementId, question }\`, where \`requirementId\` is the
  \`id\` of a requirement in the inventory you just returned. The attribution is checked
  mechanically, so use the ids you actually emitted. If a question genuinely arises from
  the PRD as a whole rather than from one requirement, leave \`requirementId\` empty and say
  so in the question text.

  IT MUST BE FALSE FOR ALL OF THESE, WITHOUT EXCEPTION:
    - a contradiction between the PRD and what is deployed. Settled: the PRD wins. That is
      removal work, not a decision.
    - ANY difference in UI or UX — layout, shells, navigation, components, visual design,
      interaction. Settled: the design system wins — the packaged artifact, else the
      composed mock. UI and architecture are symbiotic but not equivalent, and a design
      difference has never been an architecture decision. THIS ONE IS ENFORCED: a question
      attributed to a requirement whose \`surface\` is \`ui\` is dropped by the script, and if
      every question you return is attributed to a \`ui\` requirement then
      \`architectureNeeded\` is recorded as false whatever you set. An Epic once spent 45
      minutes convening an architecture panel to choose an app shell that the design mocks
      had settled months earlier; that is the failure this check exists to make impossible.
    - a question an existing recorded decision, or an established pattern already in the
      codebase, already answers. Follow the pattern.

  When \`architectureNeeded\` is false, \`architectureQuestions\` MUST be empty. An empty
  question list is read as "no architecture needed" regardless of the flag, so do not set
  the flag true with nothing to ask.

Do not soften a finding to be agreeable in either direction. Calling existing material
absent causes it to be rebuilt alongside itself; calling contradicting material conforming
leaves the product in the state the PRD was written to change.

═══ SEARCH BUDGET ═══

You are answering one question per requirement, not auditing the estate. Work requirement
by requirement and stop searching for each the moment its status is settled: one decisive
hit — the file:line that implements it, the mock that defines it, a live endpoint that
answers — settles \`conforms\` or \`contradicts\` and you move on. Two or three well-aimed
searches that all miss settles \`absent\` — absence is a legitimate finding, not a reason to
keep looking. Prefer one targeted search over browsing a repository, and never re-open a
file to confirm something you already read. Roughly six tool calls per requirement is the
expected shape.

"No implementation found after targeted search" is a correct and complete answer.
Exhaustively proving a negative across every repository is not more rigorous — it costs far
more and says the same thing, and an unevidenced claim is dropped downstream regardless.

═══ CHECK 2 — upstream dependency changes ═══

Upstream dependencies the PRD relies on:
${dependencies.length ? dependencies.map((d, i) => `${i + 1}. ${d}`).join('\n') : '(none declared in args — discover them from the PRD text and the repositories above)'}

Determine whether any upstream contract, shared schema, event, library version, or interface the PRD assumes has changed in a way that invalidates one of its assumptions. This is not a search for defects in the PRD's wording — it is a search for ground that moved. Return this check under \`dependencyChanges\`:
- current: true if no invalidating upstream change is found, false otherwise.
- changeFindings: each invalidating change (dependency, change describing what changed, invalidates describing which PRD assumption it breaks).
- evidence: how you verified the dependency state (one paragraph, under 60 words).

═══ YOUR BUDGET ═══

Your structured output IS the deliverable. Nothing you read reaches anybody except through it, so an exhaustive investigation that ends without it is worth exactly as much as no investigation at all — and it is how this phase has failed in practice: the reconciler explored until it ran out of room and returned nothing, so the whole run aborted and the work was re-dispatched from zero.

You have roughly 50 tool calls. Spend them breadth-first: cover EVERY requirement at least once before you deepen any of them, because a requirement you never looked at comes back as \`absent\` and gets built from scratch beside material that already exists. By call 50, stop investigating and emit your structured output with whatever you have — a partial inventory with honest evidence is a usable result; a perfect inventory you never returned is not. Report thin coverage in \`evidenceSummary\` rather than spending more turns on it.`,
  {
    label: 'reconcile:reality-and-dependencies',
    phase: 'Reconciliation checks',
    agentType: 'agent-teams-workforce:prd-reality-reconciler',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['requirements', 'infraOnly', 'architectureNeeded', 'architectureQuestions', 'evidenceSummary', 'dependencyChanges'],
      properties: {
        requirements: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['id', 'requirement', 'status', 'evidence', 'surface'],
            properties: {
              id: { type: 'string' },
              requirement: { type: 'string' },
              status: { type: 'string', enum: ['conforms', 'contradicts', 'absent'] },
              // minItems is load-bearing: a status with no evidence behind it is the
              // defect this mini exists to catch, so the schema refuses to express one.
              // The reduction below enforces the same rule again, because a schema
              // constrains what a model is ASKED for, not what it returns.
              evidence: { type: 'array', minItems: 1, items: { type: 'string' } },
              surface: { type: 'string', enum: ['ui', 'service', 'infra', 'data', 'unknown'] },
              conformingMaterial: { type: 'array', items: { type: 'string' } },
              removalTargets: { type: 'array', items: { type: 'string' } },
              missing: { type: 'string' },
              needsNewContract: { type: 'boolean' },
              repos: { type: 'array', items: { type: 'string' } },
            },
          },
        },
        infraOnly: { type: 'boolean' },
        architectureNeeded: { type: 'boolean' },
        architectureQuestions: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['requirementId', 'question'],
            properties: {
              // The id of a requirement in the inventory above, or empty when the question
              // arises from the PRD as a whole. Attribution is what makes the UI exclusion
              // mechanically checkable rather than a hope about how the brief is read.
              requirementId: { type: 'string' },
              question: { type: 'string' },
            },
          },
        },
        decisionRationale: { type: 'string' },
        evidenceSummary: { type: 'string' },
        uiAuthority: {
          type: 'object',
          additionalProperties: false,
          properties: {
            bundlePath: { type: 'string' },
            mocksDir: { type: 'string' },
            artifactsConsulted: { type: 'array', items: { type: 'string' } },
            shellsConsulted: { type: 'array', items: { type: 'string' } },
            pagesConsulted: { type: 'array', items: { type: 'string' } },
          },
        },
        dependencyChanges: {
          type: 'object',
          additionalProperties: false,
          required: ['current', 'changeFindings', 'evidence'],
          properties: {
            current: { type: 'boolean' },
            changeFindings: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['dependency', 'change', 'invalidates'],
                properties: {
                  dependency: { type: 'string' },
                  change: { type: 'string' },
                  invalidates: { type: 'string' },
                },
              },
            },
            evidence: { type: 'string' },
            notes: { type: 'string' },
          },
        },
      },
    },
  }
)

const reality = combined
const dependencyChanges = (combined && combined.dependencyChanges) || null

// ── A DEAD AGENT IS NOT A FINDING ───────────────────────────────────────────────
//
// A dispatch dies in two ways — skipped or dead on a terminal API error (null), or run
// to completion without ever emitting its structured output (a throw). `dispatch()`
// above normalizes both to null and has already spent its retry. Neither is the same
// event as a reconciler that ran and returned a malformed inventory, and folding them
// together is what turned two of the five real prd-to-spec runs into work failures at
// stage 'prd-reconciliation': the supervisor charged the bead for an account limit.
// Both still stop the run — reading "we could not establish what exists" as "nothing
// exists" is the blind assumption this phase removes — but only one of them is
// anybody's fault, and the caller needs to be able to tell which.
if (!reality) {
  return fail(
    'the reality reconciler never came back with an account of what already exists, on any attempt, so no ' +
      `reconciliation was performed (${dispatchNotes.join('; ')}). This is a DISPATCH failure, not a verdict on ` +
      'the PRD or on what already exists.',
    { dispatchFailed: true, dispatchFailures: dispatchNotes.slice() }
  )
}
if (!Array.isArray(reality.requirements)) {
  return fail('the reality reconciler returned no requirement inventory — reconciliation cannot be reduced to an inventory.')
}

// ── Evidence enforcement ────────────────────────────────────────────────────────
// A schema constrains the REQUEST, not the response, so the rule is applied again here
// where it is deterministic and testable. The two directions of error are not symmetric,
// and the asymmetry is the opposite of what it was under the delta contract. There, an
// unevidenced "shipped" deleted work from the delta and it was never built. Here nothing
// is ever deleted from scope — but an unevidenced `conforms` makes the pipeline REUSE
// material that may not match the PRD at all, and an unevidenced `contradicts` sends a
// removal task after a file nobody confirmed.
//
// So an unevidenced claim is never resolved in favour of the claim: it drops to
// 'absent', which means "build it fresh". That is never wrong under this rule, only
// more expensive. Every demotion is reported.
//
// Evidence must also LOOK like evidence: a file:line, a URL, a named endpoint, or an AWS
// resource identifier. "I checked the code" is a claim about the checker, not about the
// system.
//
// ONE narrow exemption, and it is narrow deliberately. A composed cds artifact is a
// single generated file — hundreds of kilobytes of machine-emitted HTML — and its build
// spec is a whole document; demanding a line number inside either is evidence theatre,
// because the artifact IS the unit of authority and no line of it means anything alone.
// So a `.html` or `.md` path is admissible WITHOUT a line number, but only when it sits
// under the design-system directories: the mocks root or the hand-off bundle root.
//
// Everywhere else the original bar holds, and that is the point of scoping it. A bare
// `services/auth/mfa.py` with no line number is "I saw the filename", not "I read the
// implementation" — and sustaining a `conforms` on it would make the pipeline reuse
// material on the strength of a path somebody typed. That is precisely the failure this
// gate exists to catch, so the exemption must never reach a service, infra or data file.
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const uiRoots = ['design-mocks', mocksDir, packagesDir]
  .filter((d) => hasText(d))
  .map((d) => escapeRe(d.replace(/\/+$/, '')))
const uiArtifactPath = new RegExp(`(?:${uiRoots.join('|')})/[^\\s"'\`]*\\.(?:html|md)\\b`, 'i')

// A CITED ENDPOINT, NOT THE WORD "ENDPOINT".
//
// The original test was `/\bendpoint\b/i`, which matches the word anywhere in a sentence
// — so "no endpoint was found" read as strong evidence and sustained a `conforms`. A
// statement that something does NOT exist was being counted as proof that it does, in the
// one gate standing between a loose claim and the pipeline reusing material that does not
// match the PRD.
//
// So the citation must identify an ADDRESS: a method and path, an AWS API host, or an
// actual CLI invocation with arguments. A URL and an `arn:aws` already pass on their own
// clauses.
const ENDPOINT_CITATION =
  /\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+\/[A-Za-z0-9._~/{}:$-]+/.source +
  '|' +
  /\b[a-z0-9-]+\.(?:execute-api|appsync-api|lambda-url)\.[a-z0-9-]+\.amazonaws\.com\S*/i.source +
  '|' +
  /\baws\s+[a-z0-9-]+\s+[a-z0-9-]+\b[^\n]*\s--[a-z][a-z-]*/i.source
const endpointCitation = new RegExp(ENDPOINT_CITATION, 'i')

// …and the address must not be sitting inside a denial that it exists. "the endpoint
// GET /v1/settings does not exist" cites a real address to say the opposite of what a
// `conforms` claims. This veto is deliberately scoped to the endpoint clause alone: a
// `contradicts` is very often evidenced as "web/Shell.tsx:12 renders a nav that does not
// exist in the mock", and that is a correct citation which must keep passing on the
// file:line clause.
const denied = (s) =>
  /\b(?:no|not|never)\s+(?:\w+\s+){0,2}(?:found|exists?|implemented|deployed|present|configured)\b/i.test(s) ||
  /\bdoes\s*n[o']?t\s+exist\b/i.test(s) ||
  /\b(?:could|can)\s*n[o']?t\s+(?:find|locate|reach)\b/i.test(s) ||
  /\bno\s+(?:such\s+)?(?:endpoint|route|handler|implementation|resource|api)\b/i.test(s) ||
  /\bnothing\s+(?:was\s+)?found\b/i.test(s) ||
  /\bnot\s+found\b/i.test(s)

const strongEvidence = (s) =>
  /:\d+/.test(s) ||
  /https?:\/\//i.test(s) ||
  /\barn:aws\b/i.test(s) ||
  uiArtifactPath.test(s) ||
  (endpointCitation.test(s) && !denied(s))

const SURFACES = ['ui', 'service', 'infra', 'data', 'unknown']
const evidenceViolations = []
const requirements = reality.requirements.map((r, i) => {
  const id = hasText(r && r.id) ? r.id : `R${i + 1}`
  const evidence = (Array.isArray(r && r.evidence) ? r.evidence : []).filter((e) => hasText(e)).map((e) => e.trim())
  const claimed = (r && r.status) || 'absent'
  // A status outside the enum is a demotion like any other, and it has a real source: a
  // resumed run, a hand-built packet, or a model reaching for the retired `shipped` /
  // `partial` / `obsolete` vocabulary. It must be COUNTED, not just remembered in
  // `claimedStatus` — the ledger's violation count is what tells a reader how much of the
  // inventory was downgraded, and a demotion missing from it makes that number a lie.
  const recognised = claimed === 'conforms' || claimed === 'contradicts' || claimed === 'absent'
  let status = claimed === 'conforms' || claimed === 'contradicts' ? claimed : 'absent'
  if (!evidence.length) {
    status = 'absent'
    evidenceViolations.push({ id, claimedStatus: claimed, reason: 'no evidence supplied' })
  } else if ((status === 'conforms' || status === 'contradicts') && !evidence.some(strongEvidence)) {
    status = 'absent'
    evidenceViolations.push({
      id,
      claimedStatus: claimed,
      reason:
        'no file:line, cited design-system artifact under the mocks or bundle root, deployed endpoint, URL, or AWS resource identifier among the evidence',
    })
  } else if (!recognised) {
    evidenceViolations.push({
      id,
      claimedStatus: claimed,
      reason: `unrecognised status '${claimed}' — not one of conforms / contradicts / absent, so it cannot be honoured`,
    })
  }
  const list = (v) => (Array.isArray(v) ? v.filter((x) => hasText(x)).map((x) => x.trim()) : [])
  return {
    id,
    requirement: (r && r.requirement) || '',
    status,
    evidence,
    // These describe the material, so they only survive alongside the status that names
    // them — a demoted requirement carries no reuse or removal instruction at all.
    // Removal in particular is DESTRUCTIVE: `removalTargets` becomes a task telling
    // somebody to delete named files, and an unconfirmed claim is not grounds to delete
    // anything. Reuse is the mirror error, quieter but not smaller: it makes the pipeline
    // build on material nobody verified matches the PRD.
    conformingMaterial: status === 'conforms' ? list(r && r.conformingMaterial) : [],
    removalTargets: status === 'contradicts' ? list(r && r.removalTargets) : [],
    missing: status === 'absent' ? (r && r.missing) || null : null,
    needsNewContract: !!(r && r.needsNewContract),
    repos: list(r && r.repos),
    surface: SURFACES.indexOf(r && r.surface) !== -1 ? r.surface : 'unknown',
    claimedStatus: claimed,
  }
})

if (evidenceViolations.length) {
  log(
    `Evidence enforcement: ${evidenceViolations.length} requirement status claim(s) could not be honoured — unevidenced, ` +
      `or claiming a status outside the enum — and were demoted to 'absent'. They will be built fresh rather than reused ` +
      `or removed on an unconfirmed claim.`
  )
}

// ── Reduction: the inventory, the work it implies, and whether architecture is needed ──
// Computed HERE, from the typed findings, rather than asked of a model. Nothing in this
// reduction narrows the PRD: every requirement that came in goes out.
const conformsCount = requirements.filter((r) => r.status === 'conforms').length
const contradictsCount = requirements.filter((r) => r.status === 'contradicts').length
const absentCount = requirements.filter((r) => r.status === 'absent').length

// Removal is real work and it must reach decomposition as a first-class output. A
// contradiction that is only recorded as a status becomes a removal nobody does, and the
// product keeps shipping the thing the PRD was written to replace.
const removalWork = requirements
  .filter((r) => r.status === 'contradicts' && r.removalTargets.length)
  .map((r) => ({ requirementId: r.id, requirement: r.requirement, targets: r.removalTargets, repos: r.repos }))

// Reuse is the other half: named material the downstream phases build ON rather than
// re-derive. It is context for them, never a subtraction from what the PRD asks.
const reuseWork = requirements
  .filter((r) => r.status === 'conforms' && r.conformingMaterial.length)
  .map((r) => ({ requirementId: r.id, requirement: r.requirement, material: r.conformingMaterial, repos: r.repos }))

// TWO REPO LISTS, ONE WORD APART — read this before picking one.
//
//   `repos`         — every repo any requirement touches, including the repos an `absent`
//                     requirement PREDICTS its work will land in. A prediction, useful for
//                     sizing the span of the whole PRD.
//   `existingRepos` — only the repos where material was actually FOUND: the union across
//                     `conforms` and `contradicts`, both of which are backed by cited
//                     evidence that survived enforcement.
//
// The distinction is the whole point of the narrower list. It is handed to the repo
// surveyor as EVIDENCE — "material exists here" — and a predicted repo in it would be a
// guess wearing evidence's clothes. An `absent` requirement proves nothing about where
// anything lives.
const allRepos = []
const existingRepos = []
for (const r of requirements) {
  const material = r.status === 'conforms' || r.status === 'contradicts'
  for (const x of r.repos) {
    if (allRepos.indexOf(x) === -1) allRepos.push(x)
    if (material && existingRepos.indexOf(x) === -1) existingRepos.push(x)
  }
}
const spansMultipleRepos = allRepos.length > 1

// A flag with no question behind it is not an architecture need, it is a shrug. The
// exclusions (PRD-vs-deployed contradictions, UI/UX differences, questions an existing
// decision already answers) are enforced in the brief; what is enforced here is the one
// thing a script can check: architecture is needed only when something is actually being
// asked.
const surfaceById = {}
for (const r of requirements) surfaceById[r.id] = r.surface

const architectureQuestions = (Array.isArray(reality.architectureQuestions) ? reality.architectureQuestions : [])
  .filter((q) => q && hasText(q.question))
  .map((q) => ({ requirementId: hasText(q.requirementId) ? q.requirementId.trim() : null, question: q.question.trim() }))

// THE UI EXCLUSION, ENFORCED RATHER THAN ASKED FOR.
//
// This is the concrete failure the whole change exists to prevent: an Epic spent 45
// minutes convening an architecture panel to choose an app shell, when the shell had been
// settled in the design mocks since August. UI and architecture are symbiotic but not
// equivalent — layout, shells, navigation, components and interaction are the design
// system's ruling, and no amount of architecture deliberation improves on it. Leaving that
// entirely to the brief means it fails again the first time a model reads the brief
// loosely, so the attribution on each question makes it checkable here.
//
// The direction of the guard matters. A question attributed to a `ui` requirement is
// dropped. A question attributed to NOTHING, or to an id that is not in the inventory, is
// NOT dropped: unknown is not the same as UI, and the safe error here is letting a genuine
// question through, not silencing one.
const uiQuestions = architectureQuestions.filter((q) => q.requirementId && surfaceById[q.requirementId] === 'ui')
const liveQuestions = architectureQuestions.filter((q) => uiQuestions.indexOf(q) === -1)

let architectureNeeded = !!reality.architectureNeeded && liveQuestions.length > 0
if (reality.architectureNeeded && uiQuestions.length && !liveQuestions.length) {
  architectureNeeded = false
  log(
    `Reconciliation: architectureNeeded was claimed, but every question attributed to a ui requirement ` +
      `(${uiQuestions.map((q) => q.requirementId).join(', ')}) — the design system settles those, so no ` +
      `architecture is needed. Questions dropped: ${uiQuestions.map((q) => q.question).join(' | ')}`
  )
} else if (reality.architectureNeeded && !architectureNeeded) {
  log('Reconciliation: architectureNeeded was claimed with no open question behind it — recorded as not needed.')
}

const infraOnly = !!reality.infraOnly

// `bundlePath` is the batch the reconciler actually selected — spec authoring reads the
// bundle's build-specs rather than re-deriving UI from PRD prose, so the resolved path
// travels with the inventory. Null when no bundle was found; the packages ROOT is not
// substituted for it, because "which batch" is the part that matters.
const ua = (reality && reality.uiAuthority) || {}
const strList = (v) => (Array.isArray(v) ? v.filter((x) => hasText(x)).map((x) => x.trim()) : [])
const uiAuthority = {
  bundlePath: hasText(ua.bundlePath) ? ua.bundlePath.trim() : null,
  mocksDir: hasText(ua.mocksDir) ? ua.mocksDir.trim() : mocksDir || null,
  artifactsConsulted: strList(ua.artifactsConsulted),
  shellsConsulted: strList(ua.shellsConsulted),
  pagesConsulted: strList(ua.pagesConsulted),
}

log(
  `Reconciliation: ${requirements.length} requirement(s) inventoried — ${conformsCount} conform (reuse), ` +
    `${contradictsCount} contradict (remove), ${absentCount} absent (build)` +
    `${infraOnly ? ' — infrastructure only' : ''}` +
    `${architectureNeeded ? `; ${liveQuestions.length} architecture question(s) open` : '; no architecture needed'}.`
)

const uiCount = requirements.filter((r) => r.surface === 'ui').length
if (uiCount) {
  log(
    `UI authority: ${uiCount} ui requirement(s) resolved against ` +
      `${uiAuthority.bundlePath ? `the cds hand-off bundle ${uiAuthority.bundlePath}` : 'the loose composed mocks (no hand-off bundle was resolved)'}` +
      `${uiAuthority.artifactsConsulted.length ? `, ${uiAuthority.artifactsConsulted.length} artifact(s) consulted` : ''}.`
  )
}

const ledger = {
  phase: 'prd-reconciliation',
  beadId: null,
  subject: prdId || prdTitle || null,
  chosen: ['prd-reality-reconciler (both checks, one session)'],
  mode: 'combined', // one checker session carries both reconciliation checks
  requirementCount: requirements.length,
  conformsCount,
  contradictsCount,
  absentCount,
  removalWork: removalWork.length,
  architectureNeeded,
  uiQuestionsDropped: uiQuestions.length,
  evidenceViolations: evidenceViolations.length,
  ok: true,
}

return {
  ok: true,
  // EVERY requirement the PRD states, never filtered and never narrowed.
  requirements,
  conformsCount,
  contradictsCount,
  absentCount,
  removalWork,
  reuseWork,
  repos: allRepos,
  existingRepos,
  // Descriptive only — NOTHING in the plugin reads this today. It also changed meaning in
  // this rewrite: it used to span the delta's repos and now spans the whole PRD's, so a
  // future consumer must read it as "this PRD touches more than one repo", never as "the
  // remaining work does".
  spansMultipleRepos,
  architectureNeeded,
  // Only the questions that survived the guard, and empty whenever architecture is not
  // needed — a caller reading the list as the work to do must never find a dropped UI
  // question sitting in it.
  architectureQuestions: architectureNeeded ? liveQuestions : [],
  uiAuthority,
  // Judged across the WHOLE PRD, not a remainder. Descriptive only — NOTHING reads this
  // today. It USED to reroute an infrastructure-only delta to the infra-change pipeline,
  // and that reroute was deleted on purpose in this rewrite: it was a decision about scope
  // taken from an inventory, which is exactly what this phase must never do. Reporting the
  // fact is fine; do not restore a caller that acts on it without a deliberate decision.
  infraOnly,
  dependencyChanges,
  evidenceViolations,
  evidenceSummary: (reality && reality.evidenceSummary) || null,
  ledger,
}
