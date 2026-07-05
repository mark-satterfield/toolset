export const meta = {
  name: 'route-bead',
  description:
    'Leaf mini — Unattended-mode bead router for the agentic SDLC. Given one ready bead, decides deterministically (by bead.type and labels) which composite must handle it (prd-to-spec, spec-to-deploy, bug-fix, infra-change) or returns null to SKIP it. Pure routing logic — it spawns no agents unless a genuine classification ambiguity (the deterministic table cannot decide) needs the read-only ambiguity-detector. Never authors content, never force-fits a bead to a composite. Returns { bead, composite, reason }.',
  phases: [
    { title: 'Classify', detail: 'deterministic type/label -> composite mapping; null = skip' },
  ],
}

// args: {
//   bead: {
//     id:          string,           // e.g. "ssbd-123"
//     type?:       string,           // bead type — feature | bug | infra | task | chore | epic | docs | ...
//     labels?:     string[],         // free-form labels; influence routing (see ROUTING.md)
//     title?:      string,
//     description?: string,
//   },
//   allowAmbiguityAgent?: boolean,    // default true — set false to force a deterministic-only pass
//                                     // (genuinely ambiguous beads then SKIP instead of being classified)
// }
//
// Returns: {
//   bead,                            // the bead echoed back (the caller threads it onward)
//   composite,                       // 'prd-to-spec' | 'spec-to-deploy' | 'bug-fix' | 'infra-change' | null
//   reason,                          // human-readable why-this-route / why-skipped
//   ruledBy?,                        // 'deterministic' | 'ambiguity-detector' — provenance of the decision
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const allowAmbiguityAgent = a.allowAmbiguityAgent !== false

// The four composites this router can dispatch to. Anything not on this list is a skip.
const COMPOSITES = ['prd-to-spec', 'spec-to-deploy', 'bug-fix', 'infra-change']

// ── Normalize the bead's classification inputs ─────────────────────────────────
const type = String(bead.type || '').trim().toLowerCase()
const labels = (Array.isArray(bead.labels) ? bead.labels : [])
  .map((l) => String(l || '').trim().toLowerCase())
  .filter(Boolean)
const labelSet = new Set(labels)
const hasLabel = (...names) => names.some((n) => labelSet.has(n))

phase('Classify')

// Standard return shape.
function route(composite, reason, ruledBy) {
  return { bead, composite, reason, ruledBy: ruledBy || 'deterministic' }
}

// ── Deterministic routing table (see ROUTING.md for the authoritative policy) ───
// Order matters: the FIRST matching rule wins. Labels can override the base type
// so an explicitly-labelled bead is never mis-typed.
//
//   bug    | label "bug"/"defect"/"regression"          -> bug-fix
//   infra  | label "infra"/"infrastructure"/"cdk"/"iac"  -> infra-change
//   feature| label "feature"/"prd"/"requirement"         -> prd-to-spec
//          | label "spec"/"spec-ready"/"implementation"   -> spec-to-deploy
//   else                                                 -> SKIP (null) + reason
function deterministicRoute() {
  // 1) Bugs — symptom-first; bug-triage manufactures the contract, shared tail fixes it.
  if (type === 'bug' || hasLabel('bug', 'defect', 'regression', 'hotfix')) {
    return route('bug-fix', `type/label indicates a defect (type="${type || 'n/a'}"${labels.length ? `, labels=[${labels.join(', ')}]` : ''}) → bug-fix`)
  }

  // 2) Infrastructure — provisioning intent; infra-intent front-end + trimmed tail.
  if (type === 'infra' || type === 'infrastructure' || hasLabel('infra', 'infrastructure', 'cdk', 'iac', 'provisioning')) {
    return route('infra-change', `type/label indicates an infrastructure change (type="${type || 'n/a'}"${labels.length ? `, labels=[${labels.join(', ')}]` : ''}) → infra-change`)
  }

  // 3) Spec-ready work — a contract already exists; go straight to the build-and-ship tail.
  //    Checked BEFORE the feature rule so a spec-ready feature skips WF1 re-derivation.
  if (hasLabel('spec', 'spec-ready', 'implementation', 'implement', 'spec-to-deploy')) {
    return route('spec-to-deploy', `label indicates an implementation-ready spec (labels=[${labels.join(', ')}]) → spec-to-deploy`)
  }

  // 4) Features / requirements — no contract yet; run the PRD→spec front-end first.
  if (type === 'feature' || type === 'epic' || type === 'story' || hasLabel('feature', 'prd', 'requirement', 'prd-to-spec')) {
    return route('prd-to-spec', `type/label indicates a feature needing a contract (type="${type || 'n/a'}"${labels.length ? `, labels=[${labels.join(', ')}]` : ''}) → prd-to-spec`)
  }

  // 5) Explicitly out-of-pipeline kinds — skipped and reported, never force-fit.
  if (type === 'chore' || type === 'docs' || type === 'task' || type === 'research' || type === 'spike') {
    return route(null, `type="${type}" is out of the automated pipeline (no composite handles it) → SKIP (reported, not force-fit)`)
  }

  // 6) Nothing matched — unknown/unlabelled. Defer to the ambiguity agent if allowed.
  return null
}

const det = deterministicRoute()
if (det) {
  log(`route-bead ${bead.id || '(no id)'}: ${det.composite || 'SKIP'} — ${det.reason}`)
  return det
}

// ── Ambiguity escalation ────────────────────────────────────────────────────────
// The deterministic table could not decide. By policy we never force-fit, so the
// default is to SKIP. Only when a classification agent is permitted do we ask the
// READ-ONLY ambiguity-detector to classify from the title/description — it never
// authors content and never executes the chosen composite; the script applies the
// verdict (and still skips if the agent is not confident or names a non-composite).
if (!allowAmbiguityAgent) {
  const reason = `type="${type || 'n/a'}"${labels.length ? `, labels=[${labels.join(', ')}]` : ''} matched no routing rule and ambiguity classification is disabled → SKIP (reported, not force-fit)`
  log(`route-bead ${bead.id || '(no id)'}: SKIP — ${reason}`)
  return route(null, reason)
}

const classification = await agent(
  `You are a READ-ONLY classifier for the agentic SDLC bead router. A bead could not be routed by its type/labels alone. Read its title and description and decide which ONE pipeline composite — if any — should handle it. Author NOTHING; do not run the composite; only classify.

Bead ${bead.id || '(no id)'}
Declared type: ${type || '(none)'}
Labels: ${labels.length ? labels.join(', ') : '(none)'}
Title: ${bead.title || '(none)'}
Description:
${bead.description || '(none)'}

The four composites and what each is for:
- prd-to-spec  — a NEW feature/requirement that has NO implementation-ready contract yet; needs PRD validation → architecture → spec → tasks.
- spec-to-deploy — work whose spec/contract ALREADY exists and is implementation-ready; goes straight to build-and-ship.
- bug-fix          — a defect/regression in EXISTING behavior; a symptom to reproduce, root-cause, and fix.
- infra-change     — an infrastructure/provisioning change (CDK/IaC, AWS resources, deploy plumbing).

Rules:
- Pick exactly one composite ONLY if the bead clearly belongs to it.
- If the bead is genuinely out of scope for all four (a chore, doc-only edit, research spike, or too underspecified to classify), choose to SKIP — do NOT force-fit it into a composite.
- "confidence" reflects how sure you are; below clear confidence, SKIP.

Deliver:
- composite: one of "prd-to-spec" | "spec-to-deploy" | "bug-fix" | "infra-change" | "skip".
- confident: true only if the bead clearly belongs to the chosen composite (false forces a SKIP).
- reason: the concrete signal in the title/description that drove the decision.`,
  {
    label: 'classify:ambiguous-bead',
    phase: 'Classify',
    agentType: 'agent-teams-workforce:ambiguity-detector',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['composite', 'confident', 'reason'],
      properties: {
        composite: {
          type: 'string',
          enum: ['prd-to-spec', 'spec-to-deploy', 'bug-fix', 'infra-change', 'skip'],
        },
        confident: { type: 'boolean' },
        reason: { type: 'string' },
      },
    },
  }
)

// Apply the verdict defensively: only dispatch on a confident pick of a real
// composite; anything else (skip, low confidence, or an unexpected value) is a
// reported SKIP — the router never force-fits an unclassifiable bead.
const picked = classification && classification.composite
const confident = !!(classification && classification.confident)
const agentReason = (classification && classification.reason) || 'no reason returned'

if (picked && picked !== 'skip' && confident && COMPOSITES.includes(picked)) {
  const reason = `ambiguity-detector classified → ${picked}: ${agentReason}`
  log(`route-bead ${bead.id || '(no id)'}: ${picked} — ${reason}`)
  return route(picked, reason, 'ambiguity-detector')
}

const skipReason = `ambiguity-detector could not confidently route this bead (verdict="${picked || 'none'}", confident=${confident}): ${agentReason} → SKIP (reported, not force-fit)`
log(`route-bead ${bead.id || '(no id)'}: SKIP — ${skipReason}`)
return route(null, skipReason, 'ambiguity-detector')
