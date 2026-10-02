export const meta = {
  name: 'prd-reconciliation',
  description:
    'Leaf mini — per-repository detailing of an approved architecture delta. One read-only session compares each delta item placed in one repository (one element the delta shows) with the code on that repository\'s main, gives it one status — add, modify, remove, done, or planned-elsewhere — each citing file:line (planned-elsewhere also names the open bead that plans it), gives each ui item its design source — bundle (a single-artifact cds bundle the owner supplied in the packages directory packages it; the newest bundle of a kind and slug is the supplied one), cds (it changes design and no bundle packages it, so it is designed with the CDS design system) or none (it changes no design) — and reports upstream dependency changes. The script fails the run, naming the items, when an item is missing or listed twice, carries a status outside that set, or lacks its citation; a failed detailing blocks that repository\'s Spec. The session saves the detailing as recon-<slug>.json and returns no item content; depscore.py recon-facts checks the saved file on disk and returns only the facts the callers branch on (the ids that make work, the ids that do not, each ui work item\'s design source with the bundle and build spec of a bundle item, whether dependencies are current), and the callers hand the file path to the sessions that read it. A saved result is replayed through the same check instead of dispatching the session; a saved file that cannot be read or is not a usable detailing stops the run, naming the file, and the repository is never detailed again behind it.',
  phases: [{ title: 'Detailing', detail: 'one read-only session compares each delta item placed in the repository with the code on its main, and checks upstream dependencies' }],
}
const dispatchFailures = []
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  return named.length ? dispatchFailures.filter((f) => named.includes(f.phase)) : dispatchFailures.slice()
}
// Runs agent(); returns its result, or null after recording the failure in dispatchFailures.
async function settleAgent(prompt, opts) {
  const o = opts || {}
  const who = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null }
  const name = who.label || who.agentType || 'agent'
  try {
    const out = await agent(prompt, o)
    if (out) return out
    dispatchFailures.push({ ...who, outcome: 'skipped', note: `${name} returned nothing` })
    log(`${name}: returned nothing`)
  } catch (err) {
    const message = String((err && err.message) || err).slice(0, 300)
    dispatchFailures.push({ ...who, outcome: 'threw', message, note: `${name} ended without a structured result: ${message}` })
    log(`${name}: ended without a structured result — ${message}`)
  }
  return null
}

// args: {
//   prd: { id?, title?, path?, repoPath? }, repos: [<the one repository>],
//   items: [{ id, element, views? }] (the delta items placed in this repository),
//   delta: { targetDir, deltaDir },
//   mocksDir?, packagesDir?, shellsDir? (packagesDir holds zero or more single-artifact cds bundles; absent or empty supplies none), dependencies?: string[], uiRepo?: boolean (false skips the cds UI resolution),
//   artifacts: { dir, relDir?, epicId, script, phase, inputs?, slug } (required: the detailing lives only in recon-<slug>.json),
//   depscore: <absolute path of depscore.py> (required: recon-facts reads the saved detailing),
//   replay?: { files: { recon: <absolute path of a saved result> } }
// }
// returns { ok, resumed?, reconPath, itemCount, counts, work, idle, uiWork, bundles, mocksDir,
//           dependenciesCurrent, dependencyFindings, ledger } — facts only; the items are in reconPath
//   or { ok: false, stage, headline, reason, reconPath?, failedItems?, dispatchFailed? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const prdInput = a.prd && typeof a.prd === 'object' ? a.prd : {}
const prdId = prdInput.id || ''
const prdTitle = prdInput.title || ''
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const repoPath = prdInput.repoPath || a.repoPath || ''
const repos = (Array.isArray(a.repos) && a.repos.length ? a.repos : [repoPath]).filter((r) => hasText(r))
const dependencies = Array.isArray(a.dependencies) ? a.dependencies : []
const repoRoot = hasText(repoPath) ? repoPath.replace(/\/+$/, '') : ''
const uiCheck = a.uiRepo !== false
const mocksDir = uiCheck && hasText(a.mocksDir) ? a.mocksDir.trim() : ''
const packagesDir = uiCheck && hasText(a.packagesDir) ? a.packagesDir.trim() : ''
const shellsDir = uiCheck && hasText(a.shellsDir) ? a.shellsDir.trim() : ''
const delta = a.delta && typeof a.delta === 'object' ? a.delta : {}
const placed = (Array.isArray(a.items) ? a.items : []).filter((i) => i && hasText(i.id) && hasText(i.element))

const STATUSES = ['add', 'modify', 'remove', 'done', 'planned-elsewhere']

function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  return ['dir', 'script', 'epicId', 'phase'].every((k) => typeof x[k] === 'string' && x[k]) ? x : null
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const ART = artifactsFrom(a.artifacts)
const artSlug = ART && hasText(ART.slug) ? ART.slug : null
const reconPath = ART && artSlug ? `${ART.dir}/recon-${artSlug}.json` : null
const depscorePath = hasText(a.depscore) && a.depscore.trim().startsWith('/') ? a.depscore.trim() : null
const replayFile = a.replay && a.replay.files && a.replay.files.recon
const replayPath = typeof replayFile === 'string' && replayFile.startsWith('/') ? replayFile : null

const refuse = (why) => ({ ok: false, stage: 'input', deterministicFailure: true, headline: `Detailing refused its input: ${why}`, reason: why, error: why })
if (repos.length !== 1) return refuse(`detailing is scoped to ONE repository; ${repos.length} were supplied`)
if (!hasText(delta.deltaDir)) return refuse('no delta supplied: delta.deltaDir names the views the items come from')
if (!placed.length) return refuse(`no delta item is placed in ${repos[0]}`)
if (!reconPath) return refuse(`no artifact directory and slug were supplied for ${repos[0]}: the detailing exists only as recon-<slug>.json in the Epic's artifact directory, which the sessions downstream read by path`)
if (!depscorePath) return refuse('no absolute depscore.py path was supplied in `depscore`: depscore.py recon-facts reads the saved detailing')

phase('Detailing')

const FACTS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['exitCode', 'output'],
  properties: { exitCode: { type: 'integer' }, output: { type: 'object' } },
}
/** Runs depscore.py recon-facts on a saved detailing; returns { facts } or { error } naming the file. */
async function readFacts(file, label) {
  const command = `python3 ${shq(depscorePath)} recon-facts --file ${shq(file)} --items ${shq(placed.map((i) => i.id).join(','))}`
  const out = await settleAgent(
    `Run exactly this one shell command, once, in the FOREGROUND, and change nothing else:

${command}

It prints one small JSON object on stdout. Return the process exit code as \`exitCode\` and that JSON object, parsed and unaltered, as \`output\`. If stdout is not JSON, return {"error": "<stdout and stderr, verbatim>"} as \`output\`. Do not open the file yourself, do not retry, do not repair, do not run any other command.`,
    { label, phase: 'Detailing', model: 'haiku', effort: 'low', schema: FACTS_SCHEMA }
  )
  if (!out) return { error: `the ${label} runner returned no result`, dispatchFailed: true }
  const o = out.output || {}
  if (out.exitCode !== 0 || hasText(o.error)) return { error: hasText(o.error) ? o.error.trim().slice(0, 600) : `depscore.py recon-facts exited ${out.exitCode}` }
  if (typeof o.ok !== 'boolean') return { error: `depscore.py recon-facts printed no verdict for ${file}` }
  return { facts: o }
}
/** Returns the failure a step stopped on, with the stage and a headline naming the file. */
function stopped(stage, headline, extra) {
  log(headline)
  return { ok: false, stage, headline, reason: headline, error: headline, reconPath: (extra && extra.file) || reconPath, ...(extra || {}) }
}
/** Returns the failure for a detailing that was read but is not usable. */
function unusable(f, file, stage, after) {
  const named = Array.isArray(f.failedItems) ? f.failedItems.map((x) => `${x.id}: ${x.problem}`) : []
  const more = Number(f.problemCount) > named.length ? ` (and ${Number(f.problemCount) - named.length} more)` : ''
  const what = hasText(f.problem) ? f.problem : `${named.join('; ')}${more}`
  return stopped(stage, `The detailing of ${repos[0]} in ${file} is not usable — ${what}${after || ''}`, {
    file,
    failedItems: Array.isArray(f.failedItems) ? f.failedItems : [],
    deterministicFailure: true,
  })
}

/** What the owner does to have a repository whose saved detailing stopped the replay detailed again. */
const REDO = `. To detail ${repos[0]} again, delete ${replayPath || reconPath} and remove the step ${ART.phase} from ${ART.dir}/STEPS.md; the step is not redone behind a saved file`
let facts = null
let resumed = false
if (replayPath) {
  const read = await readFacts(replayPath, 'replay:recon-facts')
  if (read.error) {
    return stopped('detailing-replay', `The saved detailing ${replayPath} of ${repos[0]} could not be read: ${read.error}${REDO}.`, {
      file: replayPath,
      ...(read.dispatchFailed ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('Detailing') } : {}),
    })
  }
  if (read.facts.ok !== true) return unusable(read.facts, replayPath, 'detailing-replay', REDO)
  facts = read.facts
  resumed = true
  log(`Detailing replayed from ${replayPath} (${facts.itemCount} item(s), ${facts.bytes} bytes on disk)`)
}

/** Lists the cds bundles packagesDir supplies with depscore.py cds-bundles; returns { bundles } or { error }. */
async function listBundles() {
  if (!uiCheck || !packagesDir) return { bundles: [] }
  const out = await settleAgent(
    `Run exactly this one shell command, once, in the FOREGROUND, and change nothing else:

python3 ${shq(depscorePath)} cds-bundles --packages-dir ${shq(packagesDir)}

It prints one JSON object on stdout. Return the process exit code as \`exitCode\` and that JSON object, parsed and unaltered, as \`output\`. If stdout is not JSON, return {"error": "<stdout and stderr, verbatim>"} as \`output\`. Do not open any file yourself, do not retry, do not run any other command.`,
    { label: 'detail:cds-bundles', phase: 'Detailing', model: 'haiku', effort: 'low', schema: FACTS_SCHEMA }
  )
  if (!out) return { error: 'the cds-bundles runner returned no result', dispatchFailed: true }
  const o = out.output || {}
  if (out.exitCode !== 0 || hasText(o.error) || !Array.isArray(o.bundles)) return { error: hasText(o.error) ? o.error.trim().slice(0, 600) : `depscore.py cds-bundles exited ${out.exitCode}` }
  return { bundles: o.bundles.filter((b) => b && hasText(b.path) && hasText(b.buildSpec)) }
}
let bundles = []
if (!facts && uiCheck) {
  const listed = await listBundles()
  if (listed.error) {
    return stopped('detailing-bundles', `The cds bundles in ${packagesDir} could not be listed for ${repos[0]}: ${listed.error}.`, {
      ...(listed.dispatchFailed ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('Detailing') } : {}),
    })
  }
  bundles = listed.bundles
  log(`Detailing of ${repos[0]}: ${bundles.length} supplied cds bundle(s)${packagesDir ? ` in ${packagesDir}` : ' (no packages directory)'}`)
}
const bundleLines = bundles
  .map((b) => `  - ${b.kind} \`${b.slug}\`${b.shell && b.shell.name ? ` (in shell ${b.shell.name})` : ''}, created ${b.createdAt}\n      bundle: ${b.path}\n      build spec: ${b.buildSpec}${b.buildSpecExists === false ? ' (MISSING on disk)' : ''}\n      design: ${b.design}\n      styles: ${b.styles}`)
  .join('\n')

const itemLines = placed
  .map((i) => `- ${i.id}: ${i.element}${Array.isArray(i.views) && i.views.length ? `\n    delta views: ${i.views.join('; ')}` : ''}`)
  .join('\n')
const prdLine = `PRD ${prdId}${prdTitle ? `: ${prdTitle}` : ''}`.trim()

const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter(hasText)
const recordCommand = `python3 ${shq(ART.script)} record ${shq(reconPath)} --epic ${shq(ART.epicId)} --phase ${shq(ART.phase)}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
const session = facts ? null : await settleAgent(
  `DETAIL an approved architecture delta for ONE repository: for each delta item placed in it, compare what the delta says the element becomes with what the code on the repository's \`main\` holds today, and give the item one status. You are READ-ONLY: read and search, change nothing anywhere, and write no document other than the one result file named at the end of this brief. Two checks, one pass — both go in that file.

═══ CHECK 1 — the detailing ═══

${prdLine}

THE REPOSITORY — this run is scoped to it, and only it:
  ${repos[0]}
Read its code as committed on \`main\` (\`git -C <repo> grep -n <term> main\`, \`git -C <repo> show main:<path>\`). Do not survey other repositories.

THE APPROVED TARGET is ${delta.targetDir || '(the folder above the delta)'}, and the change alone, its delta, is ${delta.deltaDir}. What the delta views say about an element is what it becomes; read the target views where a delta view needs their context.

THE ITEMS PLACED IN THIS REPOSITORY (each one element the delta shows):
${itemLines}

Give every item above exactly one entry, with one status:
- add      — the delta adds the element and the code on \`main\` does not hold it. \`from\` is "absent"; \`to\` is what the delta adds.
- modify   — the code holds the element and the delta changes it. \`from\` is what the code holds; \`to\` is what the delta makes it.
- remove   — the delta removes the element and the code still holds it. \`from\` is what the code holds; \`to\` is "removed".
- done     — the code on \`main\` already holds the element as the delta shows it. \`from\` and \`to\` are both that state.
- planned-elsewhere — an open bead of another Epic (a Story or Task planned and not built) already plans this change. Name it in \`plannedBy\` (the bead id; read beads with \`bd list\`, \`bd show\`, \`bd search\` only).

Cite evidence for every status in \`evidence\`: a \`file:line\` on \`main\` you read. For \`add\`, cite the file and line where the element attaches (the route table, the stack, the module that will hold it). A \`planned-elsewhere\` item carries its bead id in \`plannedBy\` and, like every status, a \`file:line\`: where the planned change attaches in the code on \`main\`. An item with no citation fails the run.

Also classify the SURFACE each item lives on, in \`surface\`: ui | service | infra | data | unknown.

${uiCheck ? `═══ EVERY UI ITEM TAKES ONE DESIGN SOURCE ═══

For every item whose \`surface\` is \`ui\`, decide its design source from the delta and the code:

- bundle — a cds bundle listed below packages the artifact (the Page, Shell or View) the item
  builds. The owner supplied that mockup, so the bundle is the target state: its
  \`spec/build-spec.md\` together with its composed \`design/<kind>.html\` and its own \`styles/\`.
- cds — the item changes design (layout, components, styles, visual states, or a new screen)
  and no listed bundle packages it. The implementing agent designs it with the CDS design
  system; there is nothing to cite.
- none — the item changes no design: copy or label text, or data wired into an existing
  element without changing how it looks. It touches no design or stylesheet and is built like
  any other code change.

THE SUPPLIED cds BUNDLES — each packages exactly one artifact; the newest of a kind and slug is
listed, older ones are not supplied:
${bundleLines || '  (none: no bundle is supplied, so no item takes bundle)'}

Match an item to a bundle only when the bundle packages the artifact that item builds: read the
bundle's build spec and design, and the approved target/delta views with their scoped design
references (linked source views included). The PRD (${hasText(prdInput.path) ? prdInput.path : 'no PRD path supplied'})
may name a visual reference that helps identify the artifact; it carries no package paths.
Use only the bundles listed above, at the paths listed. Do not package, copy or regenerate a
bundle, and do not cite a directory that is not listed. When no listed bundle packages the
item, it takes cds or none, decided by whether it changes design.

The loose composed artifacts may help you understand the existing design; they are not
supplied mockups and never make an item a bundle item:
${mocksDir ? `  composed pages and views: ${mocksDir}` : '  composed pages and views: (no directory supplied)'}
${shellsDir ? `  composed shells: ${shellsDir}` : '  composed shells: (no directory supplied)'}

Record one entry per \`ui\` item in \`uiAuthority.uiItems\`: \`item\` (the item id),
\`designSource\` (bundle | cds | none), \`reason\` (one sentence: which bundle packages it, or
what design it changes, or why it changes none), and for a bundle item only: \`bundle\` (the
bundle directory exactly as listed), \`buildSpec\` (its build spec exactly as listed) and
\`sections\` (the IDs in that build spec's Sections table — S1, S2, … — that the item builds;
an empty list when it builds the whole artifact or the table carries no IDs). The Spec cites
these and every Task that builds the item carries them in its build contract. List every
artifact path you opened in \`uiAuthority.artifactsConsulted\` and the mocks directory in
\`uiAuthority.mocksDir\`.` : `═══ THIS REPOSITORY HOLDS NO UI ═══

Its items take no design source and \`uiAuthority\` stays empty.`}

═══ SEARCH BUDGET ═══

Work item by item and stop searching for each the moment its status is settled. Cover every
item once before you deepen any of them, and when the budget is spent, stop and return your
structured output with what you have.

═══ CHECK 2 — upstream dependency changes ═══

Upstream dependencies the work relies on:
${dependencies.length ? dependencies.map((d, i) => `${i + 1}. ${d}`).join('\n') : '(none declared in args — discover them from the repository\'s manifests, lockfiles and imports)'}

Determine whether any upstream contract, shared schema, event, library version, or interface the delta assumes has changed in a way that invalidates it. Check the dependencies THIS repository consumes, as its manifests, lockfiles and imports on \`main\` show them. Record under \`dependencyChanges\`:
- current: true if no invalidating upstream change is found, false otherwise.
- changeFindings: each invalidating change (dependency, change, invalidates).
- evidence: how you verified the dependency state (under 60 words).

═══ THE RESULT IS A FILE, NOT YOUR REPLY ═══

1. Write your whole detailing, as ONE JSON object, to ${reconPath} with the Write tool, replacing the file if it exists (Read it first if the Write tool asks you to). Write no other file. Its keys:
   - \`items\`: one object per item above: \`id\`, \`element\`, \`status\` (${STATUSES.join(' | ')}), \`from\`, \`to\`, \`evidence\` (a list of strings, each \`file:line\` you read with what it shows), \`plannedBy\` (the bead id, for planned-elsewhere only), \`surface\` (ui | service | infra | data | unknown).
   - \`evidenceSummary\`: a string.
   - \`uiAuthority\`: \`uiItems\` (each \`{ item, designSource, reason, bundle?, buildSpec?, sections? }\`), \`mocksDir\`, \`artifactsConsulted\`, as described above; empty values when the repository holds no UI.
   - \`dependencyChanges\`: \`current\` (true or false), \`changeFindings\` (each \`{ dependency, change, invalidates }\`), \`evidence\`.
2. Then run exactly this command:
   ${recordCommand}
3. Return ONLY \`saved\` (true when the file is written and the command exited 0), \`itemCount\` (the number of entries in \`items\`) and, when anything failed, \`error\` (what failed, with the command's output). Do NOT return the detailing itself: the workflow checks the file on disk, and every session after you reads it by its path.`,
  {
    label: 'detail:delta-and-dependencies',
    phase: 'Detailing',
    effort: 'medium',
    agentType: 'prd-reality-reconciler',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['saved', 'itemCount'],
      properties: { saved: { type: 'boolean' }, itemCount: { type: 'integer' }, error: { type: 'string' } },
    },
  }
)

if (!facts) {
  if (!session) {
    const deaths = dispatchDeaths('Detailing')
    return stopped('detailing', `The detailing session for ${repos[0]} returned nothing, so the repository was not detailed (${deaths.map((f) => f.note).join('; ') || 'no dispatch was recorded'}).`, {
      dispatchFailed: true,
      dispatchFailures: deaths,
    })
  }
  if (session.saved !== true) {
    return stopped('detailing-save', `The detailing session for ${repos[0]} did not save ${reconPath}: ${hasText(session.error) ? session.error.trim().slice(0, 600) : 'it reported saved=false and gave no reason'}.`)
  }
  const read = await readFacts(reconPath, 'detail:recon-facts')
  if (read.error) {
    return stopped('detailing-read', `The detailing of ${repos[0]} was saved to ${reconPath} but could not be read back: ${read.error}.`, {
      ...(read.dispatchFailed ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('Detailing') } : {}),
    })
  }
  if (read.facts.ok !== true) return unusable(read.facts, reconPath, 'detailing')
  facts = read.facts
  if (Number(session.itemCount) !== Number(facts.itemCount)) log(`Detailing of ${repos[0]}: the session reported ${session.itemCount} item(s) and ${reconPath} holds ${facts.itemCount}; the file governs.`)
}

const ids = (v) => (Array.isArray(v) ? v.filter(hasText).map((x) => x.trim()) : [])
const counts = Object.fromEntries(STATUSES.map((s) => [s, Number((facts.counts || {})[s]) || 0]))
const work = ids(facts.work)
const idle = (Array.isArray(facts.idle) ? facts.idle : [])
  .filter((x) => x && hasText(x.id))
  .map((x) => ({ id: x.id.trim(), status: hasText(x.status) ? x.status.trim() : '', plannedBy: hasText(x.plannedBy) ? x.plannedBy.trim() : null }))
const uiWork = (Array.isArray(facts.uiWork) ? facts.uiWork : [])
  .filter((u) => u && hasText(u.id))
  .map((u) => ({
    id: u.id.trim(),
    designSource: hasText(u.designSource) ? u.designSource.trim() : null,
    bundle: hasText(u.bundle) ? u.bundle.trim() : null,
    buildSpec: hasText(u.buildSpec) ? u.buildSpec.trim() : null,
    sections: ids(u.sections),
  }))
const detailingFile = resumed ? replayPath : reconPath

log(`Detailing of ${repos[0]} (${detailingFile}): ${facts.itemCount} item(s) — ${STATUSES.map((s) => `${counts[s]} ${s}`).join(', ')}.`)

return {
  ok: true,
  ...(resumed ? { resumed: true } : {}),
  reconPath: detailingFile,
  itemCount: Number(facts.itemCount) || 0,
  counts,
  work,
  idle,
  uiWork,
  bundles: [...new Set(uiWork.map((u) => u.bundle).filter(Boolean))],
  mocksDir: hasText(facts.mocksDir) ? facts.mocksDir.trim() : mocksDir || null,
  dependenciesCurrent: typeof facts.dependenciesCurrent === 'boolean' ? facts.dependenciesCurrent : null,
  dependencyFindings: Number(facts.dependencyFindings) || 0,
  ledger: {
    phase: 'prd-reconciliation',
    beadId: null,
    subject: prdId || prdTitle || null,
    chosen: ['prd-reality-reconciler'],
    mode: 'combined',
    uiCheck,
    resumed,
    reconPath: detailingFile,
    itemCount: Number(facts.itemCount) || 0,
    ...counts,
    ok: true,
  },
}
