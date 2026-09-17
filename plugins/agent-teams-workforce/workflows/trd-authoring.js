export const meta = {
  name: 'trd-authoring',
  description:
    'Leaf mini — authors a Technical Requirements Document (TRD) from a PRD plus an arc42 SAD extract. A read-only extractor pulls the SAD source feeds (constraints, solution strategy, crosscutting) into a typed packet; the trd-author writes the TRD; ONE independent checker session performs both checks (structure/quality + bidirectional PRD<->TRD traceability) — merged checks in one checker session, never a maker checking itself. Maker never judges its own work; on a bounded maker-checker deadlock the trd-decider rules, and a "revise" ruling is carried out: one targeted author pass with the required changes, then one independent re-check. Gate feedback from a previous run of this phase seeds the first author pass. Read/author only — no production code.',
  phases: [
    { title: 'Extract SAD', detail: 'read-only extraction of the arc42 source feeds into a typed packet' },
    { title: 'Author TRD', detail: 'author the TRD from the PRD + SAD extract (maker)' },
    { title: 'Verify & Traceability', detail: 'independent validation + PRD<->TRD traceability; decider on deadlock' },
  ],
}

// args: {
//   prd: { id?, title?, path?, content?, acceptanceCriteria?: any[] },  // the source PRD
//   sad: { path?, sectionLayout?: 'single-file' | 'one-file-per-section' }, // arc42 SAD location
//   trdPath?: string,        // where the TRD should be written/lives
//   repoPath?: string,       // working repo for file reads/writes
//   maxLoops?: number,       // bounded maker-checker passes (default 2)
//   feedback?: string,       // gate feedback from a previous run of this phase; seeds the first author pass
//   artifacts?: { dir, relDir?, epicId, script, phase, inputs?, beadId? },
//                            // the Epic working directory. When present the author writes the TRD to
//                            // <dir>/trd.md and records it; trdPath is then the FILING home the
//                            // document is copied to on Done, returned as `filingPath`.
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
const prd = a.prd || {}
const sad = a.sad || {}
const repo = a.repoPath || '(repo path not provided — ask before editing files)'
// A missing trdPath used to render as a placeholder string, which told the author to
// write the TRD to nowhere. Deciding where a document belongs is NOT this workflow's
// judgment to make — the project's filing clerk owns that, so when the caller names no
// path we ask it rather than inventing one under .claude/. Its ruling is used verbatim.
let trdPath = a.trdPath || null
// Gate retry budget. One rework round, then proceed with the finding recorded.
//
// This was 3, and nested minis carried their own bound of 2 on top, so a single
// phase could burn six expensive attempts before anyone saw a result — the
// dominant cost in every run that stalled. A checker's objection is information;
// it does not have to be a veto. One revision is where nearly all the value is:
// if a maker cannot address a finding on the second try, a third rarely helps and
// the finding is better carried forward than ground against.
//
// Callers who want the old behaviour pass args.maxLoops explicitly.
const MAX_LOOPS = a.maxLoops || 2

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

if (!prd.id && !prd.path && !prd.content) {
  return { ok: false, stage: 'input', error: 'no PRD supplied (id/path/content all empty) — refusing to run without a work item' }
}

const prdRef = prd.path || prd.id || '(inline content)'
const sadRef = sad.path || '(SAD path not provided — ask before extracting)'
const sadLayout = sad.sectionLayout || 'unknown (detect single-file vs one-file-per-section)'

// ── Phase 1: Extract SAD ──────────────────────────────────────────────────────
// Read-only extraction of the four arc42 source sections into a stably-identified
// packet. The extractor authors no TRD content — it only normalizes what the SAD
// states. Invents nothing the SAD does not contain.
phase('Extract SAD')

// ── A PACKET THE CALLER ALREADY HOLDS IS REUSED, NOT RE-BOUGHT ─────────────────
// The composite re-runs this mini when its gate sends the TRD back for rework. The SAD
// cannot change between those passes (a gate that needs the architecture changed
// ESCALATES and ends the run instead of looping), so the second pass used to pay the
// extractor again for the packet the first pass already produced — on 2026-09-16 the
// extractor was 2.26M of 38.0M weighted units across 17 runs. The caller passes the
// first pass's packet back as `args.sadExtract`; only a packet with all three feeds is
// believed, and anything else is extracted fresh.
const isExtract = (x) =>
  !!x && typeof x === 'object' && ['constraints', 'solutionStrategy', 'crosscuttingConcepts'].every((k) => Array.isArray(x[k]))
const suppliedExtract = isExtract(a.sadExtract) ? a.sadExtract : null
if (suppliedExtract) log('SAD extract supplied by the caller from an earlier pass of this run — reused; the extractor is not dispatched')
else log(`Extracting arc42 source feeds from SAD at ${sadRef}`)

const sadExtract = suppliedExtract || await agent(
  `You are READ-ONLY. Extract the decision-bearing sections of the arc42 Software Architecture Document into one typed packet for the TRD author. Do NOT author requirements, do NOT change any file, and invent NOTHING the SAD does not state. Work within the repository at: ${repo}

SAD location: ${sadRef}
SAD layout: ${sadLayout}

READING BUDGET (binding): the SAD is at the location above. Read it and the files it points at — at most 12 files — and do not survey the repository or any other repository for architecture content that is not in the SAD. A section the SAD does not state comes back empty; it is never reconstructed from code.

Locate and normalize each source feed reliably across both single-file and one-file-per-section arc42 layouts:
- Section 2 — Constraints
- Section 4 — Solution Strategy
- Section 8 — Crosscutting Concepts

For every entry: assign a stable ID, capture the verbatim-grounded statement, and note its source location (file:section/anchor). If a section is absent, return it as an empty array — do not fabricate.`,
  {
    label: 'extract:sad',
    phase: 'Extract SAD',
    effort: 'low',
    agentType: 'agent-teams-workforce:sad-source-extractor',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['constraints', 'solutionStrategy', 'crosscuttingConcepts'],
      properties: {
        constraints: { $ref: '#/$defs/feed' },
        solutionStrategy: { $ref: '#/$defs/feed' },
        crosscuttingConcepts: { $ref: '#/$defs/feed' },
        sadLocation: { type: 'string' },
        notes: { type: 'string' },
      },
      $defs: {
        feed: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['id', 'statement', 'source'],
            properties: {
              id: { type: 'string' },
              statement: { type: 'string' },
              source: { type: 'string' },
            },
          },
        },
      },
    },
  }
)
if (!sadExtract) return { ok: false, stage: 'extract', reason: 'SAD extraction produced nothing' }

const extractText = JSON.stringify(sadExtract, null, 2)
const prdText = prd.content
  ? prd.content
  : `PRD ${prd.id || ''}: ${prd.title || ''} (path: ${prd.path || 'n/a'})`

// ── Phases 2 + 3: bounded maker-checker loop ──────────────────────────────────
// The maker (trd-author) writes the TRD; two INDEPENDENT checkers judge it. Neither
// checker ever authored the TRD. On rejection the maker re-runs with the combined
// checker feedback. The script owns this loop in plain JS — no workflow() calls.
let trd = null
let trdValidation = null
let traceabilityMatrix = null
let decision = null
let feedback = typeof a.feedback === 'string' && a.feedback.trim() ? `[Gate feedback from the previous run of this phase] ${a.feedback.trim()}` : ''

// ── WHERE THE TRD LIVES IS THE FILING CLERK'S RULING ─────────────────────────
// A TRD is a durable document, so it needs a real home before it is authored, not a
// path this workflow made up. The clerk already owns that decision for this knowledge
// base: it searches the vault, applies the single-source-of-truth rule, and returns the
// one correct location. Asked once per run, before the authoring loop.
if (!trdPath) {
  const home = await agent(
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
    log(`TRD home ruled by the filing clerk: ${trdPath}${home.existing ? ' (updating an existing TRD in place)' : ''}`)
  } else {
    // The clerk is the authority on location; if it cannot rule, this workflow does not
    // get to substitute a guess. Authoring proceeds and the author is told to ask.
    trdPath = '(no path supplied — ask the filing clerk before writing)'
    log('Filing clerk returned no usable path for the TRD — the author is instructed to ask before writing')
  }
}

// With an Epic working directory the TRD is authored THERE, and the filing home ruled above
// is where it is filed once the run reaches Done — so a TRD from an unfinished run never
// lands in the vault as if it were accepted.
const authorPath = ART ? `${ART.dir}/trd.md` : trdPath
const filingPath = typeof trdPath === 'string' && trdPath.startsWith('/') ? trdPath : null
const writeBrief = ART
  ? `WRITE THE TRD AS MARKDOWN BEFORE YOU RETURN, as the steps at the end of this brief say. \`trdPath\` in your result must be ${authorPath}.${filingPath ? ` Do NOT write it to ${filingPath}: that is where it is filed once the run completes, and that copy is not yours to make.` : ''}\n`
  : `WRITE THE TRD TO THIS FILE BEFORE YOU RETURN: ${trdPath}
Create any missing parent directories. A TRD is a durable document, not a value passed
between phases: returning its text without saving the file means a run that ends early
leaves no TRD anywhere, and the next run re-derives it from nothing. Saving the file is
part of authoring it, not an optional extra, and \`trdPath\` in your result must be the
path you actually wrote.
`

// ── Phase 2: Author TRD (maker) ──────────────────────────────────────────────
// The author reads the shared `feedback`, so every pass carries whatever the checker,
// the gate or the decider last asked for.
function authorTrd(pass) {
  phase('Author TRD')
  log(`Authoring TRD (${pass}) at ${authorPath}`)

  return agent(
    `${rulingsBlock}Author the Technical Requirements Document (TRD). The TRD translates the PRD's product requirements into testable technical requirements, grounded in and consistent with the SAD extract below. Write the TRD; do not write production code. Work within the repository at: ${repo}

${writeBrief}
PRD (source of product requirements):
${prdText}
${Array.isArray(prd.acceptanceCriteria) && prd.acceptanceCriteria.length ? `\nPRD acceptance criteria:\n${prd.acceptanceCriteria.map((x, i) => `${i + 1}. ${typeof x === 'string' ? x : JSON.stringify(x)}`).join('\n')}` : ''}

SAD extract (architecture constraints/strategy/crosscutting the TRD must honor; cite by stable ID):
${extractText}
${feedback ? `\nFeedback on the previous version (checker, gate or decider) — address every point:\n${feedback}` : ''}

Each technical requirement must have a stable ID, trace upward to a PRD requirement, cite any SAD source IDs it depends on, and be verifiable. Deliver the TRD file path(s) you wrote, the structured requirements, and the upstream PRD/SAD references each requirement carries.${persistBrief(ART, 'trd.md', 'the complete TRD as a markdown document', { beadKey: 'trd' })}`,
    {
      label: 'author:trd',
      phase: 'Author TRD',
      effort: 'medium',
      agentType: 'agent-teams-workforce:trd-author',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['trdPath', 'requirements'],
        properties: {
          trdPath: { type: 'string' },
          requirements: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['id', 'requirement', 'prdRefs', 'sadRefs', 'verification'],
              properties: {
                id: { type: 'string' },
                requirement: { type: 'string' },
                prdRefs: { type: 'array', items: { type: 'string' } },
                sadRefs: { type: 'array', items: { type: 'string' } },
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
}

// ── Phase 3: Verify & Traceability — ONE independent checker session, both checks ─
// This used to be two parallel checker sessions, each paying a full session-start to
// read the same TRD. Both are independent CHECKS on the maker's artifact — neither
// ever judged the other — so one session carrying both preserves segregation of
// duties (the checker authored nothing) at half the cost.
function verifyTrd() {
  const trdText = JSON.stringify(trd, null, 2)
  phase('Verify & Traceability')

  return agent(
    `You are an INDEPENDENT verifier. You did NOT author this TRD; you only judge it. Do not modify it. Perform BOTH checks below in one pass and return each under its own key. Keep every finding and feedback item under 40 words.

CHECK 1 — structure and quality (return under \`validation\`): required sections present, every requirement has a stable ID and a concrete verification method, requirements are unambiguous and testable, and the TRD is internally consistent with the SAD extract it cites. verdict "pass" only if every check holds; otherwise "reject" with feedback specific enough that the author can fix it without interpretation, and each finding with its severity.

CHECK 2 — bidirectional PRD<->TRD traceability (return under \`traceability\`): every PRD requirement maps forward to at least one TRD requirement (no coverage gaps), and every TRD requirement maps back to a PRD requirement (no orphans). Build the traceability matrix and report gaps in both directions. verdict "pass" only if traceability is complete in BOTH directions with no unexplained gaps or orphans.

PRD (source requirements):
${prdText}
${Array.isArray(prd.acceptanceCriteria) && prd.acceptanceCriteria.length ? `\nPRD acceptance criteria:\n${prd.acceptanceCriteria.map((x, i) => `${i + 1}. ${typeof x === 'string' ? x : JSON.stringify(x)}`).join('\n')}` : ''}

TRD under review:
${trdText}

SAD extract the TRD must stay consistent with:
${extractText}`,
    {
      label: 'verify:trd-and-traceability',
      phase: 'Verify & Traceability',
      effort: 'medium',
      agentType: 'agent-teams-workforce:trd-validator',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['validation', 'traceability'],
        properties: {
          validation: {
            type: 'object',
            additionalProperties: false,
            required: ['verdict', 'findings', 'feedback'],
            properties: {
              verdict: { type: 'string', enum: ['pass', 'reject'] },
              findings: {
                type: 'array',
                items: {
                  type: 'object',
                  additionalProperties: false,
                  required: ['issue', 'severity'],
                  properties: {
                    issue: { type: 'string' },
                    severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
                    location: { type: 'string' },
                  },
                },
              },
              feedback: { type: 'string' },
            },
          },
          traceability: {
            type: 'object',
            additionalProperties: false,
            required: ['verdict', 'links', 'prdGaps', 'trdOrphans', 'feedback'],
            properties: {
              verdict: { type: 'string', enum: ['pass', 'reject'] },
              links: {
                type: 'array',
                items: {
                  type: 'object',
                  additionalProperties: false,
                  required: ['prdRef', 'trdRef'],
                  properties: {
                    prdRef: { type: 'string' },
                    trdRef: { type: 'string' },
                  },
                },
              },
              prdGaps: { type: 'array', items: { type: 'string' } },
              trdOrphans: { type: 'array', items: { type: 'string' } },
              feedback: { type: 'string' },
            },
          },
        },
      },
    }
  )
}

for (let attempt = 1; attempt <= MAX_LOOPS; attempt++) {
  trd = await authorTrd(`attempt ${attempt}/${MAX_LOOPS}`)
  if (!trd) return { ok: false, stage: 'author', reason: 'TRD authoring produced nothing', sadExtract }

  const verification = await verifyTrd()
  const validation = verification && verification.validation
  const traceability = verification && verification.traceability

  trdValidation = validation
  traceabilityMatrix = traceability

  const validationPass = validation && validation.verdict === 'pass'
  const traceabilityPass = traceability && traceability.verdict === 'pass'

  if (validationPass && traceabilityPass) {
    log(`TRD accepted on attempt ${attempt}: validation PASS, traceability PASS`)
    decision = { verdict: 'pass', ruledByDecider: false, rationale: 'Both independent checkers passed.' }
    break
  }

  // Combine the rejecting checkers' feedback for the next maker pass.
  const parts = []
  if (!validationPass) parts.push(`[Structure/quality] ${(validation && validation.feedback) || 'rejected (no feedback)'}`)
  if (!traceabilityPass) parts.push(`[Traceability] ${(traceability && traceability.feedback) || 'rejected (no feedback)'}`)
  feedback = parts.join('\n\n')
  log(`TRD rejected on attempt ${attempt}/${MAX_LOOPS}: ${parts.join(' | ')}`)

  // On deadlock (final pass exhausted while still rejected), the trd-decider rules.
  // The decider only rules — it never authored or analyzed the TRD itself.
  if (attempt === MAX_LOOPS) {
    log('Maker-checker loop exhausted — escalating to trd-decider for a binding ruling')
    const ruling = await agent(
      `The TRD author and the independent checkers reached a deadlock across the bounded retry loop. You ONLY rule — you did not author the TRD and you do not re-analyze it from scratch. Decide whether the TRD ships as-is ("accept"), returns to the author for a final targeted change ("revise"), or is rejected ("reject"), and state the binding rationale. A "revise" is carried out: the author makes the changes you list in \`requiredChanges\` and the TRD is re-checked once, so list every change, each precise enough to apply without re-deciding anything.

TRD:
${JSON.stringify(trd, null, 2)}

Structure/quality verdict: ${(trdValidation && trdValidation.verdict) || 'n/a'}
Structure/quality feedback: ${(trdValidation && trdValidation.feedback) || 'n/a'}

Traceability verdict: ${(traceabilityMatrix && traceabilityMatrix.verdict) || 'n/a'}
Traceability feedback: ${(traceabilityMatrix && traceabilityMatrix.feedback) || 'n/a'}`,
      {
        label: 'decide:trd',
        phase: 'Verify & Traceability',
        effort: 'high',
        agentType: 'agent-teams-workforce:trd-decider',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['verdict', 'rationale'],
          properties: {
            verdict: { type: 'string', enum: ['accept', 'reject', 'revise'] },
            rationale: { type: 'string' },
            requiredChanges: { type: 'array', items: { type: 'string' } },
          },
        },
      }
    )
    decision = ruling
      ? { verdict: ruling.verdict, ruledByDecider: true, rationale: ruling.rationale, requiredChanges: ruling.requiredChanges || [] }
      : { verdict: 'reject', ruledByDecider: true, rationale: 'trd-decider returned no ruling.' }
  }
}

// ── A "revise" ruling is carried out, not reported ────────────────────────────
// The decider is offered "return to the author for a final targeted change". Ending the
// run on that ruling returned ok:false with the change never made, and the gate's re-run
// of this mini did not hand the required changes to the author either, so the same
// finding came back and the gate budget ran out on a TRD the decider had ruled fixable.
// A revise gets exactly one targeted author pass and one independent re-check; a TRD the
// checker still rejects after it ends the run with the ruling and the new findings.
if (decision && decision.verdict === 'revise' && trd) {
  const changes = decision.requiredChanges && decision.requiredChanges.length
    ? decision.requiredChanges.map((c, i) => `${i + 1}. ${c}`).join('\n')
    : '(none listed — apply the rationale)'
  feedback = `BINDING RULING FROM THE TRD DECIDER — make these targeted changes and change nothing else:\n${changes}\n\nRationale: ${decision.rationale || 'n/a'}\n\nLatest checker feedback:\n${feedback}`
  const revised = await authorTrd('final targeted revision per the decider ruling')
  if (revised) {
    trd = revised
    const verification = await verifyTrd()
    trdValidation = verification && verification.validation
    traceabilityMatrix = verification && verification.traceability
    const passed = !!(trdValidation && trdValidation.verdict === 'pass' && traceabilityMatrix && traceabilityMatrix.verdict === 'pass')
    log(`TRD ${passed ? 'accepted' : 'still rejected'} after the decider's targeted revision`)
    decision = passed
      ? { ...decision, verdict: 'accept', revisedPerRuling: true, rationale: `${decision.rationale} Required changes applied; both independent checks passed on re-check.` }
      : { ...decision, revisedPerRuling: true, recheckFeedback: [trdValidation && trdValidation.feedback, traceabilityMatrix && traceabilityMatrix.feedback].filter(Boolean).join('\n\n') }
  } else {
    decision = { ...decision, revisedPerRuling: false }
  }
}

const accepted = decision && (decision.verdict === 'pass' || decision.verdict === 'accept')

return {
  ok: !!accepted,
  trdPath: ART ? authorPath : (trd && trd.trdPath) || trdPath,
  // The filing home ruled for this TRD, when one was ruled. Null means nobody ruled it.
  filingPath,
  sadExtract,
  trd,
  trdValidation,
  traceabilityMatrix,
  decision,
}
