export const meta = {
  name: 'built-version',
  description:
    "Records what a Story built, after its deploy to AWS dev is verified and before its pull request. One prd-reality-reconciler session compares the code on the Story's branch with the effective views for the Story's repository and the Epic's delta items placed in it, and writes each difference as a view in built/<subject>/ (in-review), citing file:line. A Story with no difference writes nothing. When a difference exists, depscore.py arch-state confirms every built view is in-review, the architecture-maintainer corrects the effective version from the built views, the architecture-conformance-reviewer checks the correction (at most 2 correction passes), depscore.py arch-approve sets the corrected files to effective, and depscore.py arch-built-remove deletes the built views the effective version now matches — those the architecture-maintainer reports matched and the architecture-conformance-reviewer confirms in matchedBuiltViews — and commits the removal. depscore.py arch-snapshot measures what each session wrote: the comparison may write only under built/<subject>/, and the files the correction wrote are reviewed whether reported or not. A write under arc42 section 2 fails the run and is undone: depscore.py arch-constraints fingerprints that folder before and after and copies it aside, and depscore.py arch-constraints-restore puts it back. Returns { ok, stage, beadId, headline, differences, builtFiles, architectureUpdate, conformance, approval, removal }.",
  phases: [
    { title: 'Compare', detail: "a prd-reality-reconciler session compares the Story branch's code with the effective views and the delta items, and writes each difference to built/<subject>/" },
    { title: 'Correct', detail: 'the architecture-maintainer corrects the effective version from the built views; the architecture-conformance-reviewer checks it; depscore.py arch-approve sets the corrected files to effective' },
    { title: 'Remove', detail: 'depscore.py arch-built-remove deletes the built views the effective version now matches and commits the removal' },
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

// args: { beadId?, story: { id, title? }, repoPath (the Story's worktree), repoName?, branch?, archPath,
//   subject, items?: [{ id, element, status?, from?, to?, evidence? }], depscore: { script, repo } }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const listed = (x) => (Array.isArray(x) ? x.filter(hasText).map((s) => s.trim()) : [])

const story = a.story && typeof a.story === 'object' ? a.story : {}
const beadId = String(a.beadId || story.id || '').trim()
const repo = String(a.repoPath || '').trim().replace(/\/+$/, '')
const archPath = hasText(a.archPath) ? a.archPath.trim().replace(/\/+$/, '') : ''
// The <subject> folder name, derived as depscore.py arch-target derives it (archstate.subject_folder):
// folded to ASCII, lower-cased, every run of characters other than a-z and 0-9 one hyphen, no hyphen
// at either end. A folder name maps to itself, so the Epic's saved target subject passes unchanged.
const subjectFolder = (v) => String(v).normalize('NFKD').replace(/[^\x00-\x7F]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
const subject = hasText(a.subject) ? subjectFolder(a.subject.trim()) : ''
const DS = a.depscore && typeof a.depscore === 'object' && hasText(a.depscore.script) && hasText(a.depscore.repo) ? a.depscore : null
const items = (Array.isArray(a.items) ? a.items : []).filter((i) => i && hasText(i.id) && hasText(i.element))
const MAX_CORRECTIONS = 2
const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'

const handback = (ok, stage, headline, extra) => ({ ok, stage, beadId: beadId || null, headline: String(headline || ''), detailPath: null, ...(extra || {}) })
function died(phaseName) {
  const deaths = dispatchFailures.filter((f) => f.phase === phaseName)
  return deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}
}
const failed = (phaseName, stage, headline, extra) => {
  const deaths = died(phaseName)
  return handback(false, deaths.dispatchFailed ? DISPATCH_FAILED_STAGE : stage, headline, { ...deaths, ...(extra || {}) })
}

if (!beadId) return handback(false, 'input', 'no Story id supplied')
if (!repo) return handback(false, 'input', `no worktree supplied for Story ${beadId}`)
if (!archPath) return handback(false, 'input', "no archPath supplied (the project's ATW_ARCH_PATH): there is no effective version to compare the build with")
if (!subject) return handback(false, 'input', `no architecture subject supplied for Story ${beadId}, or one with no letter or digit: the built views go in built/<subject>/, named for the subject of the Epic's target`)
if (!DS) return handback(false, 'input', 'no depscore script and beads repository supplied: the state check, the section 2 check, the approval and the removal run through depscore.py')

const ARC42 = `${archPath}/arc42`
const CONSTRAINTS = `${ARC42}/02-architecture-constraints`
const BUILT_DIR = `${archPath}/built/${subject}`
const MENU = `${archPath}/reference/diagram-and-model-types.md`
const MODEL = `${archPath}/reference/architecture-documentation-model.md`

const RUN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['exitCode', 'output'],
  properties: { exitCode: { type: 'integer' }, output: { type: 'object' } },
}
/** Runs one depscore.py command in a runner session; returns its JSON output or { error }. */
async function depscore(label, phaseName, commandArgs) {
  const command = `python3 ${shq(DS.script)} -C ${shq(DS.repo)} ${commandArgs}`
  const out = await run(
    `Run exactly this one shell command, once, in the FOREGROUND (never set run_in_background) with the Bash tool's \`timeout\` parameter set to 600000, and change nothing else:

${command}

It prints one JSON object on stdout. Return the process exit code as \`exitCode\` and that JSON object, parsed and unaltered, as \`output\`. If stdout is not JSON, return {"error": "<stdout and stderr, verbatim>"} as \`output\`. Do not retry, do not repair, do not run any other command.`,
    { label, phase: phaseName, model: 'haiku', effort: 'low', schema: RUN_SCHEMA }
  )
  if (!out) return { error: `the ${label} runner returned no result` }
  if (out.exitCode !== 0 || !out.output || out.output.error) {
    const refusals = out.output && Array.isArray(out.output.refusals) ? out.output.refusals.join('; ') : ''
    return { error: (out.output && out.output.error) || refusals || `depscore.py exited ${out.exitCode}`, output: out.output || null }
  }
  return out.output
}

const COMPARE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['differences', 'files', 'summary'],
  properties: {
    differences: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['element', 'effectiveViews', 'built', 'citations', 'file'],
        properties: {
          element: { type: 'string' },
          itemId: { type: 'string' },
          effectiveViews: { type: 'array', items: { type: 'string' } },
          built: { type: 'string' },
          citations: { type: 'array', items: { type: 'string' } },
          file: { type: 'string' },
        },
      },
    },
    files: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
}
const MAINTAIN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['changedFiles', 'createdFiles', 'deletedFiles', 'matched', 'constraintIssues', 'contradictions', 'summary'],
  properties: {
    changedFiles: { type: 'array', items: { type: 'string' } },
    createdFiles: { type: 'array', items: { type: 'string' } },
    deletedFiles: { type: 'array', items: { type: 'string' } },
    matched: { type: 'array', items: { type: 'string' } },
    constraintIssues: { type: 'array', items: { type: 'string' } },
    contradictions: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
}
const CONFORMANCE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['conforms', 'reviewedFiles', 'matchedBuiltViews', 'findings', 'summary'],
  properties: {
    conforms: { type: 'boolean' },
    reviewedFiles: { type: 'array', items: { type: 'string' } },
    matchedBuiltViews: { type: 'array', items: { type: 'string' } },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'finding', 'evidence'],
        properties: { file: { type: 'string' }, finding: { type: 'string' }, evidence: { type: 'string' } },
      },
    },
    summary: { type: 'string' },
  },
}

const ARCH_WHERE = `THE ARCHITECTURE is at ${archPath}. It is not inside any product repository.
- \`arc42/\` is the effective version: the approved architecture. \`arc42/02-architecture-constraints/README.md\` holds the owner's constraints.
- Each view's frontmatter names its \`view_type\`, \`scope\`, \`subject\` and every element it \`shows\`: that frontmatter is the catalog. Find the views of an element by searching it (\`subject:\` and the \`shows:\` lists) for the element's name, in every section, at every scope.
- \`built/<subject>/\` records what a build delivered where it differs from the effective version.
- The architecture documentation model is ${MODEL}; the view types to choose from are ${MENU}.`

/** Returns the section 2 fingerprint, or { error }; with `keep`, section 2 is also copied aside for a restore. */
const constraintsSnapshot = (label, phaseName, keep) => depscore(label, phaseName, `arch-constraints --arch-root ${shq(archPath)}${keep ? ' --keep' : ''}`)
const sameSnapshot = (x, y) =>
  !!x && !!y && !x.error && !y.error && x.exists === y.exists && x.digest === y.digest && JSON.stringify(x.gitStatus || []) === JSON.stringify(y.gitStatus || [])
/** Returns null when section 2 is unchanged since `before`, else puts section 2 back from the copy and returns the failure. */
async function constraintsGuard(label, phaseName, during, extra) {
  const after = await constraintsSnapshot(label, phaseName)
  if (sameSnapshot(before, after)) return null
  const restored = after && after.error ? null : await depscore(`${label}:restore`, phaseName, `arch-constraints-restore --arch-root ${shq(archPath)} --kept ${shq(before.kept)}`)
  const restoreNote = !restored ? '' : restored.error ? `; section 2 could not be put back: ${restored.error}` : '; section 2 was put back as it was'
  const why = after && after.error ? after.error : `git status ${JSON.stringify((after && after.gitStatus) || [])}${restoreNote}`
  return handback(false, 'constraints-written', `section 2 changed while ${during}: ${why}`, { ...(extra || {}), restored })
}
/** Where this step keeps its tree fingerprints: the per-file hashes stay on disk and never pass through a session. */
const SNAP_DIR = `${DS.repo}/.claude/workflow-runs/artifacts/${beadId.replace(/[^A-Za-z0-9._-]+/g, '_')}/built-version`
const TREE_START = `${SNAP_DIR}/tree-start.json`
const TREE_COMPARED = `${SNAP_DIR}/tree-compared.json`
const TREE_LAST = `${SNAP_DIR}/tree-last.json`
/**
 * Fingerprints every file of arc42/, target/ and built/ with depscore.py arch-snapshot: `save` writes
 * the hashes to that file, and each file in `against` (a fingerprint saved earlier) yields the files
 * created, changed and deleted since it, in `diffs`, in that order. Returns the result or { error }.
 */
async function treeSnapshot(label, phaseName, { save, against = [] } = {}) {
  const out = await depscore(label, phaseName, `arch-snapshot --arch-root ${shq(archPath)}${save ? ` --save ${shq(save)}` : ''}${against.map((f) => ` --against ${shq(f)}`).join('')}`)
  if (!out || out.error) return out || { error: 'no result' }
  if (against.length && (!Array.isArray(out.diffs) || out.diffs.length !== against.length)) return { error: 'depscore.py arch-snapshot printed no difference for a saved fingerprint' }
  return out
}
/** Returns diff `i` of a snapshot as absolute paths: { created, changed, deleted }. */
function treeDiff(snap, i) {
  const d = (snap && Array.isArray(snap.diffs) && snap.diffs[i]) || {}
  const abs = (rel) => `${archPath}/${rel}`
  return { created: listed(d.created).map(abs), changed: listed(d.changed).map(abs), deleted: listed(d.deleted).map(abs) }
}
const diffFiles = (d) => [...d.created, ...d.changed, ...d.deleted]

const before = await constraintsSnapshot('constraints:before', 'Compare', true)
if (!before || before.error || !hasText(before.kept)) return failed('Compare', 'compare', `section 2 of the architecture could not be fingerprinted and copied before the step: ${(before && before.error) || 'no copy was named'}`)
const treeBefore = await treeSnapshot('tree:before', 'Compare', { save: TREE_START })
if (!treeBefore || treeBefore.error) return failed('Compare', 'compare', `the architecture could not be fingerprinted before the step: ${(treeBefore && treeBefore.error) || 'no result'}`)

// ---------------------------------------------------------------- Compare
phase('Compare')
const itemLines = items.length
  ? items
      .map((i) => `- ${i.id}: ${i.element}${hasText(i.status) ? ` [${i.status}]` : ''}${hasText(i.from) || hasText(i.to) ? `\n    change: ${i.from || '(unstated)'} → ${i.to || '(unstated)'}` : ''}`)
      .join('\n')
  : '- (no delta item was recorded for this repository)'
const compared = await run(
  `You are the prd-reality-reconciler, recording what Story ${beadId}${story.title ? ` (${story.title})` : ''} BUILT. Its deploy to AWS dev succeeded. Compare the code on the Story's branch with the effective version, and record each difference.

THE CODE is the worktree below, at its checked-out HEAD (the Story's branch). Read it there: \`git -C "${repo}" grep -n <term> HEAD\`, \`git -C "${repo}" show HEAD:<path>\`. Change nothing in it.
${repo}${hasText(a.repoName) ? `\nRepository: ${a.repoName}` : ''}${hasText(a.branch) ? `\nBranch: ${a.branch}` : ''}

${ARCH_WHERE}

THE DELTA ITEMS the Epic placed in this repository:
${itemLines}

DO THIS:
1. Find the effective views that show this repository's elements and each delta item, through the catalog, at every scope.
2. For each element, compare what the code builds with what those views show: components, interfaces, data, events, runtime flows, deployment.
3. For each difference, write one view in ${BUILT_DIR}/, in the section folder the model names for its view type, named for the element it shows. Each view has catalog frontmatter (\`view_type\` from ${MENU}, \`scope\`, \`subject\`, \`shows\`, \`lifecycle_state: in-review\`), a Mermaid diagram where the view type has one, and prose that describes the element as built, citing the code by repository, path and line. Where a view in ${BUILT_DIR}/ already shows the same element, update it in place. Write nothing outside ${BUILT_DIR}/.
4. Where the code matches the effective views, write nothing for it.

Return one entry in \`differences\` per difference: the element, the delta item id where one applies, the effective views it differs from (absolute paths), what was built, the \`file:line\` citations, and the absolute path of the built view that records it. Return in \`files\` the absolute path of every file you wrote or updated under ${BUILT_DIR}/. With no difference, return both empty.`,
  { label: 'built:compare', phase: 'Compare', agentType: 'prd-reality-reconciler', effort: 'medium', schema: COMPARE_SCHEMA }
)
if (!compared) return failed('Compare', 'compare', `the prd-reality-reconciler returned no comparison for Story ${beadId}`)
const differences = (Array.isArray(compared.differences) ? compared.differences : []).filter((d) => d && hasText(d.element))
const guardCompare = await constraintsGuard('constraints:after-compare', 'Compare', 'the build was compared', { differences })
if (guardCompare) return guardCompare
const treeCompared = await treeSnapshot('tree:after-compare', 'Compare', { save: TREE_COMPARED, against: [TREE_START] })
if (!treeCompared || treeCompared.error) return failed('Compare', 'compare', `the architecture could not be fingerprinted after the comparison: ${(treeCompared && treeCompared.error) || 'no result'}`, { differences })
const compareWrites = treeDiff(treeCompared, 0)
const builtFiles = [...new Set([...listed(compared.files), ...differences.map((d) => d.file).filter(hasText).map((f) => f.trim()), ...compareWrites.created, ...compareWrites.changed])]
const outsideBuilt = [...builtFiles, ...compareWrites.deleted].filter((f) => !f.startsWith(`${BUILT_DIR}/`) || f.split('/').includes('..'))
if (outsideBuilt.length) {
  return handback(false, 'compare', `the comparison wrote or reports files outside ${BUILT_DIR}: ${outsideBuilt.join(', ')}`, { differences, builtFiles })
}
if (!differences.length && !builtFiles.length) {
  log(`Built: Story ${beadId} built what the effective version shows; nothing written`)
  return handback(true, 'matches', `Story ${beadId}: the build matches the effective version; no built view was written`, { differences: [], builtFiles: [] })
}
if (!differences.length || !builtFiles.length) {
  return handback(false, 'compare', `the comparison for Story ${beadId} is incomplete: ${differences.length} difference(s) but ${builtFiles.length} built view(s)`, { differences, builtFiles })
}
const states = await depscore('built:state', 'Compare', `arch-state --arch-files ${shq(builtFiles.join(','))} --arch-root ${shq(archPath)}`)
if (!states || states.error) return failed('Compare', 'compare', `depscore.py arch-state did not read the built views: ${(states && states.error) || 'no result'}`, { differences, builtFiles })
const stateOf = states.states && typeof states.states === 'object' ? states.states : {}
const badState = [
  ...(states.refused || []).map((x) => `${x.path} (${x.reason})`),
  ...(states.failed || []).map((x) => `${x.path} (${x.reason})`),
  ...Object.entries(stateOf).filter(([, s]) => s !== 'in-review').map(([p, s]) => `${p} (lifecycle_state ${s || 'missing'})`),
]
if (badState.length) return handback(false, 'compare', `the built views must be in-review: ${badState.join(', ')}`, { differences, builtFiles })
log(`Built: ${differences.length} difference(s) recorded in ${builtFiles.length} view(s) under ${BUILT_DIR}`)

// ---------------------------------------------------------------- Correct
phase('Correct')
const SECTION_2_RULE = `Write nothing under ${CONSTRAINTS}: section 2 holds the owner's constraints, and only the owner changes them; the run fails on any change there. A constraint the build conflicts with goes in \`constraintIssues\`, with the constraint, the built view and the reason.`
const CORRECT_TASK = `Correct the effective version, the folder ${ARC42}, to match what was built, as the architecture documentation model's step 6 describes. The built views are:
${builtFiles.map((f) => `- ${f}`).join('\n')}
For each element a built view shows, find every effective view that shows it through the catalog (\`subject\` and \`shows\`), at every scope, and update it to describe the element as built; add a view where the effective version has none for a built element, in the section folder the model names, named for its subject. Keep every touched view's catalog frontmatter true to what it now shows. Edit in place: no changelog narrative, and no superseded content left beside the new. Leave every \`lifecycle_state\` as you find it: the run sets it after review. Leave ${BUILT_DIR}/ as it is: the run removes each built view once the effective version matches it.
${SECTION_2_RULE}
Report every file you changed, created or deleted as an absolute path under ${ARC42}, in \`matched\` every built view the effective version now matches, and every contradiction with another effective view or open target.`

const touched = (u) => [...new Set([...listed(u.changedFiles), ...listed(u.createdFiles)])]
const allTouched = (u) => [...touched(u), ...listed(u.deletedFiles)]
/**
 * Adds to a report every file the correction wrote since the comparison, measured from the tree, so
 * an unreported write is reviewed too, and saves the tree to TREE_LAST; with `sinceLast` it also names
 * the files changed since the previous measurement. Returns { update, changedSinceLast } or { failure }.
 */
async function measured(u, label, sinceLast) {
  const now = await treeSnapshot(label, 'Correct', { save: TREE_LAST, against: sinceLast ? [TREE_COMPARED, TREE_LAST] : [TREE_COMPARED] })
  if (!now || now.error) return { failure: failed('Correct', 'correct', `the architecture could not be fingerprinted after the correction: ${(now && now.error) || 'no result'}`, { differences, builtFiles, architectureUpdate: u }) }
  const d = treeDiff(now, 0)
  const unreported = diffFiles(d).filter((f) => !allTouched(u).includes(f))
  if (unreported.length) log(`Correct: files written and not reported, added to the review: ${unreported.join(', ')}`)
  const union = (key, extra) => [...new Set([...listed(u[key]), ...extra])]
  return {
    changedSinceLast: sinceLast ? diffFiles(treeDiff(now, 1)) : [],
    update: { ...u, changedFiles: union('changedFiles', d.changed), createdFiles: union('createdFiles', d.created), deletedFiles: union('deletedFiles', d.deleted) },
  }
}
/** Returns the failure when the correction wrote a file in section 2 or outside arc42 (section 2 is put back), else null. */
async function outOfBounds(u) {
  const inSection2 = allTouched(u).filter((f) => f === CONSTRAINTS || f.startsWith(`${CONSTRAINTS}/`))
  const outside = allTouched(u).filter((f) => !f.startsWith(`${ARC42}/`))
  if (!inSection2.length && !outside.length) return null
  if (inSection2.length) {
    const guard = await constraintsGuard('constraints:correct-bounds', 'Correct', 'the effective version was corrected', { differences, builtFiles, architectureUpdate: u })
    if (guard) return guard
  }
  const why = inSection2.length
    ? `the correction wrote in section 2, which holds the owner's constraints: ${inSection2.join(', ')}`
    : `the correction wrote files outside the effective version ${ARC42}: ${outside.join(', ')}`
  return handback(false, 'correct', why, { differences, builtFiles, architectureUpdate: u })
}

let update = await run(`You are the architecture-maintainer.\n\n${CORRECT_TASK}`, { label: 'built:correct', phase: 'Correct', agentType: 'architecture-maintainer', effort: 'medium', schema: MAINTAIN_SCHEMA })
if (!update) return failed('Correct', 'correct', 'the architecture-maintainer returned no result', { differences, builtFiles })
const firstMeasure = await measured(update, 'tree:after-correct')
if (firstMeasure.failure) return firstMeasure.failure
update = firstMeasure.update
const bounds = await outOfBounds(update)
if (bounds) return bounds

let reviewPass = 0
/** Every re-dispatch after a failed review, with what changed in its input. */
const retries = []
/** Marks a review not conforming when it leaves a changed file unreviewed. */
function covered(c) {
  const missed = touched(update).filter((f) => !listed(c.reviewedFiles).includes(f))
  if (!missed.length) return c
  return { ...c, conforms: false, findings: [...(Array.isArray(c.findings) ? c.findings : []), ...missed.map((f) => ({ file: f, finding: 'changed or created by the correction and not reviewed', evidence: 'absent from reviewedFiles' }))] }
}
/** Runs one conformance review of the correction; `again` names the previous review's findings and the files the correction pass changed. */
async function review(again) {
  reviewPass += 1
  const againBlock = again
    ? `\nTHIS IS REVIEW ${reviewPass}. The previous review found the findings below, and correction pass ${again.correction} changed these files to answer them: ${again.changed.join(', ')}. Confirm each finding is resolved, and check the changed files as fully as the rest.\nPREVIOUS FINDINGS:\n${JSON.stringify(again.findings, null, 1)}\n`
    : ''
  const got = await run(
    `You are the architecture-conformance-reviewer. Check one correction of the effective version to match what a build delivered; report findings and fix nothing.

THE BUILT VIEWS (what was built, citing the code):
${builtFiles.map((f) => `- ${f}`).join('\n')}
THE CORRECTION changed or created these files, every one of which you review:
${touched(update).map((f) => `- ${f}`).join('\n') || '- (none)'}
Files it deleted: ${listed(update.deletedFiles).join(', ') || '(none)'}
${againBlock}
${ARCH_WHERE}

Check that the effective version now describes each element as the built views show it, no more and no less; that every effective view the catalog lists for each built element was updated, at every scope; that new views sit in the section folders the model names with catalog frontmatter true to what they show; that no superseded content remains beside the new and no view contradicts another or an open target; and that nothing under ${CONSTRAINTS} changed. Return in \`reviewedFiles\` the absolute path of every file you checked and found conforming; in \`matchedBuiltViews\` the absolute path of every built view above that the effective version now describes completely, compared by you view by view (a built view goes in this list only when every element it shows reads the same in the effective version); and one finding per problem with its file and evidence. \`conforms\` is true only when there is no finding.`,
    { label: `built:review-${reviewPass}`, phase: 'Correct', agentType: 'agent-teams-workforce:architecture-conformance-reviewer', effort: 'medium', schema: CONFORMANCE_SCHEMA }
  )
  return got ? covered(got) : null
}

let conformance = await review()
if (!conformance) return failed('Correct', 'correct', 'the architecture-conformance-reviewer returned no result', { differences, builtFiles, architectureUpdate: update })
let corrections = 0
while (conformance.conforms !== true && corrections < MAX_CORRECTIONS) {
  corrections += 1
  const fixed = await run(
    `You are the architecture-maintainer, CORRECTING your correction of the effective version (pass ${corrections} of ${MAX_CORRECTIONS}). The architecture-conformance-reviewer found the findings below. Correct each one in place, then return the complete report, every pass together.

FINDINGS:
${JSON.stringify(conformance.findings || [], null, 1)}

${CORRECT_TASK}`,
    { label: `built:correct-${corrections}`, phase: 'Correct', agentType: 'architecture-maintainer', effort: 'medium', schema: MAINTAIN_SCHEMA }
  )
  if (!fixed) return failed('Correct', 'correct', `the architecture-maintainer returned no result for correction ${corrections}`, { differences, builtFiles, architectureUpdate: update })
  const merged = (key) => [...new Set([...listed(update[key]), ...listed(fixed[key])])]
  const fixMeasure = await measured({ ...fixed, changedFiles: merged('changedFiles'), createdFiles: merged('createdFiles'), deletedFiles: merged('deletedFiles'), matched: merged('matched') }, `tree:after-correct-${corrections}`, true)
  if (fixMeasure.failure) return fixMeasure.failure
  update = fixMeasure.update
  const fixedBounds = await outOfBounds(update)
  if (fixedBounds) return fixedBounds
  const changedNow = fixMeasure.changedSinceLast
  if (!changedNow.length) {
    const why = `correction pass ${corrections} changed no file, so a further review would judge the same correction; the findings stand: ${(conformance.findings || []).map((f) => `${f.file}: ${f.finding}`).join('; ')}`
    return handback(false, 'correct', why, { differences, builtFiles, architectureUpdate: update, conformance, retries })
  }
  const whatChanged = `correction pass ${corrections} changed ${changedNow.join(', ')} to answer ${(conformance.findings || []).length} finding(s)`
  retries.push({ step: 'built:review', attempt: reviewPass + 1, whatChanged })
  log(`Correct: review again — ${whatChanged}`)
  conformance = await review({ correction: corrections, changed: changedNow, findings: conformance.findings || [] })
  if (!conformance) return failed('Correct', 'correct', 'the architecture-conformance-reviewer returned no result', { differences, builtFiles, architectureUpdate: update })
}
if (conformance.conforms !== true) {
  const why = `the correction does not conform after ${corrections} correction pass(es): ${(conformance.findings || []).map((f) => `${f.file}: ${f.finding}`).join('; ')}`
  return handback(false, 'correct', why, { differences, builtFiles, architectureUpdate: update, conformance })
}
const guardCorrect = await constraintsGuard('constraints:after-correct', 'Correct', 'the effective version was corrected', { differences, builtFiles, architectureUpdate: update, conformance })
if (guardCorrect) return guardCorrect

let approval = null
const toApprove = touched(update)
if (toApprove.length) {
  approval = await depscore('built:approve', 'Correct', `arch-approve --arch-files ${shq(toApprove.join(','))} --reviewed-files ${shq(listed(conformance.reviewedFiles).join(','))} --arch-root ${shq(ARC42)}`)
  const n = approval && approval.summary ? approval.summary : null
  const notSet = approval && !approval.error ? [...listed(approval.unreviewed), ...(approval.refused || []).map((x) => x.path), ...(approval.failed || []).map((x) => x.path)] : []
  if (!n || approval.error || notSet.length) {
    const why = !n || approval.error
      ? `depscore.py arch-approve did not run: ${(approval && approval.error) || 'no result'}`
      : `depscore.py arch-approve did not set these corrected files to effective: ${notSet.join(', ')}`
    return failed('Correct', 'approve', why, { differences, builtFiles, architectureUpdate: update, conformance, approval })
  }
  log(`Approval: ${n.promoted || 0} file(s) set to effective, ${n.unchanged || 0} already effective`)
}

// ---------------------------------------------------------------- Remove
phase('Remove')
const reviewerMatched = new Set(listed(conformance.matchedBuiltViews))
const matched = new Set(listed(update.matched).filter((f) => reviewerMatched.has(f)))
const unmatched = builtFiles.filter((f) => !matched.has(f))
const removable = builtFiles.filter((f) => matched.has(f))
let removal = null
if (removable.length) {
  const message = `docs(architecture): remove the ${subject} built views the effective version now matches`
  removal = await depscore('built:remove', 'Remove', `arch-built-remove --arch-root ${shq(archPath)} --files ${shq(removable.join(','))} --message ${shq(message)}`)
  if (!removal || removal.error) {
    return failed('Remove', 'remove', `depscore.py arch-built-remove did not remove the matched built views: ${(removal && removal.error) || 'no result'}`, { differences, builtFiles, architectureUpdate: update, conformance, approval })
  }
}
if (unmatched.length) {
  return handback(false, 'correct', `the effective version does not yet match these built views, which stay in ${BUILT_DIR}: ${unmatched.join(', ')}`, { differences, builtFiles, architectureUpdate: update, conformance, approval, removal })
}

return handback(true, 'recorded', `Story ${beadId}: ${differences.length} difference(s) from the effective version recorded, the effective version corrected to match (${toApprove.length} file(s) set to effective), and the built views removed`, {
  differences,
  builtFiles,
  architectureUpdate: update,
  conformance,
  approval,
  removal,
  retries,
})
