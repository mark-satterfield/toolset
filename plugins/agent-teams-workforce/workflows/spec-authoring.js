export const meta = {
  name: 'spec-authoring',
  description:
    'Leaf mini — Spec authoring. Three maker sessions author, in parallel, the implementation-ready spec set for one repository from the TRD and the approved target and delta views, specifying the change for the delta items the repository\'s detailing marks add, modify or remove: API/OpenAPI, event and error contracts; the data model; the acceptance criteria and Definition of Done. For a repository with `ui` work items the contracts maker also returns uiSpec, one section per item stating its design source: a bundle item (the owner supplied a cds bundle) cites that bundle\'s spec/build-spec.md and its resolved Section IDs; a cds item states that it is designed with the CDS design system; a none item states that it changes no design. The script checks, in that return and in the saved spec document (depscore.py spec-ui-check reads the file), that every item has its section and that every bundle item cites the build spec the detailing resolved and its Section IDs; a gap sends the contracts back to their maker once, and a second gap fails the run at stage ui-citation. One more session authors the ONE Story the Spec pairs with, scoped to args.repoPath, saves it as story-<slug>.json, and writes that ONE Story bead itself with one depscore.py write-story command, keyed by its elab_key, whose full result — the keyed Tasks already under the Story among it — lands in story-<slug>.written.json. With replay: true no session authors, and one runner session runs write-story from the saved story-<slug>.json. Whether the bead landed is read from beads by depscore.py elaboration-finish, not judged here.',
  phases: [
    { title: 'Author specs', detail: 'three maker sessions author the spec artifacts in parallel' },
    { title: 'Emit story', detail: 'author the ONE Story this Spec pairs with — container only, single repo — and write its bead with depscore.py write-story' },
  ],
}
const dispatchFailures = []
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  return named.length ? dispatchFailures.filter((f) => named.includes(f.phase)) : dispatchFailures.slice()
}
// Runs agent(); returns its result, or null after recording the failure in dispatchFailures.
async function settleAgent(prompt, opts) {
  const o = opts || {}
  const who = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null }
  const name = who.label || who.agentType || 'agent'
  try {
    const out = await agent(prompt, o)
    if (out) return out
    dispatchFailures.push({ ...who, outcome: 'skipped', note: `${name} returned nothing` })
    log(`${name}: returned nothing`)
  } catch (err) {
    const message = String((err && err.message) || err).slice(0, 300)
    dispatchFailures.push({ ...who, outcome: 'threw', message, note: `${name} ended without a structured result: ${message}` })
    log(`${name}: ended without a structured result — ${message}`)
  }
  return null
}

// args: {
//   spec: { id?, title?, summary?, service?, repoPath? }, trd?, constraints?: string[],
//   architecture?: { targetDir, deltaDir } (the approved target and its delta),
//   accessPatterns?: string[], repoPath, storyKey? ('S1'), epic: { key?, id?, title? },
//   uiItems?: [{ id, element?, designSource?, buildSpec?, sections? }] (the repository's `ui` work items, each with its design source bundle | cds | none and, for bundle, the build spec it was resolved to),
//   detailingPath?: <absolute path of the repository's saved delta detailing, recon-<slug>.json; the makers read it>,
//   artifacts: { dir, relDir?, epicId, script, phase, slug, inputs? },
//   beads: { script, repo, epicId, projectRoot? }  (script: the absolute depscore.py path),
//   replay?: true
// }
// returns { ok, resumed?, unresolvedArtifacts, story: { key, type, id, elabKey, title, description, repoPath, parentEpicKey },
//           writtenPath, spec, apiSpec, dataModelSpec, eventContracts, errorSpec, uiSpec, decisionIds, outOfRepoFindings, note },
//           or { ok: false, stage, reason, dispatchFailed? }; story.id is null when the write-story summary was not relayed

const CRITERIA_MAX = 120
const DOD_MAX = 30

const SPEC_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['artifactPaths', 'summary', 'content'],
  properties: {
    artifactPaths: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    content: { type: 'string' },
    openQuestions: { type: 'array', items: { type: 'string' } },
    decisionIds: { type: 'array', items: { type: 'string' } },
  },
}

const CONTRACTS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['apiSpec', 'eventContracts', 'errorSpec'],
  properties: {
    apiSpec: SPEC_SCHEMA,
    eventContracts: SPEC_SCHEMA,
    errorSpec: SPEC_SCHEMA,
  },
}

const UI_SPEC_SCHEMA = {
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['itemId', 'designSource', 'buildSpec', 'sections', 'content'],
    properties: {
      itemId: { type: 'string' },
      designSource: { type: 'string', enum: ['bundle', 'cds', 'none'] },
      buildSpec: { type: 'string' },
      sections: { type: 'array', items: { type: 'string' } },
      content: { type: 'string' },
    },
  },
}

const CONTRACTS_UI_SCHEMA = {
  ...CONTRACTS_SCHEMA,
  required: [...CONTRACTS_SCHEMA.required, 'uiSpec'],
  properties: { ...CONTRACTS_SCHEMA.properties, uiSpec: UI_SPEC_SCHEMA },
}

const BUILD_SPEC_PATH = /(^|\/)spec\/build-spec\.md$/

/** Returns the UI items with no uiSpec section, and the bundle items whose section cites no build-spec.md or another one than the detailing resolved. */
function uiCitationGaps(uiItems, uiSpec) {
  const sections = Array.isArray(uiSpec) ? uiSpec.filter((x) => x && typeof x === 'object') : []
  return uiItems
    .map((item) => {
      const own = sections.filter((x) => String(x.itemId || '').trim() === item.id)
      if (!own.length) return { id: item.id, problem: 'no uiSpec section specifies it' }
      if (item.designSource !== 'bundle') return null
      const cited = own.map((x) => String(x.buildSpec || '').trim())
      if (!cited.some((p) => BUILD_SPEC_PATH.test(p))) return { id: item.id, problem: 'its uiSpec section cites no spec/build-spec.md path' }
      if (item.buildSpec && !cited.includes(item.buildSpec)) return { id: item.id, problem: `its uiSpec section cites ${cited.join(', ')}, not the build spec the detailing resolved, ${item.buildSpec}` }
      const listed = new Set(own.flatMap((x) => (Array.isArray(x.sections) ? x.sections : []).map((y) => String(y).trim())))
      const absent = item.sections.filter((x) => !listed.has(x))
      if (absent.length) return { id: item.id, problem: `its uiSpec section leaves out the build-spec Sections ${absent.join(', ')} the detailing resolved` }
      return null
    })
    .filter(Boolean)
}

const CRITERIA_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['acceptanceCriteria', 'definitionOfDone'],
  properties: {
    acceptanceCriteria: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['given', 'when', 'then'],
        properties: {
          given: { type: 'string' },
          when: { type: 'string' },
          then: { type: 'string' },
        },
      },
    },
    definitionOfDone: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
}

const STORY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['title', 'description', 'write'],
  properties: {
    title: { type: 'string' },
    description: { type: 'string' },
    write: {
      type: 'object',
      additionalProperties: false,
      required: ['exitCode', 'stdout'],
      properties: { exitCode: { type: 'integer' }, stdout: { type: 'string' } },
    },
  },
}

function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  return ['dir', 'script', 'epicId', 'phase'].every((k) => typeof x[k] === 'string' && x[k]) ? x : null
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
function persistBrief(art, name, what) {
  if (!art) return ''
  const file = `${art.dir}/${name}`
  const inputs = (Array.isArray(art.inputs) ? art.inputs : []).filter((p) => typeof p === 'string' && p.trim())
  const record = `python3 ${art.script} record ${file} --epic ${art.epicId} --phase ${art.phase}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN.\n1. Write ${what} to ${file} with the Write tool, replacing the whole file if it exists (Read it first, then Write). Write no other file for this.\n2. Then run exactly this command:\n   ${record}\nIf a step fails, say so in your result and still return your result.`
}

function hasText(x) {
  return typeof x === 'string' && x.trim().length > 0
}

const WRITE_RUN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['exitCode', 'output'],
  properties: { exitCode: { type: 'integer' }, output: { type: 'object' } },
}
/** Runs one depscore.py write command in a runner session; returns its JSON output, or { error }. */
async function runWrite(label, phaseName, command) {
  const out = await settleAgent(
    `Run exactly this one shell command, once, in the FOREGROUND (never set run_in_background) with the Bash tool's \`timeout\` parameter set to 600000, and change nothing else:

${command}

It prints one JSON object on stdout. Return the process exit code as \`exitCode\` and that JSON object, parsed and unaltered, as \`output\`. If stdout is not JSON, return {"error": "<stdout and stderr, verbatim>"} as \`output\`. Do not retry, do not repair, do not run any other command.`,
    { label, phase: phaseName, model: 'haiku', effort: 'low', schema: WRITE_RUN_SCHEMA }
  )
  if (!out) return { error: `the ${label} runner returned no result` }
  if (out.exitCode !== 0 || !out.output || out.output.error) {
    return { error: (out.output && out.output.error) || `depscore.py exited ${out.exitCode}` }
  }
  return out.output
}
const beadsFrom = (x) => (x && typeof x === 'object' && ['script', 'repo', 'epicId'].every((k) => hasText(x[k])) ? x : null)

/** Returns the context block every maker reads: spec header, the repository's constraints, the target and delta views, and the TRD. */
function ctxBlock(s, trd, constraints, arch, detailingPath) {
  const trdOnDisk = trd && typeof trd.trdPath === 'string' && trd.trdPath.startsWith('/')
  return [
    `Spec ${s.id || ''}: ${s.title || ''}`,
    s.service ? `Owning service: ${s.service}` : '',
    s.summary ? `What this spec must cover:\n${s.summary}` : '',
    `Work within the repository at: ${s.repoPath || '(repo path not provided — author against the supplied context only)'}`,
    "The architecture reaches this spec through the TRD: the owner's constraints (arc42 section 2) and the patterns the effective views establish for the API type, the runtime libraries, the event path and the data stores. Follow them as the TRD states them; a spec that departs from an established pattern states its reason and evidence.",
    arch && hasText(arch.deltaDir)
      ? `THE APPROVED TARGET is ${arch.targetDir || '(the folder above the delta)'}, and the change alone, its delta, is ${arch.deltaDir}. Read the delta views for the items listed below, and the target views they need: the spec specifies the change they show for this repository, and nothing the delta does not change.`
      : '',
    hasText(detailingPath)
      ? `THE DELTA DETAILING of this repository is the file ${detailingPath}. Read it: its \`items\` give each delta item placed here its status (add, modify, remove, done, planned-elsewhere), the \`from\` state the code on main holds, the \`to\` state the target makes it, its surface and its file:line evidence.`
      : '',
    constraints && constraints.length
      ? `Context and constraints for this repository:\n${constraints.map((c, i) => `${i + 1}. ${c}`).join('\n')}`
      : '',
    trdOnDisk
      ? `The TRD is the document at ${trd.trdPath}. Read it: it is the authoritative source for the technical requirements.${hasText(trd.summary) ? `\nTRD summary: ${trd.summary}` : ''}`
      : trd
        ? `Upstream TRD / requirements packet:\n${JSON.stringify(trd)}`
        : '',
  ]
    .filter(Boolean)
    .join('\n\n')
}

/** Returns the reading scope rule, plus the decision-citation rule when `cites` is true. */
function makerRules({ cites }) {
  return [
    'READING SCOPE: the packet above is your source, and the repository named above is the ONLY repository you may read — never survey other repositories. Prefer one targeted search over a directory walk, and never re-open a file you have already read.',
    cites
      ? 'CITE THE ARCHITECTURE YOU DESIGNED AGAINST. Return `decisionIds` on every artifact you author: the architecture views it depends on, each a path relative to the arc42 folder with `#<heading>` when it rests on one part of the view, written as the TRD cites them, and carry the same list in YAML frontmatter as `decisionIds:` at the top of the markdown document you save. Cite only views you read, and never cite a section number in place of a view.\n\nEFFECTIVE VIEWS ARE SETTLED. A view whose file\'s frontmatter reads `lifecycle_state: effective` has been reviewed and approved: design against it as given and never re-decide it. Only a view in any other state is open to review: before your design rests on one, check it against the TRD, and where they disagree the TRD governs.'
      : '',
  ]
    .filter(Boolean)
    .join('\n\n')
}

async function main(a) {
  const s = (a && a.spec) || {}
  const trd = a && a.trd
  const constraints = Array.isArray(a && a.constraints) ? a.constraints : []
  const accessPatterns = Array.isArray(a && a.accessPatterns) ? a.accessPatterns : []
  const repoPath = (a && a.repoPath) || (s && s.repoPath) || null
  const epic = (a && a.epic) || null
  const uiItems = (Array.isArray(a && a.uiItems) ? a.uiItems : [])
    .filter((u) => u && hasText(u.id))
    .map((u) => ({
      id: u.id.trim(),
      element: hasText(u.element) ? u.element.trim() : null,
      designSource: hasText(u.designSource) ? u.designSource.trim() : hasText(u.buildSpec) ? 'bundle' : 'cds',
      buildSpec: hasText(u.buildSpec) ? u.buildSpec.trim() : null,
      sections: Array.isArray(u.sections) ? u.sections.filter(hasText).map((x) => x.trim()) : [],
    }))

  const ART = artifactsFrom(a && a.artifacts)
  const artSlug = ART && hasText(ART.slug) ? ART.slug : 'repo'
  const beads = beadsFrom(a && a.beads)
  const parentEpicKey = (epic && (epic.key || epic.id)) || null
  const specDocPaths = ART
    ? [`${ART.dir}/spec-${artSlug}.md`, `${ART.dir}/spec-${artSlug}.data-model.md`, `${ART.dir}/spec-${artSlug}.criteria.md`]
    : []

  if (!ART || !beads) {
    return { ok: false, stage: 'input', reason: 'no artifact directory or beads target was supplied, so the Story bead cannot be written' }
  }
  const writtenPath = `${ART.dir}/story-${artSlug}.written.json`
  const storyCommand = [
    `python3 ${shq(beads.script)} -C ${shq(beads.repo)} write-story`,
    `--epic ${shq(beads.epicId)} --dir ${shq(ART.dir)} --slug ${shq(artSlug)} --repo ${shq(repoPath)}`,
    hasText(beads.projectRoot) ? `--project-root ${shq(beads.projectRoot)}` : '',
    `--out ${shq(writtenPath)}`,
  ].filter(Boolean).join(' ')

  /** Returns the spec-authoring result; `summary` is write-story's relayed summary, or null. */
  function storyResult(authored, summary, draft) {
    const w = summary && typeof summary === 'object' ? summary : {}
    log(hasText(w.id) ? `Story ${w.id} (story:${artSlug}) ${w.action || ''}` : `Story story:${artSlug}: write-story summary not relayed; beads is read at finish`)
    return {
      ok: true,
      ...authored,
      story: {
        key: (a && a.storyKey) || 'S1',
        type: 'story',
        id: hasText(w.id) ? w.id : null,
        elabKey: `story:${artSlug}`,
        title: (draft && draft.title) || null,
        description: (draft && draft.description) || null,
        repoPath,
        parentEpicKey,
      },
      writtenPath,
      summary: hasText(w.id) ? { created: Number(w.created) || 0, updated: Number(w.updated) || 0 } : null,
    }
  }

  if (a && a.replay === true) {
    log(`Spec authoring replayed: the Story is written from the saved story-${artSlug}.json`)
    const w = await runWrite('beads:write-story', 'Emit story', storyCommand)
    return storyResult({
      resumed: true,
      spec: { id: s.id || null, title: s.title || null, service: s.service || null, repoPath },
      specPaths: specDocPaths,
      outOfRepoFindings: [],
      apiSpec: { summary: '' },
      decisionIds: [],
      note: 'Replayed: the spec documents on disk are handed downstream as paths.',
    }, w && w.summary, null)
  }

  const ctx = ctxBlock(s, trd, constraints, a && a.architecture, a && a.detailingPath)
  const specMakerCtx = `${ctx}\n\n${makerRules({ cites: true })}`
  const criteriaMakerCtx = `${ctx}\n\n${makerRules({ cites: false })}`
  const contractsBrief = persistBrief(
    ART,
    `spec-${artSlug}.md`,
    uiItems.length
      ? 'the contract artifacts you return — apiSpec, eventContracts, errorSpec and uiSpec — as ONE markdown document with a section for each of the first three and one UI section per uiSpec entry, headed by its item id (a bundle item\'s section citing its build-spec.md path and Section IDs), carrying each artifact\'s full content'
      : 'the three contract artifacts you return — apiSpec, eventContracts and errorSpec — as ONE markdown document with a section for each, carrying each artifact\'s full content'
  )
  const designLine = (u) =>
    u.designSource === 'bundle'
      ? `bundle — ${u.buildSpec}${u.sections.length ? ` (Sections ${u.sections.join(', ')})` : ''}`
      : u.designSource === 'none'
        ? 'none — it changes no design'
        : 'cds — designed with the CDS design system'
  const uiBrief = uiItems.length
    ? `\n4. \`uiSpec\` — one entry per UI item below: \`itemId\` (the item id), \`designSource\` (as given below), \`buildSpec\`, \`sections\` and \`content\` (what the repository builds for the item). By design source:
   - bundle: the owner supplied a cds bundle for the item. Specify it BY REFERENCE to that bundle: \`buildSpec\` is the absolute path of its \`spec/build-spec.md\` given below, \`sections\` the build spec's Section IDs it builds (an empty list when it builds the whole artifact), and \`content\` cites those Sections. Styling comes from that bundle's own stylesheets, so the spec adds no CSS, tokens or component stylesheet.
   - cds: the item changes design and is designed with the CDS design system by the implementing agent. \`buildSpec\` is "" and \`sections\` empty; \`content\` specifies the behaviour and content and states that the design comes from the CDS design system.
   - none: the item changes no design (copy, or data wired into an existing element). \`buildSpec\` is "" and \`sections\` empty; \`content\` specifies the change and states that it changes no design.
The workflow reads the document you save and checks that every UI item has a section headed by its item id, and that a bundle item's section cites the absolute path of its spec/build-spec.md and every Section ID given for it below.\n\nUI items${hasText(a && a.detailingPath) ? ` (each item's element and its from and to state are in the detailing file ${a.detailingPath})` : ''}:\n${uiItems.map((u) => `- ${u.id}${u.element ? ` ${u.element}` : ''}: ${designLine(u)}`).join('\n')}`
    : ''
  const contractsPrompt = (rework) => `Author the ${uiItems.length ? 'four' : 'three'} INTERFACE CONTRACT artifacts for this feature, each under its own key.

1. \`apiSpec\` — the API/OpenAPI contract specification (spec-first). Use the API type the TRD names. Define resources, methods, request/response schemas, status codes, and auth.
2. \`eventContracts\` — the event contracts/schemas. Event names and the envelope follow the event pattern the TRD names. Define each event's name, envelope, and payload schema.
3. \`errorSpec\` — the error-handling specification: error taxonomy, error responses (aligned to the API contract), retry/backoff and idempotency expectations, and how failures surface (errors stay visible — never silently swallowed).${uiBrief}${rework}

${specMakerCtx}${contractsBrief}${pointerNote}`
  const contractsOpts = {
    label: 'author:contracts',
    phase: 'Author specs',
    effort: 'medium',
    agentType: 'api-specification-author',
    schema: uiItems.length ? CONTRACTS_UI_SCHEMA : CONTRACTS_SCHEMA,
  }
  const dataModelBrief = persistBrief(ART, `spec-${artSlug}.data-model.md`, 'the data-model specification you return, with its full content, as a markdown document')
  const criteriaBrief = persistBrief(ART, `spec-${artSlug}.criteria.md`, 'the acceptance criteria and Definition of Done you return, as ONE markdown document with a section for each')
  const pointerNote = ART ? '\n\n`content` in your result need only be a one-line pointer to its section in the document you save.' : ''

  phase('Author specs')

  let [contractsDraft, dataModelSpecDraft, criteriaDraft] = await parallel([
    () => settleAgent(contractsPrompt(''), contractsOpts),
    () =>
      settleAgent(
        `Author the data-model specification for this feature: the data stores the target and delta views show for this repository, designed as those views and the TRD describe them. Define the stores, keys, indexes and item shapes that satisfy every access pattern below.\n\nKnown access patterns:\n${accessPatterns.length ? accessPatterns.map((p, i) => `${i + 1}. ${p}`).join('\n') : '(derive the access patterns from the spec context)'}\n\n${specMakerCtx}${dataModelBrief}${pointerNote}`,
        {
          label: 'author:data-model',
          phase: 'Author specs',
          effort: 'medium',
          agentType: 'data-model-specification-author',
          schema: SPEC_SCHEMA,
        }
      ),
    () =>
      settleAgent(
        `Author two artifacts for this spec, each under its own key.

1. \`acceptanceCriteria\` — testable given/when/then statements covering the happy path, error paths, and boundary conditions. Every behaviour the spec set states gets a criterion; cover each behaviour ONCE rather than enumerating variants of it, and keep each clause under 30 words. At most ${CRITERIA_MAX} criteria.
2. \`definitionOfDone\` — a concrete, verifiable checklist (spec-first OpenAPI present, schemas typed at boundaries, tests defined, docs current, etc.). At most ${DOD_MAX} items.

${criteriaMakerCtx}${criteriaBrief}`,
        {
          label: 'author:criteria',
          phase: 'Author specs',
          effort: 'low',
          agentType: 'acceptance-criteria-writer',
          schema: CRITERIA_SCHEMA,
        }
      ),
  ])

  const deadMakers = [
    ['contracts', contractsDraft],
    ['data-model', dataModelSpecDraft],
    ['criteria', criteriaDraft],
  ].filter(([, d]) => !d).map(([k]) => k)
  if (deadMakers.length) {
    const deaths = dispatchDeaths('Author specs')
    return {
      ok: false,
      stage: 'author',
      reason: `the spec maker(s) ${deadMakers.join(', ')} returned nothing — the spec set is incomplete.`,
      ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
    }
  }

  // The saved spec document is what later phases read, so its UI sections are checked by
  // depscore.py spec-ui-check reading the file, beside the check on the structured uiSpec.
  const uiCheckCommand = `python3 ${shq(beads.script)} spec-ui-check --doc ${shq(`${ART.dir}/spec-${artSlug}.md`)} --items ${shq(JSON.stringify(uiItems.map((u) => ({ id: u.id, designSource: u.designSource, buildSpec: u.buildSpec, sections: u.sections }))))}`
  const uiGapsOf = async (draft, round) => {
    const own = uiCitationGaps(uiItems, draft.uiSpec)
    const doc = await runWrite(`ui-citation-check${round}`, 'Author specs', uiCheckCommand)
    if (doc.error) return { error: `depscore.py spec-ui-check could not check spec-${artSlug}.md: ${doc.error}` }
    const seen = new Set()
    return {
      gaps: [...own, ...(Array.isArray(doc.gaps) ? doc.gaps : [])]
        .filter((g) => g && hasText(g.id) && hasText(g.problem))
        .filter((g) => !seen.has(`${g.id}|${g.problem}`) && seen.add(`${g.id}|${g.problem}`)),
    }
  }
  const uiCheckFailed = (check) => ({ ok: false, stage: 'ui-citation', reason: check.error })
  let uiCheck = uiItems.length ? await uiGapsOf(contractsDraft, '') : { gaps: [] }
  if (uiCheck.error) return uiCheckFailed(uiCheck)
  let uiGaps = uiCheck.gaps
  if (uiGaps.length) {
    log(`UI citation check: ${uiGaps.map((g) => `${g.id}: ${g.problem}`).join('; ')} — the contracts go back to their maker once`)
    const reworked = await settleAgent(
      contractsPrompt(`\n\nREWORK — the workflow's check found UI items whose section, in the uiSpec you returned or in the spec document you saved, is missing or, for a bundle item, does not cite its build spec:\n${uiGaps.map((g) => `- ${g.id}: ${g.problem}`).join('\n')}\nReturn all four artifacts again and save the document again, with a section for every UI item and every bundle item specified by reference to its spec/build-spec.md and its Section IDs.`),
      { ...contractsOpts, label: 'author:contracts:rework' }
    )
    if (reworked) contractsDraft = reworked
    uiCheck = await uiGapsOf(contractsDraft, ':rework')
    if (uiCheck.error) return uiCheckFailed(uiCheck)
    uiGaps = uiCheck.gaps
    if (uiGaps.length) {
      const deaths = dispatchDeaths('Author specs')
      return {
        ok: false,
        stage: 'ui-citation',
        reason: `the UI spec still has gaps after one rework — ${uiGaps.map((g) => `${g.id}: ${g.problem}`).join('; ')}`,
        uiGaps,
        ...(!reworked && deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
      }
    }
  }

  const apiSpec = contractsDraft.apiSpec
  const uiSpec = uiItems.length && Array.isArray(contractsDraft.uiSpec) ? contractsDraft.uiSpec : []
  const eventContracts = contractsDraft.eventContracts
  const errorSpec = contractsDraft.errorSpec
  const dataModelSpec = dataModelSpecDraft

  phase('Emit story')

  const specDigest = [
    ...[['apiSpec', apiSpec], ['dataModelSpec', dataModelSpec], ['eventContracts', eventContracts], ['errorSpec', errorSpec]]
      .map(([k, x]) => `- ${k}: ${(x && hasText(x.summary) && x.summary) || '(no summary)'}`),
    `- acceptanceCriteria: ${Array.isArray(criteriaDraft.acceptanceCriteria) ? criteriaDraft.acceptanceCriteria.length : 0} criteria`,
  ].join('\n')
  const storyCtx = [`Spec ${s.id || ''}: ${s.title || ''}`, s.service ? `Owning service: ${s.service}` : '', s.summary ? `What this spec covers:\n${s.summary}` : '']
    .filter(Boolean)
    .join('\n\n')
  const decisionIds = [...new Set(
    [apiSpec, dataModelSpec, eventContracts, errorSpec]
      .flatMap((x) => (x && Array.isArray(x.decisionIds) ? x.decisionIds : []))
      .map((x) => String(x == null ? '' : x).trim())
      .filter(Boolean)
  )]
  const storyBrief = persistBrief(
    ART,
    `story-${artSlug}.json`,
    `your complete structured result (title, description — exactly as you return them) plus the key "decisionIds" holding exactly this list, ${JSON.stringify(decisionIds)}, as ONE JSON object`
  )

  const storyDraft = await settleAgent(
    `Author the Story bead this Spec pairs with. A Story is scoped to a SINGLE repository — the one named below. Write a title and a description stating what this Story contains in terms of the authored spec set. The Story is a CONTAINER: it is never worked and never itself decomposed — do NOT include a task breakdown, a WSJF score, or any priority.\n\nThis Story's single repository: ${repoPath || '(none supplied)'}\n\nAuthored spec set:\n${specDigest}${specDocPaths.length ? `\n\nThe spec documents:\n${specDocPaths.map((p) => `- ${p}`).join('\n')}` : ''}\n\n${storyCtx}${storyBrief}

Then, once that file is saved and recorded, and before you return, write the Story bead: run exactly this one command, once, in the FOREGROUND (never set run_in_background) with the Bash tool's \`timeout\` parameter set to 600000:

${storyCommand}

It prints one short JSON object. Return its exit code as \`write.exitCode\` and its stdout as \`write.stdout\` (append stderr when the exit code is not 0). Do not retry, do not repair, and run no other bd command.`,
    {
      label: 'author:story-bead',
      phase: 'Emit story',
      effort: 'low',
      agentType: 'agent-teams-workforce:user-story-writer',
      schema: STORY_SCHEMA,
    }
  )

  if (!storyDraft) {
    const deaths = dispatchDeaths('Emit story')
    return {
      ok: false,
      stage: 'story',
      reason: 'the Story writer returned nothing — the Spec has no Story to pair with.',
      ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
    }
  }

  let relayed = null
  try {
    relayed = storyDraft.write ? JSON.parse(storyDraft.write.stdout).summary : null
  } catch (err) {
    relayed = null
  }
  return storyResult({
    unresolvedArtifacts: [],
    spec: {
      id: s.id || null,
      title: s.title || null,
      service: s.service || null,
      repoPath,
    },
    apiSpec,
    dataModelSpec,
    eventContracts,
    errorSpec,
    uiSpec,
    decisionIds,
    outOfRepoFindings: [],
    note: 'The Story is a CONTAINER (no tasks, no WSJF) covering exactly one repo; depscore.py write-story writes its bead.',
  }, relayed, storyDraft)
}

return await main(typeof args === 'string' ? JSON.parse(args) : (args || {}))
