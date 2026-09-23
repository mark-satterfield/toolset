export const meta = {
  name: 'prd-validation',
  description:
    'Leaf mini — PRD Validation. ONE independent validation analyst session inspects the raw PRD through six read-only lenses (ambiguity, completeness, conflict, constraints, domain boundaries, requirements clarification) — plus an INFORMATIONAL BRD traceability mapping when an optional args.brd is supplied, which produces no findings and never binds the PRD — and the script consolidates the lens findings into one validated-PRD package deterministically. The lenses are all CHECKS on a document authored upstream, so folding them into one checker session preserves segregation of duties (no maker judges its own work) while paying one session-start instead of seven. Read-only: it judges and packages the PRD but authors no PRD content.',
  phases: [
    { title: 'Validate', detail: 'one independent analyst session inspects the raw PRD through every lens' },
  ],
}
// ── EVERY DISPATCH IS SETTLED ────────────────────────────────────────────────────
//
// `agent()` fails in two different ways and the scripts used to conflate them. It
// RETURNS NULL when a subagent is skipped or dies on a terminal API error after the
// runtime's own retries. It THROWS when a subagent finishes without calling
// StructuredOutput — and an uncaught throw leaves this script, leaves whatever
// composite called it, and kills the run: two recorded crashes cost 1.13M and 1.88M
// tokens and discarded every artifact the run had already paid for.
//
// So every dispatch in this file goes through settleAgent(). A throw never escapes it,
// and it records what the engine's error text loses — that text reads
// `agent({schema}): subagent completed without calling StructuredOutput`, which names
// neither the agent, nor the phase, nor the schema, and points at no transcript. The
// caller receives null, which every call site already handles, and `dispatchFailures`
// carries the identity of what died, for the `dispatchFailed` report this script owes
// its caller: a phase whose producing agents died is NOT adjudicated.
//
// This block is identical in every workflow script on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text everywhere.
const dispatchFailures = []
// The dispatch deaths belonging to the named phases (every death when none is named).
// A phase whose PRODUCING agents died has no artifact to judge, so its caller must not
// adjudicate it and must not spend a retry on it — that is the `dispatchFailed` contract.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
function settleSchemaName(o) {
  if (typeof o.schemaName === 'string' && o.schemaName) return o.schemaName
  const s = o.schema
  if (!s || typeof s !== 'object') return null
  if (typeof s.title === 'string' && s.title) return s.title
  const req = Array.isArray(s.required) && s.required.length ? s.required : Object.keys(s.properties || {})
  return req.length ? `{${req.join(', ')}}` : null
}
function settleTranscript(err, label) {
  const e = err && typeof err === 'object' ? err : {}
  for (const k of ['transcriptPath', 'transcript', 'agentPath', 'logPath']) {
    if (typeof e[k] === 'string' && e[k]) return e[k]
  }
  const id = typeof e.agentId === 'string' && e.agentId ? e.agentId : null
  if (id) return `agent-${id}.jsonl in this run's workflow transcript directory`
  return `the agent-<id>.jsonl in this run's workflow transcript directory whose agent-<id>.meta.json description is ${JSON.stringify(label)}`
}
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const call = { ...o }
  delete call.schemaName
  const who = {
    agentType: o.agentType || null,
    label: o.label || null,
    phase: o.phase || null,
    schema: settleSchemaName(o),
  }
  const name = who.label || who.agentType || 'agent'
  const whose = `${name}${who.agentType && who.agentType !== name ? ` (${who.agentType})` : ''}${who.phase ? ` in ${who.phase}` : ''}`
  let out = null
  try {
    out = await agent(prompt, call)
  } catch (err) {
    const message = String((err && err.message) || err)
    dispatchFailures.push({
      ...who,
      outcome: 'threw',
      message: message.slice(0, 300),
      transcript: settleTranscript(err, name),
      note: `${whose} finished without a structured result${who.schema ? ` for schema ${who.schema}` : ''}: ${message.slice(0, 160)}`,
    })
    log(`${name}: session ended without a structured result — ${message.slice(0, 160)}`)
    // A caller that owns its own failure reporting asks for the throw back, so the real
    // reason reaches its catch instead of being flattened to "returned no result".
    if (o.rethrow) throw err
    return null
  }
  if (out) return out
  dispatchFailures.push({
    ...who,
    outcome: 'skipped',
    message: null,
    transcript: settleTranscript(null, name),
    note: `${whose} returned nothing — skipped, or died on a terminal API error after the runtime's own retries`,
  })
  log(`${name}: returned nothing — skipped, or died on a terminal API error after the runtime's own retries`)
  return null
}

// ── A LIMIT BELONGS WHERE THE DATA IS MADE, AND AN OVERAGE IS A FLAG ─────────────
//
// Two rules, and they are different rules.
//
// ONE: a limit is never a JSON-Schema maxItems/minItems/maxLength. A schema bound cannot
// trim an over-long answer — the runtime rejects the WHOLE result, the caller receives a
// bare null it cannot tell from a dead agent, and the run halts. One really did, on 61
// items against a bound of 60, claiming files were unread that had been read. So a limit
// is STATED in the prompt and COUNTED here, once the result is in hand.
//
// TWO, and it decides whether a limit may be stated at all: a limit belongs at the layer
// where the data is CREATED, not where it is read. A dispatch that AUTHORS its output —
// criteria, findings, a persona, a draft — chooses its own volume, so a ceiling stated to
// it is a real instruction it can honour. A dispatch that READS or EXTRACTS — an
// inventory of what exists, the evidence found in a repository, the ids it was handed,
// what git printed — has a volume that is a property of the source. Telling it "at most
// N" instructs it to truncate, which loses information, or to lie. Those dispatches get
// NO stated ceiling; bounding what they may DRAW ON (which repository, which files) is
// the guard that works, and it already lives in their prompts. Where a read's volume
// genuinely ought to be smaller, the fix belongs upstream, in whatever made the data.
//
// BOTH kinds are still counted here, because a wildly unexpected count is exactly the
// signal worth having, and nothing is ever truncated, dropped, reordered or summarised at
// any multiple. The count is a GRADUATED FLAG: modestly over the expected figure is
// ordinary variation and reads as an observation; at SCRUTINY_MULTIPLE times it or more,
// the shape is no longer variation — it is what padding, a misread assignment or
// duplicated entries look like — and it is logged prominently so a person looks. 2x is
// the threshold because a single band has to sit above the honest overshoots this
// pipeline actually produces (61 against 60 is 1.02x; the worst recorded lens overshoot
// is well under 1.5x) and below the runaway enumerations the limits exist to catch. It is
// a flag for a person, never a thing the code acts on: neither branch alters control flow.
//
// This block is identical in every workflow script on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text everywhere.
const limitFindings = []
const SCRUTINY_MULTIPLE = 2
function checkLimit(where, what, value, expected, min) {
  const n = Array.isArray(value) ? value.length : typeof value === 'string' ? value.length : null
  if (n === null) return value
  if (typeof expected === 'number' && n > expected) {
    const ratio = expected > 0 ? n / expected : Infinity
    const scrutinise = ratio >= SCRUTINY_MULTIPLE
    limitFindings.push({ where, what, count: n, expected, ratio: Math.round(ratio * 100) / 100, severity: scrutinise ? 'scrutinise' : 'observation' })
    log(
      scrutinise
        ? `⚠ ${where}: ${what} returned ${n} where ${expected} was expected — ${Math.round(ratio * 10) / 10}x. Every item is kept and nothing downstream changes, but a count this far over is the shape of padding, a misread assignment or duplicated entries: worth a look.`
        : `${where}: ${what} returned ${n} where ${expected} was expected — over by ${n - expected}; every item is kept.`
    )
  }
  if (typeof min === 'number' && n < min) {
    limitFindings.push({ where, what, count: n, expected: min, severity: 'under' })
    log(`${where}: ${what} returned ${n}, under the ${min} this asked for — carried through as returned.`)
  }
  return value
}

// args: {
//   prd: { id?, title?, body, repoPath? } | string,  // the raw PRD under validation (required)
//   context?: string,                                 // optional bounded-context / service-boundary notes
//   brd?: string,                                     // OPTIONAL BRD objectives. Supplying one enables an
//                                                     // informational traceability mapping. It is never
//                                                     // required, and it never binds the PRD: the PRD is the
//                                                     // top of the requirements chain.
//   artifacts?: { dir, relDir?, epicId, script, phase, inputs?, beadId? },
//                                                     // the Epic working directory the analyst saves its own
//                                                     // result into (`prd-validation.json`) — see persistBrief
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

// ── ARTIFACT PERSISTENCE ─────────────────────────────────────────────────────────
// When the caller names an Epic working directory, the session that AUTHORED an output
// writes it there once and runs the deterministic recorder, which hashes what is on disk.
// No session copies another session's output. Absent, nothing is written.
const SAFE_ART_PATH = /^\/[A-Za-z0-9._/-]+$/
function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  if (typeof x.dir !== 'string' || !SAFE_ART_PATH.test(x.dir) || x.dir.split('/').includes('..')) return null
  if (typeof x.script !== 'string' || !SAFE_ART_PATH.test(x.script) || x.script.split('/').includes('..')) return null
  if (typeof x.epicId !== 'string' || !/^[A-Za-z0-9._-]+$/.test(x.epicId)) return null
  if (typeof x.phase !== 'string' || !/^[A-Za-z0-9._:-]+$/.test(x.phase)) return null
  return x
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
function persistBrief(art, name, what, opts) {
  if (!art) return ''
  const o = opts || {}
  const file = `${art.dir}/${name}`
  const inputs = (Array.isArray(art.inputs) ? art.inputs : []).filter((p) => typeof p === 'string' && p.trim())
  const record = `python3 ${art.script} record ${file} --epic ${art.epicId} --phase ${art.phase}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  const steps = [
    `1. Write ${what} to ${file} with the Write tool, replacing the whole file if it exists (the Write tool refuses to overwrite a file this session has not read: Read it first, then Write). Write no other file for this.`,
    `2. Then run exactly this command${o.extraInputs ? `, adding ${o.extraInputs} as further --inputs values (add \`--inputs\` if the command has none)` : ''}:\n   ${record}\n   It hashes the file as it is on disk and prints the recorded metadata as JSON, including \`sha256\`.`,
  ]
  const relOk = typeof art.relDir === 'string' && /^[A-Za-z0-9._/-]+$/.test(art.relDir) && !art.relDir.startsWith('/')
  if (o.beadKey && relOk && typeof art.beadId === 'string' && /^[A-Za-z0-9._-]+$/.test(art.beadId)) {
    steps.push(`3. Then record it on the bead that owns it:\n   bd update ${art.beadId} --set-metadata artifact_${o.beadKey}_path=${art.relDir}/${name} --set-metadata artifact_${o.beadKey}_sha256=<the sha256 that step 2 printed>`)
  }
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN. This file is the durable copy a later run of this Epic resumes from instead of re-authoring it, and no other session will write it for you.\n${steps.join('\n')}\nIf a step fails, say so in your result and still return your result. Never improvise another way to write, move or record the file.`
}
const ART = artifactsFrom(a.artifacts)
const prdInput = a.prd || {}
const prdBody = typeof prdInput === 'string' ? prdInput : prdInput.body || ''
const prdId = typeof prdInput === 'string' ? '' : prdInput.id || ''
const prdTitle = typeof prdInput === 'string' ? '' : prdInput.title || ''
const repo = (typeof prdInput === 'string' ? '' : prdInput.repoPath) || '(repo path not provided)'
const context = a.context || '(no bounded-context / service-boundary notes supplied)'
const brd = a.brd || (typeof prdInput === 'string' ? '' : prdInput.brd) || ''

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

if (!prdBody) {
  return {
    ok: false,
    reason: 'prd-validation invoked with an empty PRD body — nothing to validate.',
    validatedPrd: null,
    findings: [],
    ambiguities: [],
    conflicts: [],
    completenessGaps: [],
    nfrs: null,
    constraints: [],
    dependencyGraph: null,
    boundaryFindings: [],
  }
}

const prdHeader = `PRD ${prdId} ${prdTitle}`.trim()
const prdBlock = `${prdHeader ? prdHeader + '\n\n' : ''}${prdBody}`

// ── WHICH LENSES GET A CEILING, AND WHICH ONLY GET COUNTED ───────────────────────
//
// The judging lenses COMPOSE their output. An ambiguity, a completeness gap, a conflict,
// a boundary finding and a clarification are all written by the analyst, which chooses
// how finely to split one problem into entries — so a ceiling stated to it is a real
// instruction, and the one it needs: the failure mode here is enumerating restatements of
// a single finding, and the gate re-reads every one of them. Those ceilings are stated in
// the brief, counted below, and never bound in the schema, so a lens one finding over
// cannot cost the run the other five lenses' findings.
//
// THREE ARE READS and get no stated ceiling at all. `constraints` are extracted from the
// PRD — it imposes what it imposes. The BRD traceability mapping (`matrix`,
// `orphanRequirements`, `unimplementedObjectives`) is a correspondence between two
// documents, so its size is decided by those documents and by nothing the analyst does.
// Telling a read to report fewer rows than it found can only be honoured by dropping
// rows. `conflicts[].requirements` is read the same way: how many requirements are in
// tension is a fact about the PRD, not a budget.
//
// Every figure below is what this script expects, used to flag a count worth a look. The
// judging ones are doubled from the schema bounds they used to be, because the largest
// recorded ambiguities list was 8 and the largest completenessGaps 11 against a bound of
// 15 — near enough to fire on a genuinely thorough PRD.
const LENS_FINDINGS_MAX = 30
const CONFLICTS_MAX = 20
const BOUNDARY_FINDINGS_MAX = 25
const CLARIFICATIONS_MAX = 30
const CONFLICT_REQUIREMENTS_EXPECTED = 10
const CONSTRAINTS_EXPECTED = 40
const MATRIX_EXPECTED = 200
const OBJECTIVES_PER_REQUIREMENT_EXPECTED = 20
const TRACEABILITY_LIST_EXPECTED = 100

// A finding-list schema reused across the lenses that emit flat findings.
// Across eleven recorded Epic runs the largest ambiguities list was 8 and the largest
// completenessGaps 11. A lens returning far more than that is usually enumerating
// restatements of one finding, and every extra entry is re-read by the gate — so the
// count is OBSERVED in a log line below and the findings are kept either way.
const findingItems = {
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['requirement', 'issue', 'severity'],
    properties: {
      requirement: { type: 'string' },
      issue: { type: 'string' },
      severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'info'] },
      suggestion: { type: 'string' },
    },
  },
}

phase('Validate')

// ── One session, every lens ──────────────────────────────────────────────────────
// This used to be six (seven with a BRD) separate analyst sessions plus an
// aggregator — eight session-starts to read ONE document. Every lens is an
// independent CHECK on a PRD authored upstream, so segregation of duties is about
// maker-vs-checker, not checker-vs-checker: one session that applies every lens
// judges nothing it produced. The consolidation the aggregator used to do is now
// DETERMINISTIC script code below — folding orphans and clarifications into the
// flat findings list and deriving the verdict are rules, not judgements.
const traceabilitySchema = {
  type: 'object',
  additionalProperties: false,
  required: ['traceable', 'matrix', 'orphanRequirements', 'unimplementedObjectives'],
  properties: {
    traceable: { type: 'boolean' },
    matrix: {
      type: 'array',
      // Informational only — it binds nothing.
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['requirement', 'objectives'],
        properties: {
          requirement: { type: 'string' },
          objectives: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    orphanRequirements: { type: 'array', items: { type: 'string' } },
    unimplementedObjectives: { type: 'array', items: { type: 'string' } },
  },
}

const analysisSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['ambiguities', 'completenessGaps', 'conflicts', 'constraints', 'boundaryFindings', 'clarifications', 'summary'],
  properties: {
    ambiguities: findingItems,
    completenessGaps: findingItems,
    conflicts: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['requirements', 'contradiction', 'severity'],
        properties: {
          requirements: { type: 'array', items: { type: 'string' } },
          contradiction: { type: 'string' },
          severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'info'] },
        },
      },
    },
    constraints: {
      type: 'array',
      // Largest observed: 21.
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['constraint', 'kind', 'explicit'],
        properties: {
          constraint: { type: 'string' },
          kind: { type: 'string' },
          explicit: { type: 'boolean' },
          source: { type: 'string' },
        },
      },
    },
    boundaryFindings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['requirement', 'boundaryCrossed', 'severity'],
        properties: {
          requirement: { type: 'string' },
          boundaryCrossed: { type: 'string' },
          severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'info'] },
          detail: { type: 'string' },
        },
      },
    },
    clarifications: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['requirement', 'question'],
        properties: {
          requirement: { type: 'string' },
          question: { type: 'string' },
          reason: { type: 'string' },
        },
      },
    },
    ...(brd ? { traceability: traceabilitySchema } : {}),
    summary: { type: 'string' },
  },
  ...(brd ? { required: ['ambiguities', 'completenessGaps', 'conflicts', 'constraints', 'boundaryFindings', 'clarifications', 'traceability', 'summary'] } : {}),
}

const analysis = await settleAgent(
  `${rulingsBlock}You are an INDEPENDENT PRD validation analyst. You did not author this PRD and you never rewrite it — you only inspect it, applying EVERY lens below in one pass. Shared ground rules for all lenses:
- This is a WHAT-level PRD. A requirement that names a desired outcome without naming its implementation mechanism is NOT defective — never flag absent mechanism, thresholds, schemas, or quantified NFRs.
- This PRD is one slice of a decomposed set: its \`Specified Elsewhere\` section names the sibling PRD that owns each requirement listed there. A requirement owned by a sibling is not a gap, a cross-PRD contract is not a conflict, and naming a sibling's behavior is not a boundary violation — flag a violation only where this PRD claims to OWN behavior a sibling owns.
- The product is built ITERATIVELY: an absence that may legitimately arrive as its own later PRD is scheduling, not a defect — report it at INFO severity only.
- Keep every issue/question/detail field under 40 words. Report findings, not essays.
- THE LENSES YOU COMPOSE HAVE A CEILING, and nothing past it is read: at most ${LENS_FINDINGS_MAX} entries each in \`ambiguities\` and \`completenessGaps\`, ${CONFLICTS_MAX} in \`conflicts\`, ${BOUNDARY_FINDINGS_MAX} in \`boundaryFindings\` and ${CLARIFICATIONS_MAX} in \`clarifications\`. These are generous against what this phase actually produces — the largest recorded ambiguities list is 8. A lens heading past its ceiling is enumerating restatements of one finding, which costs the gate a re-read of every one of them. \`constraints\` has NO ceiling: the PRD imposes what it imposes, and you are reading them out of it rather than deciding how many to write.

Lens 1 — AMBIGUITY (return in \`ambiguities\`): requirements whose intended user-observable behavior is genuinely unclear, internally contradictory, or open to two incompatible readings, each with a concrete clarification.
Lens 2 — COMPLETENESS (return in \`completenessGaps\`): each requirement should name an actor, a trigger, and an observable user outcome, with acceptance criteria as observable behavior; flag missing user-observable paths (cancel, error, empty/limit states) described as behavior.
Lens 3 — CONFLICT (return in \`conflicts\`): pairs (or sets) of requirements whose WHAT cannot both hold, citing the requirements in tension.
Lens 4 — CONSTRAINTS (return in \`constraints\`): the explicit AND implied constraints the PRD imposes (regulatory, business, platform, policy), each with its source, kind, and explicit/implied.
Lens 5 — DOMAIN BOUNDARIES (return in \`boundaryFindings\`): requirements that make this feature own behavior another feature or service owns, or that sit in more than one bounded context.
Lens 6 — CLARIFICATION REQUESTS (return in \`clarifications\`): the open questions the author must answer before this PRD can be specified — do not resolve them.
${brd ? `Lens 7 — BRD TRACEABILITY (return in \`traceability\`) — INFORMATIONAL ONLY, NOT A JUDGMENT OF THE PRD: map each PRD requirement to the BRD objective(s) it serves. List in orphanRequirements those that map to no objective, and in unimplementedObjectives those objectives no requirement serves (only where this single PRD could plausibly have served them). Set \`traceable\` to say whether a mapping could be built at all — it is NOT a verdict on the PRD. A requirement mapping to a stated objective or guiding principle is traced; the BRD states objectives, not features.

THIS LENS NEVER PRODUCES A DEFECT. The PRD is the top of the requirements chain and answers to no document above it, so a requirement that traces to no BRD objective is perfectly valid and must NOT be reported as a problem, a gap, an ambiguity, or a conflict through this or any other lens. You are recording a correspondence, not auditing the PRD against the BRD.

BRD objectives:
${brd}
` : ''}
Also return \`summary\`: a plain-language readout (under 120 words) of the PRD's readiness for downstream specification.

Bounded-context / service-boundary notes:
${context}

Repository under consideration: ${repo}

PRD under validation:
${prdBlock}

READING BUDGET (binding): the PRD is quoted in full above and it is the entire object of every lens — a PRD is judged on what it SAYS, so the codebase cannot make an ambiguous requirement clear or a conflict go away. Read nothing unless a lens turns on a specific sibling PRD named in \`Specified Elsewhere\`, and then read only that document. Do not survey the repository or the polyrepo. Roughly five tool calls is the expected shape, and zero is a correct answer.${persistBrief(ART, 'prd-validation.json', 'your complete structured result — every key you return, exactly as you return it — as ONE JSON object')}`,
  {
    label: 'validate:all-lenses',
    // Every lens is a CHECK on a document authored upstream, applied against stated
    // criteria — the cheapest kind of judgment. Nothing here decides anything that is
    // expensive to reverse: a blocker sends the PRD back to its author.
    effort: 'low',
    phase: 'Validate',
    schema: analysisSchema,
  }
)

// ── A DEAD AGENT IS NOT A VERDICT ───────────────────────────────────────────────
//
// `agent()` returns null when the subagent was skipped or died on a terminal API error
// after the runtime's own retries. The PRD was not found wanting; nobody looked at it.
// Without `dispatchFailed` the caller's gate treats this as a failed validation, spends
// its retry budget re-dispatching into the same wall, and hands the supervisor a work
// failure at stage 'prd-validation' — which charges the bead for an account limit.
if (!analysis) {
  return {
    ok: false,
    dispatchFailed: true,
    dispatchFailures: ['validate:all-lenses (validation analyst)'],
    reason:
      'the validation analyst session returned nothing — it was skipped or died on a terminal API error, so the PRD ' +
      'was not judged. This is a DISPATCH failure, not a finding against the PRD.',
    validatedPrd: null,
    findings: [],
    ambiguities: [],
    conflicts: [],
    completenessGaps: [],
    nfrs: null,
    constraints: [],
    dependencyGraph: null,
    boundaryFindings: [],
  }
}

const ambiguities = analysis.ambiguities || []
const completenessGaps = analysis.completenessGaps || []
const conflicts = analysis.conflicts || []
const constraints = analysis.constraints || []
const boundaryFindings = analysis.boundaryFindings || []
const clarifications = analysis.clarifications || []
const traceability = brd
  ? analysis.traceability || { traceable: false, matrix: [], orphanRequirements: [], unimplementedObjectives: [] }
  : { traceable: false, matrix: [], orphanRequirements: [], unimplementedObjectives: [] }

// Counted, never a gate. The judging lenses were given their ceiling in the brief; the
// reads were given none. Every finding is consolidated below whatever the counts say.
checkLimit('Validate', 'ambiguities', ambiguities, LENS_FINDINGS_MAX)
checkLimit('Validate', 'completenessGaps', completenessGaps, LENS_FINDINGS_MAX)
checkLimit('Validate', 'conflicts', conflicts, CONFLICTS_MAX)
for (const c of conflicts) checkLimit('Validate', 'the requirements cited by a conflict', c && c.requirements, CONFLICT_REQUIREMENTS_EXPECTED)
checkLimit('Validate', 'constraints', constraints, CONSTRAINTS_EXPECTED)
checkLimit('Validate', 'boundaryFindings', boundaryFindings, BOUNDARY_FINDINGS_MAX)
checkLimit('Validate', 'clarifications', clarifications, CLARIFICATIONS_MAX)
// The traceability lens is informational and binds nothing, which is exactly why a bound
// on it must never have been able to take the six judging lenses down with it.
checkLimit('Validate (traceability)', 'matrix', traceability.matrix, MATRIX_EXPECTED)
for (const row of Array.isArray(traceability.matrix) ? traceability.matrix : []) {
  checkLimit('Validate (traceability)', 'the objectives cited by one requirement', row && row.objectives, OBJECTIVES_PER_REQUIREMENT_EXPECTED)
}
checkLimit('Validate (traceability)', 'orphanRequirements', traceability.orphanRequirements, TRACEABILITY_LIST_EXPECTED)
checkLimit('Validate (traceability)', 'unimplementedObjectives', traceability.unimplementedObjectives, TRACEABILITY_LIST_EXPECTED)

// ── Deterministic consolidation ─────────────────────────────────────────────────
// The flat findings list and the verdict are RULES over the typed lens outputs, so
// they are computed here rather than asked of a second session. Each clarification
// folds in as 'info' (its open question is the issue), which alone never fails the
// gate — only a blocker-severity defect in the PRD's WHAT does.
//
// THE TRACEABILITY LENS FOLDS IN NOTHING. A BRD may exist and a caller may pass one,
// but the PRD is the top of the requirements chain and answers to no document above
// it. A requirement that maps to no BRD objective is therefore not a defect, and the
// mapping is returned as information rather than scored as a finding.
const findings = []
for (const f of ambiguities) findings.push({ source: 'ambiguity', requirement: f.requirement, issue: f.issue, severity: f.severity })
for (const f of completenessGaps) findings.push({ source: 'completeness', requirement: f.requirement, issue: f.issue, severity: f.severity })
for (const f of conflicts) findings.push({ source: 'conflict', requirement: (f.requirements || []).join(' + '), issue: f.contradiction, severity: f.severity })
for (const f of boundaryFindings) findings.push({ source: 'domain-boundary', requirement: f.requirement, issue: `crosses boundary: ${f.boundaryCrossed}${f.detail ? ` — ${f.detail}` : ''}`, severity: f.severity })
for (const c of clarifications) findings.push({ source: 'clarification', requirement: c.requirement, issue: c.question, severity: 'info' })
const rank = { blocker: 0, major: 1, minor: 2, info: 3 }
const sevRank = (s) => (rank[s] === undefined ? 4 : rank[s])
findings.sort((x, y) => sevRank(x.severity) - sevRank(y.severity))
const validationVerdict = findings.some((f) => f.severity === 'blocker') ? 'fail' : 'pass'

const ledger = {
  phase: 'prd-validation',
  beadId: null,
  subject: prdId || null,
  chosen: ['validation-analyst-combined' + (brd ? '+brd-traceability' : '')],
  mode: 'combined', // one checker session carries every lens; consolidation is deterministic
  ok: validationVerdict === 'pass',
}

return {
  ok: validationVerdict === 'pass',
  validationVerdict,
  summary: analysis.summary,
  // The validated PRD package: the original PRD plus its consolidated findings.
  validatedPrd: {
    id: prdId || null,
    title: prdTitle || null,
    body: prdBody,
    verdict: validationVerdict,
  },
  findings,
  ambiguities,
  conflicts,
  completenessGaps,
  nfrs: null,
  constraints,
  dependencyGraph: null,
  boundaryFindings,
  clarifications,
  traceability,
  // Every lens list that came back longer than its stated ceiling, with its count. The
  // findings above are complete regardless; this says what they cost.
  ...(limitFindings.length ? { limitFindings } : {}),
  ledger,
}
