export const meta = {
  name: 'repo-scoping',
  description:
    'Leaf mini — rules the repository span of a PRD from its approved architecture delta. One polyrepo-steward session places each delta item (one element the delta shows, as depscore.py arch-delta lists it) in the repository whose code changes for it, or records that the element has no code in this project, and creates each new repository the approved target names, from the name, template and reason the target gives. The span is the distinct repositories the placements name. The run fails when an item is placed twice or not at all, or when no placement names a repository.',
  phases: [
    { title: 'Place and provision', detail: 'the polyrepo-steward places each delta item in a repository and creates the new repositories the approved target names' },
  ],
}

const dispatchFailures = []

async function run(prompt, opts) {
  let message = 'returned nothing'
  try {
    const out = await agent(prompt, opts)
    if (out) return out
  } catch (err) {
    message = String((err && err.message) || err).slice(0, 300)
  }
  dispatchFailures.push({ label: opts.label, agentType: opts.agentType || null, phase: opts.phase, message })
  log(`${opts.label}: no structured result — ${message}`)
  return null
}

// args: { prd: { id?, title?, path? }, delta: { subject, targetDir, deltaDir, items: [{ id, element, views }] },
//   epic?: { key?, title? }, artifacts?: { dir, relDir?, epicId, script, phase, inputs?, beadId? } }
// returns: { ok, reason?, repos, placements, noCode, createdRepos, creationFailures, spanRationale, surveySummary, ledger }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const hasText = (v) => typeof v === 'string' && v.trim().length > 0

const ART = a.artifacts && typeof a.artifacts === 'object' && typeof a.artifacts.dir === 'string' && a.artifacts.dir ? a.artifacts : null
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
function persistBrief(name, what) {
  if (!ART) return ''
  const file = `${ART.dir}/${name}`
  const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter((p) => typeof p === 'string' && p.trim())
  const record = `python3 ${ART.script} record ${file} --epic ${ART.epicId} --phase ${ART.phase}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN. No other session will write it for you.
1. Write ${what} to ${file} with the Write tool, replacing the whole file if it exists (the Write tool refuses to overwrite a file this session has not read: Read it first, then Write). Write no other file for this.
2. Then run exactly this command:\n   ${record}\n   It hashes the file as it is on disk and prints the recorded metadata as JSON.
If a step fails, say so in your result and still return your result. Never improvise another way to write, move or record the file.`
}

const prdInput = a.prd && typeof a.prd === 'object' ? a.prd : {}
const prdId = prdInput.id || ''
const prdTitle = prdInput.title || ''
const epic = a.epic || {}
const delta = a.delta && typeof a.delta === 'object' ? a.delta : {}
const items = (Array.isArray(delta.items) ? delta.items : []).filter((i) => i && hasText(i.id) && hasText(i.element))


const fail = (reason, extra) => ({
  ok: false,
  reason,
  repos: [],
  placements: [],
  noCode: [],
  createdRepos: [],
  creationFailures: [],
  ...(extra || {}),
})
const died = (phaseName) => {
  const deaths = dispatchFailures.filter((f) => f.phase === phaseName)
  return deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}
}

if (!hasText(delta.deltaDir) || !hasText(delta.targetDir)) {
  return { ...fail('no approved target and delta were supplied: the span is the repositories the delta changes'), stage: 'input', deterministicFailure: true }
}
if (!items.length) {
  return { ...fail(`the delta at ${delta.deltaDir} lists no item: depscore.py arch-delta found no element in its views' \`shows\``), stage: 'input', deterministicFailure: true }
}

phase('Place and provision')

const itemLines = items
  .map((i) => `- ${i.id}: ${i.element}${Array.isArray(i.views) && i.views.length ? `\n    shown in: ${i.views.join('; ')}` : ''}`)
  .join('\n')

const placed = await run(
  `Place each item of an approved architecture delta in the repository whose code changes for it, and CREATE each new repository the approved target names. You own the project's repositories and your records of them; repository facts come from your records and the live repositories, as the polyrepo-repo skill describes.

THE APPROVED TARGET for ${prdTitle || prdId || 'this PRD'} is ${delta.targetDir}; the change alone, its delta, is ${delta.deltaDir}. Read the delta views, and the target views where a delta view leaves an element's home unstated. Each item below is one element the delta shows:
${itemLines}

DO THIS, IN ORDER:

1. Take the inventory LIVE, now, with your polyrepo tool: \`inventory --json\` (the polyrepo-repo skill names the tool and its path).
2. For each item, name the repository whose code changes for it: the repository that owns the element, as your records and the code on its \`main\` show. An element that has no code in this project (an external system, or a managed service whose configuration lives in the code of another item's repository) goes in \`noCode\` with the reason; an element whose configuration lives in a repository's code is placed in that repository.
3. Where the approved target names a NEW repository for an element, look first in the live inventory for a repository that already serves it, including one an earlier run of this same PRD created, and place the item there rather than creating a second. Otherwise create it with the polyrepo tool's \`create\` command, locally and on GitHub, as the polyrepo-repo skill describes, with the name, the template and the reason the target gives; where the target names no template, the template whose kind matches the element as the target describes it. If a creation fails, fix what the error names and try it once more; if it still fails, report it in creationFailures with the error text. Create no repository the target does not name.

Return:

- placements — one entry per repository that holds work, including each repository you created. Each: repoPath (the repository's absolute local path, exactly as your polyrepo tool reports it), repoName, itemIds (the ids of the items placed there), frontend (true when the repository serves a user interface, per your records), rationale, and created (true when you created it in this session).
- noCode — one entry per item with no code in this project: itemId and reason.
- createdRepos — one entry per repository you created in this session: name, repoPath, template, purpose, itemIds. Empty when you created none.
- creationFailures — one entry per repository the target names that you could not create: proposedName, itemIds, error. Empty when every creation succeeded.
- surveySummary — how many repositories the inventory holds and how you took it.
- spanRationale — why these are the repositories the delta changes, in a few sentences.

Every item appears exactly once: in one placement or in noCode. Change nothing in any repository beyond creating the ones the target names.${persistBrief('repo-scoping.json', 'your complete result (placements, noCode, createdRepos, creationFailures, surveySummary, spanRationale — exactly as you return them) as ONE JSON object')}`,
  {
    label: 'scope:place-delta',
    phase: 'Place and provision',
    effort: 'high',
    agentType: 'agent-teams-workforce:polyrepo-steward',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['placements', 'noCode', 'createdRepos', 'creationFailures', 'spanRationale'],
      properties: {
        placements: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['repoPath', 'repoName', 'itemIds', 'frontend', 'rationale'],
            properties: {
              repoPath: { type: 'string' },
              repoName: { type: 'string' },
              itemIds: { type: 'array', items: { type: 'string' } },
              frontend: { type: 'boolean' },
              rationale: { type: 'string' },
              created: { type: 'boolean' },
            },
          },
        },
        noCode: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['itemId', 'reason'],
            properties: { itemId: { type: 'string' }, reason: { type: 'string' } },
          },
        },
        createdRepos: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['name', 'repoPath', 'purpose'],
            properties: {
              name: { type: 'string' },
              repoPath: { type: 'string' },
              template: { type: 'string' },
              purpose: { type: 'string' },
              itemIds: { type: 'array', items: { type: 'string' } },
            },
          },
        },
        creationFailures: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['proposedName', 'error'],
            properties: {
              proposedName: { type: 'string' },
              itemIds: { type: 'array', items: { type: 'string' } },
              error: { type: 'string' },
            },
          },
        },
        surveySummary: { type: 'string' },
        spanRationale: { type: 'string' },
      },
    },
  }
)

if (!placed) {
  return fail('the polyrepo-steward returned no placement, so the repositories the delta changes were not established.', died('Place and provision'))
}

const known = new Set(items.map((i) => i.id))
const seen = new Map()
const note = (id, where) => seen.set(id, [...(seen.get(id) || []), where])
const placements = []
const repos = []
for (const p of placed.placements) {
  if (!p || !hasText(p.repoPath)) continue
  const repoPath = p.repoPath.trim()
  const itemIds = (Array.isArray(p.itemIds) ? p.itemIds : []).filter((x) => hasText(x)).map((x) => x.trim())
  if (!itemIds.length) continue
  if (!repos.includes(repoPath)) repos.push(repoPath)
  for (const id of itemIds) note(id, repoPath)
  placements.push({
    repoPath,
    repoName: hasText(p.repoName) ? p.repoName : repoPath,
    itemIds,
    frontend: p.frontend === true,
    rationale: p.rationale || '',
    created: p.created === true,
  })
}
const noCode = (Array.isArray(placed.noCode) ? placed.noCode : []).filter((n) => n && hasText(n.itemId)).map((n) => ({ itemId: n.itemId.trim(), reason: n.reason || '' }))
for (const n of noCode) note(n.itemId, 'noCode')
const createdRepos = placed.createdRepos.filter((c) => c && hasText(c.name))
const creationFailures = placed.creationFailures.filter((f) => f && hasText(f.proposedName))

const unknown = [...seen.keys()].filter((id) => !known.has(id))
const twice = [...seen.entries()].filter(([id, where]) => known.has(id) && where.length > 1).map(([id, where]) => `${id} (${where.join(', ')})`)
const unplaced = items.filter((i) => !seen.has(i.id)).map((i) => `${i.id} ${i.element}`)
const faults = [
  unplaced.length ? `not placed: ${unplaced.join('; ')}` : '',
  twice.length ? `placed more than once: ${twice.join('; ')}` : '',
  unknown.length ? `not items of the delta: ${unknown.join(', ')}` : '',
  creationFailures.length ? `not created: ${creationFailures.map((f) => `${f.proposedName} (${f.error})`).join('; ')}` : '',
].filter(Boolean)
if (faults.length) {
  return fail(`the placement of the delta items is incomplete — ${faults.join('; ')}`, { placements, noCode, createdRepos, creationFailures })
}
if (!repos.length) {
  return fail('the polyrepo-steward placed the delta in no repository: every item was recorded as having no code in this project.', { noCode, createdRepos, creationFailures })
}

log(
  `Span placed: ${repos.length} repositor(ies) — ${repos.join(', ')}` +
    `${createdRepos.length ? `; ${createdRepos.length} created (${createdRepos.map((c) => c.name).join(', ')})` : ''}` +
    `${noCode.length ? `; ${noCode.length} item(s) with no code here` : ''}.`
)

return {
  ok: true,
  repos,
  placements,
  noCode,
  createdRepos,
  creationFailures,
  spanRationale: placed.spanRationale || null,
  surveySummary: placed.surveySummary || null,
  ledger: {
    phase: 'repo-scoping',
    beadId: (epic && epic.key) || null,
    subject: prdId || prdTitle || null,
    chosen: ['polyrepo-steward'],
    mode: 'fixed',
    repoCount: repos.length,
    itemCount: items.length,
    createdRepoCount: createdRepos.length,
    ok: true,
  },
}
