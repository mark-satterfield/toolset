export const meta = {
  name: 'route-elaboration',
  description:
    'Routes an Epic, a Story or a feature to prd-to-spec; every other kind is skipped with a reason naming where it belongs. Returns { bead, action, composite, reason, ruledBy }: action is "elaborate" or "skip".',
  phases: [{ title: 'Classify', detail: 'maps the bead type and labels to prd-to-spec or a skip' }],
}

// args: { bead: { id, type?, labels?, title?, description?, parentType?, parentId?, ancestorTypes? } }
// returns: { bead, action: 'elaborate' | 'skip', composite: 'prd-to-spec' | null, reason, ruledBy: 'deterministic' }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}

const norm = (v) => String(v || '').trim().toLowerCase()
const type = norm(bead.type)
const labels = (Array.isArray(bead.labels) ? bead.labels : []).map(norm).filter(Boolean)
const labelSet = new Set(labels)
const hasLabel = (...names) => names.some((n) => labelSet.has(n))
const KNOWN_TYPES = new Set(['task', 'bug', 'infra', 'infrastructure', 'epic', 'story', 'feature', 'chore', 'docs', 'research', 'spike'])
const byLabel = (...names) => !KNOWN_TYPES.has(type) && hasLabel(...names)
const labelTail = labels.length ? `, labels=[${labels.join(', ')}]` : ''

phase('Classify')

const route = (action, composite, reason) => ({ bead, action, composite, reason, ruledBy: 'deterministic' })
const elaborate = (reason) => route('elaborate', 'prd-to-spec', reason)
const skip = (reason) => route('skip', null, reason)

function decide() {
  if (type === 'epic' || byLabel('epic')) {
    return elaborate('epic → prd-to-spec, which authors the TRD and produces the Specs, Stories and Tasks beneath it')
  }
  if (type === 'story' || byLabel('story')) {
    return elaborate(
      `story → prd-to-spec, run over the Story's parent Epic${bead.parentId ? ` (${bead.parentId})` : ''}; prd-to-spec takes an Epic, never a Story`,
    )
  }
  if (type === 'feature' || byLabel('feature', 'prd', 'requirement', 'prd-to-spec')) {
    return elaborate('feature → prd-to-spec, once the invoking command has resolved or minted its PRD and Epic')
  }
  if (type === 'bug' || byLabel('bug', 'defect', 'regression', 'hotfix')) {
    return skip(
      `bug is a REPORTING MECHANISM and is never implemented directly (type="${type || 'n/a'}"${labelTail}); it is triaged by a person into an Epic, a Task, or a closure → SKIP`,
    )
  }
  if (type === 'task' || type === 'infra' || type === 'infrastructure' || byLabel('task', 'infra', 'infrastructure')) {
    return skip(`${type || 'this bead'} carries development work → SKIP here; route it through route-build.js`)
  }
  return skip(`type="${type || 'n/a'}"${labelTail} has no elaboration composite → SKIP`)
}

const result = decide()
log(`route-elaboration ${bead.id || '(no id)'}: ${result.action.toUpperCase()}${result.composite ? ` via ${result.composite}` : ''} — ${result.reason}`)
return result
