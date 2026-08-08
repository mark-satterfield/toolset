export const meta = {
  name: 'route-bead',
  description:
    'Leaf mini — bead router for the agentic SDLC. Enforces the work-item hierarchy: a PRD and its Epic are ONE item in two representations, as are a Spec and its Story; Epic → Story → Task; a Bug stands alone. ONLY a Task or a Bug is workable, and a Task only when it has a parent Story and a grandparent Epic. Nothing decomposes an Epic or a Story: the FILE side is what decomposes (PRD → TRD → Spec), and the beads are what that chain deposits, so an Epic or Story with no children needs its document ELABORATED, not itself broken up. Returns { bead, action, composite, reason }: action is "work" (dispatch the composite), "elaborate" (run the next document stage, which deposits the beads beneath this one), or "skip" (with the reason). Elaboration requires an explicit human-initiated invocation — existence is not readiness — so an unattended sweep gets "skip" and a reason. Pure routing logic; it authors nothing and force-fits nothing.',
  phases: [
    { title: 'Classify', detail: 'hierarchy + workability rules; never force-fit' },
  ],
}

// args: {
//   bead: {
//     id:           string,          // e.g. "ssbd-123"
//     type?:        string,          // epic | story | task | bug | infra | chore | docs | ...
//     labels?:      string[],
//     title?:       string,
//     description?: string,
//
//     // ── Hierarchy inputs. Supply these or a Task can never be judged workable. ──
//     parentType?:  string,          // type of the immediate parent ('epic' | 'story' | ...)
//     parentId?:    string,
//     ancestorTypes?: string[],      // every ancestor type, nearest-first: ['story','epic']
//     childCount?:  number,          // how many children this bead already has
//   },
//   allowAmbiguityAgent?: boolean,   // default true
//   humanInitiated?: boolean,        // default FALSE. Set ONLY when a person invoked this
//                                    // run (e.g. /work-bead). Elaborating an Epic's or a
//                                    // Story's document starts build work, and that is a
//                                    // product decision; an unattended sweep leaves this
//                                    // unset and gets a skip with the command to run.
// }
//
// Returns: {
//   bead,
//   action,      // 'work' | 'elaborate' | 'skip'
//   composite,   // 'prd-to-spec' | 'spec-to-deploy' | 'bug-fix' | 'infra-change' | null
//   reason,
//   ruledBy?,    // 'deterministic' | 'ambiguity-detector'
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const allowAmbiguityAgent = a.allowAmbiguityAgent !== false

// Existence is NOT readiness. A PRD, an Epic, or a Story sitting there with no
// children is not a request to build it — running a pipeline is, and that is a
// product decision a person makes. So elaboration is gated on the caller stating
// that a human initiated this run. An unattended sweep leaves the flag unset and
// receives a skip, exactly as a `feature` bead already does. Putting the gate here
// rather than in each caller is deliberate: a rule every future caller has to
// remember is not a rule.
const humanInitiated = a.humanInitiated === true

const norm = (v) => String(v || '').trim().toLowerCase()
const type = norm(bead.type)
const labels = (Array.isArray(bead.labels) ? bead.labels : []).map(norm).filter(Boolean)
const labelSet = new Set(labels)
const hasLabel = (...names) => names.some((n) => labelSet.has(n))

const parentType = norm(bead.parentType)
const ancestorTypes = (Array.isArray(bead.ancestorTypes) ? bead.ancestorTypes : []).map(norm)
const childCount = Number.isFinite(bead.childCount) ? bead.childCount : null
const labelTail = labels.length ? `, labels=[${labels.join(', ')}]` : ''

phase('Classify')

function route(action, composite, reason, ruledBy) {
  return { bead, action, composite, reason, ruledBy: ruledBy || 'deterministic' }
}
const work = (composite, reason) => route('work', composite, reason)
const elaborate = (composite, reason) => route('elaborate', composite, reason)
const skip = (reason) => route('skip', null, reason)

// Which build-and-ship composite a workable item belongs to. Infra beats the
// default because an infra task changes provisioning, not application code.
function workComposite() {
  if (type === 'infra' || type === 'infrastructure' || hasLabel('infra', 'infrastructure', 'cdk', 'iac', 'provisioning')) {
    return 'infra-change'
  }
  return 'spec-to-deploy'
}

// ── The hierarchy rules ────────────────────────────────────────────────────────
//
//   Files:  PRD ──> TRD ──> Spec
//   Beads:  Epic ──1:many──> Story ──> Task          Bug stands alone
//
//   A Story is scoped to a single repo. A Task is scoped to one agent's work
//   within one repo. ONLY a Task or a Bug is workable; a Task only when it has
//   a parent Story and a grandparent Epic.
//
//   A PRD and its Epic are ONE item in two representations, created together, as
//   are a Spec and its Story. The FILE side is what decomposes; the beads are what
//   that chain deposits. So nothing "decomposes an Epic" or "decomposes a Story" —
//   an Epic with no Stories needs its PRD elaborated into a TRD and Spec(s), and a
//   Story with no Tasks needs its SPEC decomposed. Once that has happened they are
//   inert containers and the work lives in their descendants.
function deterministicRoute() {
  // 1) BUG — workable on its own. No parent required: a defect in existing
  //    behavior is its own contract, manufactured by bug-triage.
  if (type === 'bug' || hasLabel('bug', 'defect', 'regression', 'hotfix')) {
    return work('bug-fix', `bug is workable standing alone (type="${type || 'n/a'}"${labelTail}) → bug-fix`)
  }

  // 2) EPIC — the bead face of a PRD, never worked. An Epic with no Stories does
  //    not get "decomposed": its PRD gets elaborated into a TRD and Specs, and the
  //    Stories are what that chain deposits underneath it.
  if (type === 'epic' || hasLabel('epic')) {
    if (childCount === 0) {
      if (!humanInitiated) {
        return skip(
          `epic has no Stories yet, but elaborating its PRD is a decision about whether to build this, and now — a human's call, not a sweep's. → SKIP. To build it: /agent-teams-workforce:work-bead ${bead.id || '<epic-id>'}, or /agent-teams-workforce:start-prd`,
        )
      }
      return elaborate(
        'prd-to-spec',
        `epic has no Stories yet and the run is human-initiated → prd-to-spec, which elaborates its PRD into the TRD and Spec(s) and deposits the Story + Task beads beneath it`,
      )
    }
    if (childCount === null) {
      return skip(
        `epic is the bead face of a PRD and is never worked directly; childCount was not supplied, so whether its PRD still needs elaborating cannot be determined → SKIP (supply bead.childCount to route epics)`,
      )
    }
    return skip(
      `epic already has ${childCount} child Story/Stories — its PRD has been elaborated and the work lives in its descendants → SKIP (route its Tasks instead)`,
    )
  }

  // 3) STORY — the bead face of a Spec, never worked. A Story with no Tasks does
  //    not get "decomposed" either: its SPEC is what decomposes into tasks, and
  //    they are parented to the Story.
  if (type === 'story' || hasLabel('story')) {
    if (childCount === 0) {
      if (!humanInitiated) {
        return skip(
          `story has no Tasks yet, but decomposing its Spec starts build work — a human's call, not a sweep's. → SKIP. To build it: /agent-teams-workforce:work-bead ${bead.id || '<story-id>'}`,
        )
      }
      return elaborate(
        'prd-to-spec',
        `story has no Tasks yet and the run is human-initiated → prd-to-spec, whose task-decomposition phase decomposes this Story's Spec into Task beads parented to it`,
      )
    }
    if (childCount === null) {
      return skip(
        `story is the bead face of a Spec and is never worked directly; childCount was not supplied, so whether its Spec still needs decomposing cannot be determined → SKIP (supply bead.childCount to route stories)`,
      )
    }
    return skip(
      `story already has ${childCount} child Task(s) — its Spec has been decomposed and the work lives in its Tasks → SKIP (route its Tasks instead)`,
    )
  }

  // 4) TASK — the workable unit, but ONLY inside a complete hierarchy.
  //    A parentless Task has no Story, therefore no Spec, therefore no contract
  //    to build against. Dispatching it would make the implementer invent one.
  if (type === 'task' || hasLabel('task')) {
    const hasStoryParent = parentType === 'story' || ancestorTypes.includes('story')
    const hasEpicAncestor = ancestorTypes.includes('epic')

    if (hasStoryParent && hasEpicAncestor) {
      const composite = workComposite()
      return work(
        composite,
        `task sits under a Story and an Epic (parent="${parentType || ancestorTypes[0] || 'story'}", ancestors=[${ancestorTypes.join(', ') || 'story, epic'}]) → ${composite}`,
      )
    }

    const missing = [!hasStoryParent && 'parent Story', !hasEpicAncestor && 'ancestor Epic']
      .filter(Boolean)
      .join(' and ')
    return skip(
      `task is missing its ${missing}; a Task without a Story has no Spec and therefore no contract to build against → SKIP (attach it to a Story under an Epic, or elaborate the Epic's PRD first)`,
    )
  }

  // 5) FEATURE / PRD-shaped work that is not yet an Epic. This is the entry to
  //    the hierarchy: it needs an Epic and everything beneath it.
  // 5) FEATURE — a request, not work, and promoting it is the HUMAN's call.
  //
  // A feature bead becomes implementable by being promoted to a PRD and an Epic,
  // and that decision is a product decision: whether this is worth building at
  // all, and now. An automated loop that promotes every feature bead it finds has
  // decided the roadmap, which is not a call any agent here has the standing to
  // make. So this is a reported SKIP, not a decompose.
  if (type === 'feature' || hasLabel('feature', 'prd', 'requirement', 'prd-to-spec')) {
    return skip(
      `feature is a REQUEST, not work (type="${type || 'n/a'}"${labelTail}). A feature becomes ` +
        `implementable by being promoted to a PRD and an Epic, which is a human decision about ` +
        `whether to build it. → SKIP. When you want it built: /agent-teams-workforce:start-prd, ` +
        `or dispatch prd-to-spec with { request } to author the PRD first.`,
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
  log(`route-bead ${bead.id || '(no id)'}: ${det.action.toUpperCase()}${det.composite ? ` via ${det.composite}` : ''} — ${det.reason}`)
  return det
}

// ── Ambiguity escalation ───────────────────────────────────────────────────────
// The deterministic table could not decide. Policy is never to force-fit, so the
// default is SKIP. The READ-ONLY ambiguity-detector may classify the bead's TYPE
// from its title/description — it decides what the bead IS, not what to run. The
// script then re-applies the same hierarchy rules to that answer, so a classified
// bead can never bypass the workability rule.
if (!allowAmbiguityAgent) {
  const reason = `type="${type || 'n/a'}"${labelTail} matched no routing rule and ambiguity classification is disabled → SKIP (reported, not force-fit)`
  log(`route-bead ${bead.id || '(no id)'}: SKIP — ${reason}`)
  return skip(reason)
}

const classification = await agent(
  `You are a READ-ONLY classifier for the agentic SDLC bead router. A bead could not be classified by its type/labels alone. Read its title and description and decide WHAT KIND of work item it is. You are NOT choosing a pipeline and NOT running anything — you only name the kind.

Bead ${bead.id || '(no id)'}
Declared type: ${type || '(none)'}
Labels: ${labels.length ? labels.join(', ') : '(none)'}
Parent type: ${parentType || '(none)'}
Ancestor types: ${ancestorTypes.length ? ancestorTypes.join(', ') : '(none)'}
Child count: ${childCount === null ? '(unknown)' : childCount}
Title: ${bead.title || '(none)'}
Description:
${bead.description || '(none)'}

The work-item kinds:
- epic    — a container for a whole PRD's worth of work. Spans repos. Holds Stories. Never worked directly.
- story   — a container scoped to ONE repo, corresponding to a Spec. Holds Tasks. Never worked directly.
- task    — one agent's unit of work within ONE repo. Workable, but only under a Story and an Epic.
- bug     — a defect or regression in EXISTING behavior. Workable standing alone.
- infra   — a provisioning/IaC change (CDK, AWS resources, deploy plumbing).
- feature — requirement-shaped work that has no Epic/Story/Task structure yet.
- other   — chore, docs-only, research spike, or too underspecified to classify.

Rules:
- Name the kind the bead actually IS. Do not pick a kind because it would let work proceed.
- If the bead is too underspecified to place, answer "other".
- "confident" false forces a SKIP.

Deliver:
- kind: one of "epic" | "story" | "task" | "bug" | "infra" | "feature" | "other".
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
        kind: { type: 'string', enum: ['epic', 'story', 'task', 'bug', 'infra', 'feature', 'other'] },
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
  log(`route-bead ${bead.id || '(no id)'}: SKIP — ${reason}`)
  return skip(reason)
}

// Re-apply the SAME hierarchy rules to the classified kind. The classifier
// decides what the bead IS; the workability rule stays the script's and is not
// negotiable by an agent's answer — a classified 'task' with no Story still skips.
let final
if (kind === 'bug') {
  final = work('bug-fix', `classified as a bug: ${agentReason} → bug-fix`)
} else if (kind === 'epic' || kind === 'story') {
  final =
    childCount !== 0
      ? skip(`classified as an ${kind} — the bead face of a document, never worked directly: ${agentReason} → SKIP (route its descendants instead)`)
      : humanInitiated
        ? elaborate('prd-to-spec', `classified as an ${kind} with no children and the run is human-initiated: ${agentReason} → prd-to-spec, which elaborates its document and deposits the beads beneath it`)
        : skip(`classified as an ${kind} with no children: ${agentReason}. Elaborating its document is a decision to build, which is a human's call, not a sweep's → SKIP (invoke /agent-teams-workforce:work-bead ${bead.id || '<id>'} to proceed)`)
} else if (kind === 'task') {
  const hasStoryParent = parentType === 'story' || ancestorTypes.includes('story')
  const hasEpicAncestor = ancestorTypes.includes('epic')
  final =
    hasStoryParent && hasEpicAncestor
      ? work(workComposite(), `classified as a task under a Story and an Epic: ${agentReason} → ${workComposite()}`)
      : skip(`classified as a task but it lacks a parent Story and/or an ancestor Epic: ${agentReason} → SKIP (attach it to a Story under an Epic first)`)
} else if (kind === 'infra') {
  final = work('infra-change', `classified as an infrastructure change: ${agentReason} → infra-change`)
} else {
  final = humanInitiated
    ? elaborate('prd-to-spec', `classified as feature-shaped work with no hierarchy yet and the run is human-initiated: ${agentReason} → prd-to-spec`)
    : skip(`classified as feature-shaped work with no hierarchy yet: ${agentReason}. Promoting it to a PRD and an Epic is a human's call → SKIP (/agent-teams-workforce:start-prd)`)
}

final.ruledBy = 'ambiguity-detector'
log(`route-bead ${bead.id || '(no id)'}: ${final.action.toUpperCase()}${final.composite ? ` via ${final.composite}` : ''} — ${final.reason}`)
return final
