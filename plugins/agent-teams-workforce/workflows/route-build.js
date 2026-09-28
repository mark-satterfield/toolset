export const meta = {
  name: 'route-build',
  description:
    'Routes a bead to the build composite that works it, deterministically from its type and labels. A Task goes to task-to-deploy (infra-change when it carries an infrastructure type or label) and an infrastructure bead goes to infra-change; a bug, a bead labelled `human`, an Epic, Story or feature, and every other kind are skipped with a reason. Returns { bead, action, composite, reason, ruledBy }: action is "work" or "skip".',
  phases: [{ title: 'Classify', detail: 'maps the bead type and labels to a composite or a skip' }],
}

// args: { bead: { id, type?, labels?, title?, description?, parentType?, parentId?, ancestorTypes? } }
// returns: { bead, action: 'work' | 'skip', composite: 'task-to-deploy' | 'infra-change' | null, reason, ruledBy: 'deterministic' }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}

const norm = (v) => String(v || '').trim().toLowerCase()
const type = norm(bead.type)
const labels = (Array.isArray(bead.labels) ? bead.labels : []).map(norm).filter(Boolean)
const labelSet = new Set(labels)
const hasLabel = (...names) => names.some((n) => labelSet.has(n))
const KNOWN_TYPES = new Set(['task', 'bug', 'infra', 'infrastructure', 'epic', 'story', 'feature', 'chore', 'docs', 'research', 'spike'])
const byLabel = (...names) => !KNOWN_TYPES.has(type) && hasLabel(...names)

const parentType = norm(bead.parentType)
const ancestorTypes = (Array.isArray(bead.ancestorTypes) ? bead.ancestorTypes : []).map(norm)
const labelTail = labels.length ? `, labels=[${labels.join(', ')}]` : ''
const INFRA_LABELS = ['infra', 'infrastructure', 'cdk', 'iac', 'provisioning']

phase('Classify')

const route = (action, composite, reason) => ({ bead, action, composite, reason, ruledBy: 'deterministic' })
const work = (composite, reason) => route('work', composite, reason)
const skip = (reason) => route('skip', null, reason)

const workComposite = () =>
  type === 'infra' || type === 'infrastructure' || hasLabel(...INFRA_LABELS) ? 'infra-change' : 'task-to-deploy'
const hasStoryParent = () => parentType === 'story' || ancestorTypes.includes('story')
const hasEpicAncestor = () => ancestorTypes.includes('epic')

function decide() {
  if (type === 'bug' || byLabel('bug', 'defect', 'regression', 'hotfix')) {
    return skip(
      `bug is a REPORTING MECHANISM and is never implemented directly (type="${type || 'n/a'}"${labelTail}); it is triaged by a person into an Epic, a Task, or a closure → SKIP`,
    )
  }
  if (hasLabel('human')) {
    return skip(
      `held for a person: ${bead.id || 'this bead'} carries the \`human\` label → SKIP until the label is removed (\`bd label remove ${bead.id || '<id>'} human\`)`,
    )
  }
  if (type === 'task' || byLabel('task')) {
    const composite = workComposite()
    if (hasStoryParent() && hasEpicAncestor()) return work(composite, `task under a Story and an Epic → ${composite}`)
    const missing = [!hasStoryParent() && 'parent Story', !hasEpicAncestor() && 'ancestor Epic'].filter(Boolean).join(' and ')
    return work(composite, `task is missing its ${missing}, which is never a dispatch precondition → ${composite}`)
  }
  if (type === 'infra' || type === 'infrastructure' || byLabel(...INFRA_LABELS)) {
    return work('infra-change', `infrastructure change (type="${type || 'n/a'}"${labelTail}) → infra-change`)
  }
  if (type === 'epic' || type === 'story' || byLabel('epic', 'story')) {
    return skip(`${type || 'container'} carries elaboration work, not development work → SKIP here; route it through route-elaboration.js`)
  }
  if (type === 'feature' || byLabel('feature', 'prd', 'requirement')) {
    return skip(`feature is a request, not development work (type="${type || 'n/a'}"${labelTail}) → SKIP here; route it through route-elaboration.js or /agent-teams-workforce:start-prd`)
  }
  return skip(`type="${type || 'n/a'}"${labelTail} has no build composite → SKIP`)
}

const result = decide()
log(`route-build ${bead.id || '(no id)'}: ${result.action.toUpperCase()}${result.composite ? ` via ${result.composite}` : ''} — ${result.reason}`)
return result
