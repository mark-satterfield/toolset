export const meta = {
  name: 'route-build',
  description:
    'Leaf mini — the BUILD router. Routes a Task or a Bug to the composite that takes it through code, test, and deployment to dev. Development work is the only thing routed here: a Task (workable with or without a parent Story — a Story is a roll-up parent for reporting, never a dispatch precondition) or a Bug (workable standing alone). An Epic, Story, or feature belongs to route-elaboration and is skipped here with a pointer to it. Returns { bead, action, composite, reason }: action is "work" (dispatch the composite) or "skip" (with the reason). Pure routing logic; it authors nothing and force-fits nothing.',
  phases: [
    { title: 'Classify', detail: 'workability rules for development work; never force-fit' },
  ],
}

// args: {
//   bead: {
//     id:           string,          // e.g. "ssbd-123"
//     type?:        string,          // task | bug | infra | ...
//     labels?:      string[],
//     title?:       string,
//     description?: string,
//
//     // ── Hierarchy inputs. Without these a Task can never be judged workable. ──
//     parentType?:  string,          // type of the immediate parent ('story' | ...)
//     parentId?:    string,
//     ancestorTypes?: string[],      // every ancestor type, nearest-first: ['story','epic']
//   },
//   allowAmbiguityAgent?: boolean,   // default true
// }
//
// Returns: {
//   bead,
//   action,      // 'work' | 'skip'
//   composite,   // 'task-to-deploy' | 'bug-fix' | 'infra-change' | null
//   reason,
//   ruledBy?,    // 'deterministic' | 'ambiguity-detector'
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const allowAmbiguityAgent = a.allowAmbiguityAgent !== false

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
const work = (composite, reason) => route('work', composite, reason)
const skip = (reason) => route('skip', null, reason)

// Infra beats the default because an infra task changes provisioning, not
// application code.
function workComposite() {
  if (type === 'infra' || type === 'infrastructure' || hasLabel('infra', 'infrastructure', 'cdk', 'iac', 'provisioning')) {
    return 'infra-change'
  }
  return 'task-to-deploy'
}

const hasStoryParent = () => parentType === 'story' || ancestorTypes.includes('story')
const hasEpicAncestor = () => ancestorTypes.includes('epic')

// ── What this router is for ───────────────────────────────────────────────────
//
//   Files:  PRD ──> TRD ──> Spec
//   Beads:  Epic ──1:many──> Story ──> Task          Bug stands alone
//
//   DEVELOPMENT work — writing code, tests, infrastructure, and deploying to dev —
//   belongs to a Task or a Bug and to nothing else. A Task is scoped to one agent's
//   work within one repo. Its Story and Epic are ROLL-UP PARENTS FOR REPORTING: they
//   say where the work reports, and they NEVER gate whether it is worked. A Task with
//   no Story is routed exactly like one with a Story; the missing parent is a
//   reporting repair the caller makes on the side (and names when it cannot), not a
//   reason to refuse. This router used to refuse such a Task on the theory that "no
//   Story means no Spec means no contract" — but the composite it routes to builds
//   its contract from the Task's own statement of work and rules the repository at
//   run time, so the gate guarded nothing and held 50 of 51 live Tasks out of the run.
//
//   An Epic or a Story IS workable, but its work is elaboration, not development.
//   That belongs to route-elaboration.
function deterministicRoute() {
  // 1) BUG — workable standing alone. No parent required: a defect in existing
  //    behavior is its own contract, manufactured by bug-triage.
  if (type === 'bug' || hasLabel('bug', 'defect', 'regression', 'hotfix')) {
    return work('bug-fix', `bug is workable standing alone (type="${type || 'n/a'}"${labelTail}) → bug-fix`)
  }

  // 2) TASK — the unit of development work. Its parents never gate it.
  if (type === 'task' || hasLabel('task')) {
    const composite = workComposite()
    if (hasStoryParent() && hasEpicAncestor()) {
      return work(
        composite,
        `task sits under a Story and an Epic (parent="${parentType || ancestorTypes[0] || 'story'}", ancestors=[${ancestorTypes.join(', ') || 'story, epic'}]) → ${composite}`,
      )
    }
    const missing = [!hasStoryParent() && 'parent Story', !hasEpicAncestor() && 'ancestor Epic']
      .filter(Boolean)
      .join(' and ')
    return work(
      composite,
      `task is missing its ${missing} — a roll-up parent for reporting, never a dispatch precondition; the composite builds against the Task's own statement of work and rules the repository at run time → ${composite} (the missing parent is a reporting repair, made on the side)`,
    )
  }

  // 3) INFRA declared as its own type, outside a Story hierarchy.
  if (type === 'infra' || type === 'infrastructure' || hasLabel('infra', 'infrastructure', 'cdk', 'iac', 'provisioning')) {
    return work('infra-change', `infrastructure change (type="${type || 'n/a'}"${labelTail}) → infra-change`)
  }

  // 4) ELABORATION-SIDE kinds — real work, but not development work.
  if (type === 'epic' || type === 'story' || hasLabel('epic', 'story')) {
    return skip(
      `${type || 'container'} carries no DEVELOPMENT work — its work is elaboration (an Epic: reconcile its PRD, author the TRD, produce the Specs and Stories; a Story: keep it in sync with its Spec and its Tasks covering it). → SKIP here. Route it through route-elaboration.js instead.`,
    )
  }

  if (type === 'feature' || hasLabel('feature', 'prd', 'requirement')) {
    return skip(
      `feature is a REQUEST, not development work (type="${type || 'n/a'}"${labelTail}). It becomes implementable by being promoted to a PRD and an Epic, which is a human decision. → SKIP here. Route it through route-elaboration.js, or /agent-teams-workforce:start-prd.`,
    )
  }

  // 5) Explicitly out-of-pipeline kinds.
  if (type === 'chore' || type === 'docs' || type === 'research' || type === 'spike') {
    return skip(`type="${type}" is out of the automated pipeline (no composite handles it) → SKIP (reported, not force-fit)`)
  }

  // 6) Unknown — defer to the ambiguity agent if allowed.
  return null
}

const det = deterministicRoute()
if (det) {
  log(`route-build ${bead.id || '(no id)'}: ${det.action.toUpperCase()}${det.composite ? ` via ${det.composite}` : ''} — ${det.reason}`)
  return det
}

// ── Ambiguity escalation ──────────────────────────────────────────────────────
// The deterministic table could not decide. Policy is never to force-fit, so the
// default is SKIP. The READ-ONLY ambiguity-detector may classify the bead's TYPE
// from its title/description — it decides what the bead IS, not what to run. The
// script then re-applies the same workability rules to that answer, so a
// classified bead can never bypass them.
if (!allowAmbiguityAgent) {
  const reason = `type="${type || 'n/a'}"${labelTail} matched no routing rule and ambiguity classification is disabled → SKIP (reported, not force-fit)`
  log(`route-build ${bead.id || '(no id)'}: SKIP — ${reason}`)
  return skip(reason)
}

const classification = await agent(
  `You are a READ-ONLY classifier for the agentic SDLC build router. A bead could not be classified by its type/labels alone. Read its title and description and decide WHAT KIND of work item it is. You are NOT choosing a pipeline and NOT running anything — you only name the kind.

Bead ${bead.id || '(no id)'}
Declared type: ${type || '(none)'}
Labels: ${labels.length ? labels.join(', ') : '(none)'}
Parent type: ${parentType || '(none)'}
Ancestor types: ${ancestorTypes.length ? ancestorTypes.join(', ') : '(none)'}
Title: ${bead.title || '(none)'}
Description:
${bead.description || '(none)'}

The work-item kinds:
- task    — one agent's unit of work within ONE repo. Development work, with or without a Story above it.
- bug     — a defect or regression in EXISTING behavior. Development work, standing alone.
- infra   — a provisioning/IaC change (CDK, AWS resources, deploy plumbing).
- epic    — a container for a whole PRD's worth of work, spanning repos. Not development work.
- story   — a container scoped to ONE repo, corresponding to a Spec. Not development work.
- feature — requirement-shaped work with no Epic/Story/Task structure yet.
- other   — chore, docs-only, research spike, or too underspecified to classify.

Rules:
- Name the kind the bead actually IS. Do not pick a kind because it would let work proceed.
- If the bead is too underspecified to place, answer "other".
- "confident" false forces a SKIP.

Deliver:
- kind: one of "task" | "bug" | "infra" | "epic" | "story" | "feature" | "other".
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
        kind: { type: 'string', enum: ['task', 'bug', 'infra', 'epic', 'story', 'feature', 'other'] },
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
  log(`route-build ${bead.id || '(no id)'}: SKIP — ${reason}`)
  return skip(reason)
}

// Re-apply the SAME workability rules to the classified kind. The classifier
// decides what the bead IS; the workability rule stays the script's and is not
// negotiable by an agent's answer — and a classified 'task' is worked whether or
// not it has a Story, exactly as the deterministic rule works one.
let final
if (kind === 'bug') {
  final = work('bug-fix', `classified as a bug: ${agentReason} → bug-fix`)
} else if (kind === 'infra') {
  final = work('infra-change', `classified as an infrastructure change: ${agentReason} → infra-change`)
} else if (kind === 'task') {
  final =
    hasStoryParent() && hasEpicAncestor()
      ? work(workComposite(), `classified as a task under a Story and an Epic: ${agentReason} → ${workComposite()}`)
      : work(workComposite(), `classified as a task with no parent Story and/or ancestor Epic — a roll-up parent for reporting, never a dispatch precondition: ${agentReason} → ${workComposite()}`)
} else {
  final = skip(
    `classified as ${kind === 'feature' ? 'feature-shaped work' : `an ${kind}`}: ${agentReason}. That is elaboration work, not development work → SKIP here. Route it through route-elaboration.js.`,
  )
}

final.ruledBy = 'ambiguity-detector'
log(`route-build ${bead.id || '(no id)'}: ${final.action.toUpperCase()}${final.composite ? ` via ${final.composite}` : ''} — ${final.reason}`)
return final
