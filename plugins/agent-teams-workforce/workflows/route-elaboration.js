export const meta = {
  name: 'route-elaboration',
  description:
    'Leaf mini — the ELABORATION router. Routes a PRD/Epic or a Spec/Story to the document pipeline that takes it forward: an Epic to reconciling its PRD, authoring the TRD, and producing the Specs, Stories and Tasks beneath it; a Story to keeping it in sync with its Spec and its Tasks current and covering it. This is real work, but it is NOT development work — a Task belongs to route-build and is skipped here with a pointer to it. A Bug belongs to neither router: it is a reporting mechanism, triaged by a person into an Epic, a Task, or a closure, and is skipped here with a reason naming triage. Child count is never consulted: a container that already has children can still have drifted from the document above it. Elaboration is a product decision, so it requires an explicit human-initiated invocation; an unattended sweep gets a skip and the command to run. Returns { bead, action, composite, reason }: action is "elaborate" or "skip".',
  phases: [
    { title: 'Classify', detail: 'document-side hierarchy rules; never force-fit' },
  ],
}

// args: {
//   bead: {
//     id:           string,          // e.g. "ssbd-123"
//     type?:        string,          // epic | story | feature | ...
//     labels?:      string[],
//     title?:       string,
//     description?: string,
//     parentType?:  string,
//     ancestorTypes?: string[],
//   },
//   allowAmbiguityAgent?: boolean,   // default true
//   humanInitiated?: boolean,        // default FALSE. Set ONLY when a person invoked
//                                    // this run (e.g. /work-bead, /start-prd).
// }
//
// Returns: {
//   bead,
//   action,      // 'elaborate' | 'skip'
//   composite,   // 'prd-to-spec' | null
//   reason,
//   ruledBy?,    // 'deterministic' | 'ambiguity-detector'
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const allowAmbiguityAgent = a.allowAmbiguityAgent !== false

// Existence is NOT readiness. An Epic or a Story sitting there is not a request to
// elaborate it — running the pipeline is, and that is a product decision a person
// makes. So elaboration is gated on the caller stating a human initiated this run.
// An unattended sweep leaves the flag unset and receives a skip with the command.
// The gate lives here rather than in each caller: a rule every future caller has
// to remember is not a rule.
const humanInitiated = a.humanInitiated === true

const norm = (v) => String(v || '').trim().toLowerCase()
const type = norm(bead.type)
const labels = (Array.isArray(bead.labels) ? bead.labels : []).map(norm).filter(Boolean)
const labelSet = new Set(labels)
const hasLabel = (...names) => names.some((n) => labelSet.has(n))

const parentType = norm(bead.parentType)
const ancestorTypes = (Array.isArray(bead.ancestorTypes) ? bead.ancestorTypes : []).map(norm)
const labelTail = labels.length ? `, labels=[${labels.join(', ')}]` : ''

phase('Classify')

function route(action, composite, reason, ruledBy) {
  return { bead, action, composite, reason, ruledBy: ruledBy || 'deterministic' }
}
const elaborate = (composite, reason) => route('elaborate', composite, reason)
const skip = (reason) => route('skip', null, reason)

const id = bead.id || '<bead-id>'

// ── What this router is for ───────────────────────────────────────────────────
//
//   Files:  PRD ──> TRD ──> Spec
//   Beads:  Epic ──1:many──> Story ──> Task          Bug stands alone
//
//   A PRD and its Epic are ONE item in two representations, created together, as
//   are a Spec and its Story. The FILE side is what decomposes; the beads are what
//   that chain deposits. Nothing "decomposes" an Epic or a Story.
//
//   Both ARE workable — their work is elaboration:
//     Epic  — reconcile the PRD's contents into the Epic, author the TRD, produce
//             the Spec(s), and deposit the Stories and Tasks beneath it.
//     Story — keep the Story and its Spec in sync, and keep its Tasks current and
//             covering it.
//
//   CHILD COUNT IS NEVER CONSULTED. An Epic with four Stories can still need this:
//   the PRD may have moved on and the beads beneath it drifted. Treating "has
//   children" as "done" is what let drift accumulate silently.
function deterministicRoute() {
  // 1) EPIC — the bead face of a PRD.
  if (type === 'epic' || hasLabel('epic')) {
    if (!humanInitiated) {
      return skip(
        `epic elaboration — reconciling its PRD, authoring the TRD, producing the Specs and Stories — is a decision about whether to build this, and now. That is a human's call, not a sweep's. → SKIP. To work it: /agent-teams-workforce:work-bead ${id}, or /agent-teams-workforce:start-prd`,
      )
    }
    return elaborate(
      'prd-to-spec',
      `working this epic was human-initiated → prd-to-spec, which reconciles the PRD with the Epic, authors the TRD, and produces the Spec(s) and the Story and Task beads beneath it. An Epic that ALREADY has Stories may still need this — the PRD may have moved on.`,
    )
  }

  // 2) STORY — the bead face of a Spec.
  if (type === 'story' || hasLabel('story')) {
    if (!humanInitiated) {
      return skip(
        `story elaboration — keeping the Story and its Spec in sync and its Tasks current and covering it — starts build work. That is a human's call, not a sweep's. → SKIP. To work it: /agent-teams-workforce:work-bead ${id}`,
      )
    }
    return elaborate(
      'prd-to-spec',
      `working this story was human-initiated → prd-to-spec, whose task-decomposition phase reconciles the Story with its Spec and emits the Task beads parented to it. A Story that ALREADY has Tasks may still need this — the Spec may have moved on.`,
    )
  }

  // 3) FEATURE — a request, not work. Promoting it to a PRD and an Epic is a
  //    product decision: whether this is worth building at all, and now. An
  //    automated loop that promotes every feature bead it finds has decided the
  //    roadmap, which is not a call any agent here has the standing to make.
  if (type === 'feature' || hasLabel('feature', 'prd', 'requirement', 'prd-to-spec')) {
    if (!humanInitiated) {
      return skip(
        `feature is a REQUEST, not work (type="${type || 'n/a'}"${labelTail}). It becomes implementable by being promoted to a PRD and an Epic, which is a human decision about whether to build it. → SKIP. When you want it built: /agent-teams-workforce:start-prd`,
      )
    }
    return elaborate(
      'prd-to-spec',
      `promoting this feature was human-initiated → prd-to-spec, which authors the PRD and mints the Epic, then carries it to TRD, Spec(s), Stories and Tasks`,
    )
  }

  // 4) BUG — neither elaboration work nor development work. A bug is a REPORTING
  //    MECHANISM: it is TRIAGED by a person into an Epic, a Task, or a closure.
  //    Pointing it at route-build would be wrong — that router skips it too.
  if (type === 'bug' || hasLabel('bug', 'defect', 'regression', 'hotfix')) {
    return skip(
      `bug is a REPORTING MECHANISM and is never implemented directly (type="${type || 'n/a'}"${labelTail}) — it is TRIAGED into an Epic, a Task, or a closure, and that is a person's judgment call. Not elaboration work, and not development work either → SKIP (route-build skips it for the same reason; no triage composite exists to dispatch)`,
    )
  }

  // 5) DEVELOPMENT-SIDE kinds — real work, but not elaboration work.
  if (type === 'task' || type === 'infra' || type === 'infrastructure' ||
      hasLabel('task', 'infra', 'infrastructure')) {
    return skip(
      `${type || 'this bead'} carries DEVELOPMENT work — code, tests, infrastructure, deployment to dev. → SKIP here. Route it through route-build.js instead.`,
    )
  }

  // 6) Explicitly out-of-pipeline kinds.
  if (type === 'chore' || type === 'docs' || type === 'research' || type === 'spike') {
    return skip(`type="${type}" is out of the automated pipeline (no composite handles it) → SKIP (reported, not force-fit)`)
  }

  // 7) Unknown — defer to the ambiguity agent if allowed.
  return null
}

const det = deterministicRoute()
if (det) {
  log(`route-elaboration ${bead.id || '(no id)'}: ${det.action.toUpperCase()}${det.composite ? ` via ${det.composite}` : ''} — ${det.reason}`)
  return det
}

// ── Ambiguity escalation ──────────────────────────────────────────────────────
// The deterministic table could not decide. Policy is never to force-fit, so the
// default is SKIP. The READ-ONLY ambiguity-detector may classify the bead's TYPE
// from its title/description — it decides what the bead IS, not what to run. The
// script then re-applies the same rules to that answer, so a classified bead can
// never bypass the human-initiated gate.
if (!allowAmbiguityAgent) {
  const reason = `type="${type || 'n/a'}"${labelTail} matched no routing rule and ambiguity classification is disabled → SKIP (reported, not force-fit)`
  log(`route-elaboration ${bead.id || '(no id)'}: SKIP — ${reason}`)
  return skip(reason)
}

const classification = await agent(
  `You are a READ-ONLY classifier for the agentic SDLC elaboration router. A bead could not be classified by its type/labels alone. Read its title and description and decide WHAT KIND of work item it is. You are NOT choosing a pipeline and NOT running anything — you only name the kind.

Bead ${bead.id || '(no id)'}
Declared type: ${type || '(none)'}
Labels: ${labels.length ? labels.join(', ') : '(none)'}
Parent type: ${parentType || '(none)'}
Ancestor types: ${ancestorTypes.length ? ancestorTypes.join(', ') : '(none)'}
Title: ${bead.title || '(none)'}
Description:
${bead.description || '(none)'}

The work-item kinds:
- epic    — a container for a whole PRD's worth of work, spanning repos. Holds Stories. Its work is elaboration.
- story   — a container scoped to ONE repo, corresponding to a Spec. Holds Tasks. Its work is elaboration.
- feature — requirement-shaped work that has no Epic/Story/Task structure yet.
- task    — one agent's unit of DEVELOPMENT work within ONE repo.
- bug     — a REPORT of a defect or regression in EXISTING behavior. Neither elaboration nor development work: a bug is triaged by a person into an Epic, a Task, or a closure.
- infra   — a provisioning/IaC change (CDK, AWS resources, deploy plumbing).
- other   — chore, docs-only, research spike, or too underspecified to classify.

Rules:
- Name the kind the bead actually IS. Do not pick a kind because it would let work proceed.
- If the bead is too underspecified to place, answer "other".
- "confident" false forces a SKIP.

Deliver:
- kind: one of "epic" | "story" | "feature" | "task" | "bug" | "infra" | "other".
- confident: true only if the bead clearly is that kind.
- reason: the concrete signal in the title/description that drove the decision.`,
  {
    label: 'classify:ambiguous-bead',
    phase: 'Classify',
    agentType: 'agent-teams-workforce:ambiguity-detector',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['kind', 'confident', 'reason'],
      properties: {
        kind: { type: 'string', enum: ['epic', 'story', 'feature', 'task', 'bug', 'infra', 'other'] },
        confident: { type: 'boolean' },
        reason: { type: 'string' },
      },
    },
  }
)

const kind = classification && classification.kind
const confident = !!(classification && classification.confident)
const agentReason = (classification && classification.reason) || 'no reason returned'

if (!kind || kind === 'other' || !confident) {
  const reason = `ambiguity-detector could not confidently classify this bead (kind="${kind || 'none'}", confident=${confident}): ${agentReason} → SKIP (reported, not force-fit)`
  log(`route-elaboration ${bead.id || '(no id)'}: SKIP — ${reason}`)
  return skip(reason)
}

// Re-apply the SAME rules to the classified kind. The classifier decides what the
// bead IS; the human-initiated gate stays the script's and is not negotiable by an
// agent's answer.
let final
if (kind === 'epic' || kind === 'story' || kind === 'feature') {
  const what = kind === 'feature' ? 'feature-shaped work with no hierarchy yet' : `an ${kind}`
  final = humanInitiated
    ? elaborate('prd-to-spec', `classified as ${what} and the run is human-initiated: ${agentReason} → prd-to-spec`)
    : skip(`classified as ${what}: ${agentReason}. Elaborating its document is a decision to build, which is a human's call, not a sweep's → SKIP (invoke /agent-teams-workforce:work-bead ${id} to proceed)`)
} else if (kind === 'bug') {
  final = skip(
    `classified as a bug: ${agentReason}. A bug is a REPORTING MECHANISM and is never implemented directly — it is TRIAGED into an Epic, a Task, or a closure by a person. Neither elaboration nor development work → SKIP (no triage composite exists to dispatch)`,
  )
} else {
  final = skip(
    `classified as ${kind === 'infra' ? 'an infrastructure change' : `a ${kind}`}: ${agentReason}. That is DEVELOPMENT work, not elaboration → SKIP here. Route it through route-build.js.`,
  )
}

final.ruledBy = 'ambiguity-detector'
log(`route-elaboration ${bead.id || '(no id)'}: ${final.action.toUpperCase()}${final.composite ? ` via ${final.composite}` : ''} — ${final.reason}`)
return final
