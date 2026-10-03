export const meta = {
  name: 'trd-authoring',
  description:
    'Leaf mini — authors a Technical Requirements Document (TRD) from a PRD plus the approved target and delta of its architecture. A filing-clerk session names the TRD file when the caller gives no path, then one trd-author session reads the owner\'s constraints in section 2, the target and delta views, and the effective views of the elements the delta adds or changes, and writes the TRD in one pass: PRD business requirements that need technical elaboration plus the obligations the architecture imposes on the elements the delta adds or changes, each citing its PRD requirement or the view path it comes from and naming the element it applies to. Refuses a run with no target and delta. A technical rule reaches the TRD from the architecture, never from the PRD.',
  phases: [
    { title: 'Author TRD', detail: 'author the TRD from the PRD and the target and delta views, one pass' },
  ],
}
// BEGIN interruption propagation — no retry or replay of completed dispatches.
let dispatchInterruption = null
function dispatchOutcome(result) {
  if (!dispatchInterruption) return result
  const out = result && typeof result === 'object' ? result : {}
  return { ...out, ok: false, dispatchFailed: true, paused: true, resumable: true,
    stage: dispatchInterruption.stage, reason: dispatchInterruption.message, headline: dispatchInterruption.message,
    ...(typeof out.passed === 'boolean' ? { passed: false } : {}),
    ...(out.ledger ? { ledger: { ...out.ledger, ok: false } } : {}), dispatchInterruption }
}
function dispatchFailureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = [e.message || err || '', e.type, e.code, e.error && e.error.type].join(' ')
  if (/structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i.test(text)) return 'deterministic'
  if (/insufficient_quota|quota|usage[ _-]?limit|spend[ _-]?limit|session[ _-]?limit|credit balance|out of credits|hit your limit|token limit|account.quota.exhausted/i.test(text)) return 'exhausted'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((value) => Number(value)).find((value) => Number.isFinite(value) && value >= 100 && value < 600)
  return [408, 425, 429, 500, 502, 503, 504, 529].includes(status) || /overload|rate[ _-]?limit|too many requests|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i.test(text) ? 'transient' : 'deterministic'
}
function captureDispatchInterruption(err, name) {
  const cause = dispatchFailureCause(err)
  if (cause === 'deterministic') return
  const stage = cause === 'exhausted' ? 'account-quota-exhausted' : 'api-unavailable'
  dispatchInterruption = { stage, message: stage + ': ' + name + ': ' + String((err && err.message) || err) }
}
// END interruption propagation

const dispatchFailures = []
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  return named.length ? dispatchFailures.filter((f) => named.includes(f.phase)) : dispatchFailures.slice()
}
// Runs agent(); returns its result, or null after recording the failure in dispatchFailures.
async function settleAgent(prompt, opts) {
  if (dispatchInterruption) return null
  const o = opts || {}
  const who = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null }
  const name = who.label || who.agentType || 'agent'
  try {
    const out = await agent(prompt, o)
    if (out) return out
    dispatchFailures.push({ ...who, outcome: 'skipped', note: `${name} returned nothing` })
    log(`${name}: returned nothing`)
  } catch (err) {
    captureDispatchInterruption(err, (opts && (opts.label || opts.agentType)) || 'agent')
    const message = String((err && err.message) || err).slice(0, 300)
    dispatchFailures.push({ ...who, outcome: 'threw', message, note: `${name} ended without a structured result: ${message}` })
    log(`${name}: ended without a structured result — ${message}`)
  }
  return null
}

// args: {
//   prd: { id?, title?, path?, content?, acceptanceCriteria?: any[] },
//   archPath,
//   trdPath?, repoPath?, feedback?,
//   architecture: { subject, targetDir, deltaDir, items?: [{ id, element, views }], decisionPath? } (the approved target and its delta),
//   artifacts?: { dir, relDir?, epicId, script, phase, inputs?, beadId? }
// }
// returns { ok, trdPath, filingPath, trd, decisionIds } or { ok: false, stage, reason, ... }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  return ['dir', 'script', 'epicId', 'phase'].every((k) => typeof x[k] === 'string' && x[k]) ? x : null
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
function persistBrief(art, name, what, opts) {
  if (!art) return ''
  const o = opts || {}
  const file = `${art.dir}/${name}`
  const inputs = (Array.isArray(art.inputs) ? art.inputs : []).filter((p) => typeof p === 'string' && p.trim())
  const record = `python3 ${art.script} record ${file} --epic ${art.epicId} --phase ${art.phase}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  const steps = [
    `1. Write ${what} to ${file} with the Write tool, replacing the whole file if it exists (Read it first, then Write). Write no other file for this.`,
    `2. Then run exactly this command:\n   ${record}\n   It prints the recorded metadata as JSON, including \`sha256\`.`,
  ]
  if (o.beadKey && typeof art.relDir === 'string' && art.relDir && typeof art.beadId === 'string' && art.beadId) {
    steps.push(`3. Then record it on the bead that owns it:\n   bd update ${art.beadId} --set-metadata artifact_${o.beadKey}_path=${art.relDir}/${name} --set-metadata artifact_${o.beadKey}_sha256=<the sha256 that step 2 printed>`)
  }
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN.\n${steps.join('\n')}\nIf a step fails, say so in your result and still return your result.`
}
const ART = artifactsFrom(a.artifacts)
const prd = a.prd || {}
const repo = a.repoPath || '(repo path not provided)'
let trdPath = a.trdPath || null


const prdContent = typeof prd.content === 'string' && prd.content.trim().length > 0
const prdPath = typeof prd.path === 'string' && prd.path.startsWith('/') ? prd.path : ''
if (!prdContent && !prdPath) {
  const why = 'no PRD supplied — prd.content is empty and prd.path is not an absolute path. Pass the PRD content or its path.'
  return dispatchOutcome({ ok: false, stage: 'input', deterministicFailure: true, error: why, reason: why })
}
const archPath = typeof a.archPath === 'string' ? a.archPath.trim() : ''
if (!archPath.startsWith('/')) {
  const why = 'no architecture supplied — archPath is not an absolute path. Set ATW_ARCH_PATH for the run, or pass archPath.'
  return dispatchOutcome({ ok: false, stage: 'input', deterministicFailure: true, error: why, reason: why })
}

const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const target = a.architecture && typeof a.architecture === 'object' ? a.architecture : null
if (!target || !hasText(target.targetDir) || !hasText(target.deltaDir)) {
  const why = 'no approved target and delta supplied — architecture.targetDir and architecture.deltaDir name the views the TRD states obligations on.'
  return dispatchOutcome({ ok: false, stage: 'input', deterministicFailure: true, error: why, reason: why })
}

const died = (...phases) => {
  const deaths = dispatchDeaths(...phases)
  return deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}
}

const archText = `THE ARCHITECTURE is at ${archPath}. It is not inside the product repository ${repo}. Its \`arc42/\` folder is the effective version (the approved architecture), its \`target/\` folder holds the targets in progress, and the architecture documentation model in its \`reference/\` folder says what each version and section holds.
- \`arc42/02-architecture-constraints\` holds the owner's constraints. Read its README.md in full.
- \`arc42/04-solution-strategy\` holds the enterprise-level strategy. Read its README.md.
- Every other arc42 section is the design so far, as views. Each view's frontmatter names its \`view_type\`, \`scope\`, \`subject\` and every element it \`shows\`: that frontmatter is the catalog.
- THIS PRD'S APPROVED TARGET is ${target.targetDir}, and the change alone, its delta, is ${target.deltaDir}. Read every delta view in full, and the target views that show the elements the delta adds or changes. For each such element, find its effective views by searching the catalog frontmatter (\`subject:\` and the \`shows:\` lists) for the element's name, at every scope, and read them. The views in \`arc42/08-crosscutting-concepts\` describe patterns used across services; read every one whose concept applies to an element the delta adds or changes.
- When a relevant architecture view selects a scoped UI design/mock or hand-off package, follow that reference and preserve its identity and scope in the applicable TRD obligation with the architecture citation. Do not substitute a newer unrelated mock or promote other advisory mocks to requirements. Report missing or conflicting references in your summary; do not invent package paths. Consumed by: spec-authoring — carries the applicable design obligation into the implementation contract.
- Other open targets in \`target/\` that show the same elements are designs in progress; read them, so this TRD does not contradict them.`
const prdText = prdContent
  ? prd.content
  : `PRD ${prd.id || ''}${prd.title ? `: ${prd.title}` : ''}\n\nThe PRD is the document at ${prdPath}. Read that ONE file in full before you author anything; every requirement in it is in scope.`

const deltaItems = (Array.isArray(target.items) ? target.items : []).filter((i) => i && hasText(i.id) && hasText(i.element))
const deltaBlock = `\nTHE ELEMENTS THE DELTA SHOWS (the delta items; name each requirement's \`appliesTo\` as the item's element is named here):\n${deltaItems.length ? deltaItems.map((i) => `- ${i.id}: ${i.element}`).join('\n') : '(read them from the delta views\' \`shows\` frontmatter)'}\n${hasText(target.decisionPath) ? `The architecture decision that approved the target is the document at ${target.decisionPath}.\n` : ''}`
const feedback = typeof a.feedback === 'string' && a.feedback.trim() ? `[Gate feedback from the previous run of this phase] ${a.feedback.trim()}` : ''

phase('Author TRD')

if (!trdPath) {
  const home = await settleAgent(
    `Decide the ONE correct absolute file path for the Technical Requirements Document described below, using this project's documentation conventions and knowledge base. Do not author the TRD and do not create the file — return only where it belongs.

If a TRD for this subject already exists, return ITS path so the document is updated in place rather than duplicated.

Subject: ${prd.id || prd.title || 'TRD'}
PRD title: ${prd.title || '(untitled)'}
Repository the run is working in: ${repo}`,
    {
      label: 'trd:filing-home',
      phase: 'Author TRD',
      effort: 'low',
      agentType: 'filing-clerk',
      schema: {
        type: 'object', additionalProperties: false, required: ['ok'],
        properties: { ok: { type: 'boolean' }, path: { type: 'string' }, existing: { type: 'boolean' }, error: { type: 'string' } },
      },
    }
  )
  if (home && home.ok === true && typeof home.path === 'string' && home.path.startsWith('/')) {
    trdPath = home.path
    log(`TRD home ruled by the filing clerk: ${trdPath}`)
  } else {
    trdPath = '(no path supplied — ask the filing clerk before writing)'
  }
}

const authorPath = ART ? `${ART.dir}/trd.md` : trdPath
const filingPath = typeof trdPath === 'string' && trdPath.startsWith('/') ? trdPath : null
const writeBrief = ART
  ? `WRITE THE TRD AS MARKDOWN BEFORE YOU RETURN, as the steps at the end of this brief say. \`trdPath\` in your result must be ${authorPath}.${filingPath ? ` Do NOT write it to ${filingPath}.` : ''}\n`
  : `WRITE THE TRD TO THIS FILE BEFORE YOU RETURN: ${trdPath}
Create any missing parent directories. \`trdPath\` in your result must be the path you actually wrote.
`
const MAX_REQUIREMENTS = 40
log(`Authoring TRD at ${authorPath}`)

const trd = await settleAgent(
  `Author the Technical Requirements Document (TRD). Write the TRD; do not write production code. Work within the repository at: ${repo}

WHAT THIS DOCUMENT IS FOR. The TRD is the single point at which the obligations the architecture imposes enter the build chain. The Specs, Stories and Tasks are built from it; an obligation that does not reach the TRD is built by nobody. It is NOT the full HOW — the detailed HOW lives in the Specs and Tasks. Make sure the right obligations are PRESENT AND SOURCED.

THE TRD'S REQUIREMENTS COME FROM TWO SOURCES.

1. PRD BUSINESS REQUIREMENTS THAT NEED TECHNICAL ELABORATION. One PRD requirement may need several technical requirements, and several may be answered by one. A PRD line that states a rule about how the system is built is not a business requirement and is not a source: a technical rule reaches the TRD only from the architecture, under the condition below.

2. THE OBLIGATIONS THE ARCHITECTURE IMPOSES, WHICH NO PRD WOULD EVER STATE. These have NO PRD parent. System uptime, latency, maintainability, security, failover, disaster recovery, specific infrastructure and CDK instructions, and observability: where the architecture describes how a service is observed, and this PRD results in that kind of service being built, the TRD says what that service must provide for it. The same class covers throughput and latency budgets, data modelling, API contracts, encryption, retention and auth protocols, and monitoring and alerting. The architecture views describe which of these this system has.

Read the architecture as the block below says, and for every view you read ask what it demands of anything this PRD builds.

SOURCE EVIDENCE HANDOFF. ${typeof a.surveyPath === 'string' && a.surveyPath.trim() ? `The existing architecture survey is ${a.surveyPath}. Read its relevant coverage/claim entries and evidenceRefs; do not paste or repeat the whole survey.` : 'No survey path was supplied; treat implementation evidence not otherwise provided as unknown and use only targeted reads.'} Each evidenceRef carries path, heading, repo, revision and url (unused fields are empty). Preserve the exact relevant repository path, commit revision, file:line or document heading, and claim/coverage ID alongside the TRD requirement ID in the existing summary/context and requirement prose. Implementation evidence describes what exists; PRD and architecture references remain the authority for what is required. Before a new source read, state in that context which obligation is already established and the changed revision, missing evidence or unanswered question that requires the read. Compare the named repository's main revision with the recorded revision; unchanged, sufficient evidence can be reused. A changed revision or legacy citation without revision requires a targeted check of the affected source; preserve prior evidence as historical rather than inventing a revision. Test code read is not test execution.

EXISTING IMPLEMENTATION CONTEXT. Use the supplied architecture survey and target/delta citations to identify the existing owning repository and integration points. Within this authoring pass, inspect relevant available entrypoints, contracts and focused tests when needed to distinguish a remaining obligation from an already implemented one; do not perform a new fleet survey. Code is neither presumed correct nor discarded because its provenance is uncertain. State material gaps or unknowns, with file:line evidence, in the TRD's existing summary/context; reading tests does not prove they pass or exercise live dependencies. Requirements remain the source of the desired behavior. Preserve supported behavior and compatible published contracts, and describe the incremental obligation on the named element. A missing implementation is implementation work, not a new product feature; a PRD does not itself authorize a new repository or service. Do not silently redesign an approved target: report an evidenced contradiction for resolution. The later per-repository detailing supplies the precise from/to comparison for Specs and Tasks.

AN OBLIGATION BINDS ONLY WHAT THE DELTA ADDS OR CHANGES. An obligation about a kind of thing (an S3 bucket, a Lambda function, a DynamoDB table, a VPC endpoint) is stated only where the delta adds or changes that thing, and the requirement names it: "the delta adds bucket <name>, so <name> is versioned and SSE-S3 encrypted [<view path>]". An element the delta does not touch carries no obligation here, and an obligation is never a reason to add the thing it governs: things are added by the target. Set \`appliesTo\` on every requirement to the element it governs, named as the delta names it.

EFFECTIVE FILES ARE REVIEWED. \`lifecycle_state: effective\` means a file was reviewed and approved: it is the design so far, followed as the established pattern, not a fixed rule. Cite it. The TRD states obligations on the design and does not redesign it: where a requirement would depart from an effective view, name the view and the departure in your \`summary\` for the architecture step. This PRD's target and delta views read \`in-review\` because they are integrated after review; the architecture step approved them, and they are the design you state obligations on. Any other file in a state other than \`effective\` is open to review: before a requirement rests on one, check it against the PRD and the target, and name each such file you rely on in your \`summary\`. Read the field in every file you open.

CITE THE ARCHITECTURE; DO NOT RESTATE IT. A requirement that names the obligation and cites the view path that describes it (a target, delta or effective view) is complete and is the preferred shape. Where the architecture already settles a point a PRD requirement raises, cite that view. A correct TRD is often very short; where the architecture obliges nothing new, write nothing for it.

${writeBrief}
PRD (source of product requirements):
${prdText}
${deltaBlock}
${Array.isArray(prd.acceptanceCriteria) && prd.acceptanceCriteria.length ? `\nPRD acceptance criteria:\n${prd.acceptanceCriteria.map((x, i) => `${i + 1}. ${typeof x === 'string' ? x : JSON.stringify(x)}`).join('\n')}` : ''}

${archText}
${feedback ? `\nFeedback on the previous version from the gate — address every point:\n${feedback}` : ''}

Each technical requirement has a stable ID, NAMES ITS SOURCE, names the design element it applies to, and is verifiable. The source is EITHER a PRD requirement (in \`prdRefs\`) OR an architecture view (in \`archRefs\`); an architecture-sourced requirement carries an empty \`prdRefs\`. Where a requirement and a view disagree, name the disagreement in your \`summary\` with both citations.

Return at most ${MAX_REQUIREMENTS} technical requirements, each under 60 words, and keep the TRD document under about 25,000 characters: consolidate related obligations into one requirement rather than splitting them. Cite every view a requirement rests on in \`archRefs\`.

CITE THE VIEWS IN THE DOCUMENT AS WELL AS IN YOUR RESULT: YAML frontmatter at the top of the TRD with \`decisionIds:\` listing every view any requirement depends on, and on each requirement the views it depends on. Cite an effective view by its path relative to the arc42 folder and a target or delta view by its path relative to the architecture directory (for example \`target/<subject>/delta/<section>/<view>.md\`), with \`#<heading>\` when the requirement rests on one part of it; cite only files you read, and never a section number in place of one.${persistBrief(ART, 'trd.md', 'the complete TRD as a markdown document', { beadKey: 'trd' })}`,
  {
    label: 'author:trd',
    phase: 'Author TRD',
    effort: 'medium',
    agentType: 'trd-author',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['trdPath', 'requirements'],
      properties: {
        trdPath: { type: 'string' },
        decisionIds: { type: 'array', items: { type: 'string' } },
        requirements: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['id', 'requirement', 'appliesTo', 'prdRefs', 'archRefs', 'verification'],
            properties: {
              id: { type: 'string' },
              requirement: { type: 'string' },
              appliesTo: { type: 'string' },
              prdRefs: { type: 'array', items: { type: 'string' } },
              archRefs: { type: 'array', items: { type: 'string' } },
              verification: { type: 'string' },
            },
          },
        },
        summary: { type: 'string' },
        notes: { type: 'string' },
      },
    },
  }
)
if (!trd) return dispatchOutcome({ ok: false, stage: 'author', reason: 'TRD authoring produced nothing', ...died('Author TRD') })
const resultPath = ART ? authorPath : trd.trdPath || trdPath
if (typeof resultPath === 'string' && resultPath.startsWith('/')) trd.trdPath = resultPath

return dispatchOutcome({
  ok: true,
  trdPath: resultPath,
  filingPath,
  trd,
  decisionIds: [...new Set([
    ...(Array.isArray(trd.decisionIds) ? trd.decisionIds : []),
    ...(Array.isArray(trd.requirements) ? trd.requirements : []).flatMap((r) => (Array.isArray(r.archRefs) ? r.archRefs : [])),
  ].map((x) => String(x == null ? '' : x).trim()).filter(Boolean))],
})
