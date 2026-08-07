export const meta = {
  name: 'route-bead',
  description:
    'Leaf mini — Unattended-mode bead router for the agentic SDLC. Enforces the work-item hierarchy: PRD→Epic, Spec→Story, Story→Task, and Bug standing alone. ONLY a Task or a Bug is workable, and a Task only when it has a parent Story and a grandparent Epic. Epics and Stories are containers — they are never worked, only DECOMPOSED into the next level down. Returns { bead, action, composite, reason }: action is "work" (dispatch the composite), "decompose" (dispatch the composite that creates the next level), or "skip" (with the reason). Pure routing logic; it authors nothing and force-fits nothing.',
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
// }
//
// Returns: {
//   bead,
//   action,      // 'work' | 'decompose' | 'skip'
//   composite,   // 'prd-to-spec' | 'spec-to-deploy' | 'bug-fix' | 'infra-change' | null
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
const childCount = Number.isFinite(bead.childCount) ? bead.childCount : null
const labelTail = labels.length ? `, labels=[${labels.join(', ')}]` : ''

phase('Classify')

function route(action, composite, reason, ruledBy) {
  return { bead, action, composite, reason, ruledBy: ruledBy || 'deterministic' }
}
const work = (composite, reason) => route('work', composite, reason)
const decompose = (composite, reason) => route('decompose', composite, reason)
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
//   Epics and Stories are never worked. An Epic with no Stories needs
//   decomposing; a Story with no Tasks needs decomposing. Once decomposed they
//   are inert containers and the work lives in their descendants.
function deterministicRoute() {
  // 1) BUG — workable on its own. No parent required: a defect in existing
  //    behavior is its own contract, manufactured by bug-triage.
  if (type === 'bug' || hasLabel('bug', 'defect', 'regression', 'hotfix')) {
    return work('bug-fix', `bug is workable standing alone (type="${type || 'n/a'}"${labelTail}) → bug-fix`)
  }

  // 2) EPIC — a container, never worked. Decompose it if it has no Stories yet.
  if (type === 'epic' || hasLabel('epic')) {
    if (childCount === 0) {
      return decompose(
        'prd-to-spec',
        `epic has no Stories yet → prd-to-spec, to produce the TRD/Spec and the Story + Task beads beneath it`,
      )
    }
    if (childCount === null) {
      return skip(
        `epic is a container and is never worked directly; childCount was not supplied, so whether it still needs decomposing cannot be determined → SKIP (supply bead.childCount to route epics)`,
      )
    }
    return skip(
      `epic already has ${childCount} child Story/Stories — it is a container, and the work lives in its descendants → SKIP (route its Tasks instead)`,
    )
  }

  // 3) STORY — a container, never worked. Decompose it if it has no Tasks yet.
  if (type === 'story' || hasLabel('story')) {
    if (childCount === 0) {
      return decompose(
        'prd-to-spec',
        `story has no Tasks yet → prd-to-spec, whose task-decomposition phase emits the Task beads beneath it`,
      )
    }
    if (childCount === null) {
      return skip(
        `story is a container and is never worked directly; childCount was not supplied, so whether it still needs decomposing cannot be determined → SKIP (supply bead.childCount to route stories)`,
      )
    }
    return skip(
      `story already has ${childCount} child Task(s) — it is a container, and the work lives in its Tasks → SKIP (route its Tasks instead)`,
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
      `task is missing its ${missing}; a Task without a Story has no Spec and therefore no contract to build against → SKIP (attach it to a Story under an Epic, or decompose the Epic first)`,
    )
  }

  // 5) FEATURE / PRD-shaped work that is not yet an Epic. This is the entry to
  //    the hierarchy: it needs an Epic and everything beneath it.
  if (type === 'feature' || hasLabel('feature', 'prd', 'requirement', 'prd-to-spec')) {
    return decompose(
      'prd-to-spec',
      `feature/PRD-shaped work with no Epic structure yet (type="${type || 'n/a'}"${labelTail}) → prd-to-spec, to create the Epic → Story → Task hierarchy`,
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
    childCount === 0
      ? decompose('prd-to-spec', `classified as an ${kind} with no children: ${agentReason} → prd-to-spec to decompose it`)
      : skip(`classified as an ${kind} — a container, never worked directly: ${agentReason} → SKIP (route its descendants instead)`)
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
  final = decompose('prd-to-spec', `classified as feature-shaped work with no hierarchy yet: ${agentReason} → prd-to-spec`)
}

final.ruledBy = 'ambiguity-detector'
log(`route-bead ${bead.id || '(no id)'}: ${final.action.toUpperCase()}${final.composite ? ` via ${final.composite}` : ''} — ${final.reason}`)
return final
