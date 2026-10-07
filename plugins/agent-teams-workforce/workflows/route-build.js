export const meta = {
  name: 'route-build',
  description:
    'Routes a bead to the build composite that works it, deterministically from its type and labels. A Task and an infrastructure bead go to task-to-deploy, which adds its Infra Intent phase for a bead with an infrastructure type or label; a bug, a bead labelled `human`, an Epic, Story or feature, and every other kind are skipped with a reason. Returns { bead, action, composite, reason, ruledBy }: action is "work" or "skip".',
  phases: [{ title: 'Classify', detail: 'maps the bead type and labels to a composite or a skip' }],
}

// args: { bead: { id, type?, labels?, title?, description?, parentType?, parentId?, ancestorTypes? },
//         infraVocabulary: { types, labels } (the plugin's scripts/infra-vocabulary.json) }
// returns: { bead, action: 'work' | 'skip', composite: 'task-to-deploy' | null, reason, ruledBy: 'deterministic' }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}

const norm = (v) => String(v || '').trim().toLowerCase()
const type = norm(bead.type)
const labels = (Array.isArray(bead.labels) ? bead.labels : []).map(norm).filter(Boolean)
const labelSet = new Set(labels)
const hasLabel = (...names) => names.some((n) => labelSet.has(n))
const vocabulary = a.infraVocabulary || {}
const INFRA_TYPES = (Array.isArray(vocabulary.types) ? vocabulary.types : []).map(norm).filter(Boolean)
const INFRA_LABELS = (Array.isArray(vocabulary.labels) ? vocabulary.labels : []).map(norm).filter(Boolean)
const KNOWN_TYPES = new Set(['task', 'bug', ...INFRA_TYPES, 'epic', 'story', 'feature', 'chore', 'docs', 'research', 'spike'])
const byLabel = (...names) => !KNOWN_TYPES.has(type) && hasLabel(...names)

const parentType = norm(bead.parentType)
const ancestorTypes = (Array.isArray(bead.ancestorTypes) ? bead.ancestorTypes : []).map(norm)
const labelTail = labels.length ? `, labels=[${labels.join(', ')}]` : ''

phase('Classify')

const route = (action, composite, reason) => ({ bead, action, composite, reason, ruledBy: 'deterministic' })
const work = (composite, reason) => route('work', composite, reason)
const skip = (reason) => route('skip', null, reason)

const isInfra = () => INFRA_TYPES.includes(type) || hasLabel(...INFRA_LABELS)
const workComposite = () => 'task-to-deploy'
const infraTail = () => (isInfra() ? ' (an infrastructure change: its Infra Intent phase runs)' : '')
const hasStoryParent = () => parentType === 'story' || ancestorTypes.includes('story')
const hasEpicAncestor = () => ancestorTypes.includes('epic')

function decide() {
  if (!INFRA_TYPES.length || !INFRA_LABELS.length) {
    return skip('no infraVocabulary supplied: pass the types and labels from scripts/infra-vocabulary.json as args.infraVocabulary → SKIP')
  }
  if (type === 'bug' || byLabel('bug', 'defect', 'regression', 'hotfix')) {
    return skip(
      `bug is a REPORTING MECHANISM and is never implemented directly (type="${type || 'n/a'}"${labelTail}); it is triaged by a person into an Epic, a Task, or a closure → SKIP`,
    )
  }
  if (hasLabel('human')) {
    return skip(
      `held for a person: ${bead.id || 'this bead'} carries the \`human\` label → SKIP until the label is removed (\`atw-bd label remove ${bead.id || '<id>'} human\`)`,
    )
  }
  if (type === 'task' || byLabel('task')) {
    const composite = workComposite()
    if (hasStoryParent() && hasEpicAncestor()) return work(composite, `task under a Story and an Epic → ${composite}${infraTail()}`)
    const missing = [!hasStoryParent() && 'parent Story', !hasEpicAncestor() && 'ancestor Epic'].filter(Boolean).join(' and ')
    return work(composite, `task is missing its ${missing}, which is never a dispatch precondition → ${composite}${infraTail()}`)
  }
  if (INFRA_TYPES.includes(type) || byLabel(...INFRA_LABELS)) {
    return work('task-to-deploy', `infrastructure change (type="${type || 'n/a'}"${labelTail}) → task-to-deploy, with its Infra Intent phase`)
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
