export const meta = {
  name: 'prd-reconciliation',
  description:
    'Leaf mini — per-repository detailing of an approved architecture delta. One read-only session compares each delta item placed in one repository (one element the delta shows) with the code on that repository\'s main, gives it one status — add, modify, remove, done, or planned-elsewhere — each citing file:line (planned-elsewhere also names the open bead that plans it), resolves UI items against the cds design artifacts, and reports upstream dependency changes. The script fails the run, naming the items, when an item is missing or listed twice, carries a status outside that set, or lacks its citation; a failed detailing blocks that repository\'s Spec. The session saves the detailing as recon-<slug>.json and returns no item content; depscore.py recon-facts checks the saved file on disk and returns only the facts the callers branch on (the ids that make work, the ids that do not, each ui work item\'s build spec, the cds bundle, whether dependencies are current), and the callers hand the file path to the sessions that read it. A saved result is replayed through the same check instead of dispatching the session; a saved file that cannot be read or is not a usable detailing stops the run, naming the file, and the repository is never detailed again behind it.',
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
//   mocksDir?, packagesDir?, shellsDir? (packagesDir is a selected bundle or search root; caller supplies design system paths), dependencies?: string[], uiRepo?: boolean (false skips the cds UI resolution),
//   artifacts: { dir, relDir?, epicId, script, phase, inputs?, slug } (required: the detailing lives only in recon-<slug>.json),
//   depscore: <absolute path of depscore.py> (required: recon-facts reads the saved detailing),
//   replay?: { files: { recon: <absolute path of a saved result> } }
// }
// returns { ok, resumed?, reconPath, itemCount, counts, work, idle, uiWork, bundlePath, mocksDir,
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
if (uiCheck && !mocksDir && !packagesDir) return refuse(`${repos[0]} serves a user interface and no design system directory was supplied: pass packagesDir or mocksDir, which the caller resolves from CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR and CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR`)
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

${uiCheck ? `═══ UI ITEMS ARE RESOLVED AGAINST THE cds DESIGN SYSTEM ═══

For every item whose \`surface\` is \`ui\`, the design system's output is the target state, highest first:

  1. THE cds HAND-OFF BUNDLE — the packaged artifact: its \`spec/build-spec.md\` together
     with the composed HTML under \`design/\`.
  2. THE LOOSE COMPOSED ARTIFACT in the directories below — used when the artifact is not
     in the bundle.
  3. The delta views.

Design package input:
${packagesDir ? `  ${packagesDir}` : '  (none supplied: use the loose composed artifacts below)'}
If this directory itself holds \`styles/tokens.css\`, it is the caller's explicitly selected
package for this run: inspect it directly, not its children or a newer sibling. Otherwise it
is a search root, not a selection or approval of every package beneath it.

Read the relevant approved target/delta views and follow their scoped design hand-off
references (including linked source views) FIRST. Preserve the selected mock/package and
its scope; do not replace that design with a newer unrelated package. This is the existing
architecture-to-TRD-to-detailing hand-off, not a requirement for technical fields in the PRD.
Optional PRD visual references: ${hasText(prdInput.path) ? prdInput.path : '(no PRD path supplied)'}
The PRD defines business requirements; it need not carry package paths or implementation
details. A visual reference may help identify the artifact. If an explicit caller-selected
package conflicts with the scoped architecture hand-off or an explicit design reference,
report the conflict rather than silently substitute either. Resolve absolute references directly. For relative references, use the
base named by the reference (for example its named repository or the package search root);
ordinary relative file links resolve beside the source document. Do not silently rebase a
vault link onto the implementation repository. If a selected path is missing, its base is
ambiguous, or its intended artifact cannot be identified, report that in \`evidenceSummary\`
and the item's evidence, leave its build-spec unresolved, and do not fabricate a citation
or fall back to another design. Packaging details belong in this technical hand-off, not in
new mandatory PRD fields.

Inspect candidate README/specs to match the item before selecting by recency; the newest
unrelated package is not its design. Accept BOTH existing layouts:

  Single-design package from \`cds:package-change\`:
    <change-slug>-<timestamp>/
      README.md                     package index
      spec/build-spec.md            selected artifact's build contract — READ THIS
      design/page.html | shell.html | view.html
      styles/                       generated stylesheet set and manifest
      assets/                       referenced assets, when present
      state/                        composer record
      update/                       brownfield source/diff, when present
    No MANIFEST.tsv or pages/views/shells subdirectories are required.

  Legacy batch package:
    batch-<timestamp>/
      MANIFEST.tsv                  match the item to its artifact
      {shells,pages,views}/<slug>/spec/build-spec.md
      {shells,pages,views}/<slug>/design/<kind>.html
      styles/                       shared stylesheet set
      assets/                       shared assets
      unpackaged.md                 loose artifacts excluded from this batch, when present

Record the selected package's actual absolute root in \`uiAuthority.bundlePath\` (the directory
holding \`styles/tokens.css\`), and actual absolute build-spec paths in \`uiAuthority.buildSpecs\`.
Read the matching build spec and design payload, following their asset/style references.
If multiple applicable packages remain ambiguous, report the ambiguity rather than choose
by timestamp. Packaging alone does not approve unrelated designs. If the item's artifact
is not packaged and no explicit package reference failed, consult its loose composed artifact:
${mocksDir ? `  composed pages and views: ${mocksDir}` : '  composed pages and views: (no directory supplied)'}
${shellsDir ? `  composed shells: ${shellsDir}` : '  composed shells: (no directory supplied)'}

Cite the artifact path you used beside the \`file:line\` for every \`ui\` item. List every artifact
path you opened in \`uiAuthority.artifactsConsulted\`, the loose shells and pages in
\`uiAuthority.shellsConsulted\` / \`uiAuthority.pagesConsulted\`, and the mocks directory in
\`uiAuthority.mocksDir\`.

For every \`ui\` item resolved against a packaged artifact, add one entry to
\`uiAuthority.buildSpecs\`: \`item\` (the item id), \`buildSpec\` (the absolute path of that
artifact's \`spec/build-spec.md\`), and \`sections\` (the IDs in that build spec's Sections table —
S1, S2, … — that the item builds; an empty list when it builds the whole artifact or the table
carries no IDs). The Spec cites these and every Task that builds the item carries them in its
build contract, so record only paths you read.

If neither the bundle nor the mocks directory exists, say so in \`evidenceSummary\`.` : `═══ THIS REPOSITORY HOLDS NO UI ═══

Do not look for the cds hand-off bundle or the design mocks.`}

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
   - \`uiAuthority\`: \`bundlePath\`, \`mocksDir\`, \`artifactsConsulted\`, \`shellsConsulted\`, \`pagesConsulted\`, \`buildSpecs\` (each \`{ item, buildSpec, sections }\`), as described above; empty values when the repository holds no UI.
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
  .map((u) => ({ id: u.id.trim(), buildSpec: hasText(u.buildSpec) ? u.buildSpec.trim() : null, sections: ids(u.sections) }))
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
  bundlePath: hasText(facts.bundlePath) ? facts.bundlePath.trim() : null,
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
