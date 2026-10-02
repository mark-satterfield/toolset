export const meta = {
  name: 'task-to-deploy',
  description:
    "Builds a Task from its build contract on its Story's branch and commits it only when the repository's whole test suite passes. Establishes (or reuses) the Story's worktree, stashing a reused tree's uncommitted changes; for an infrastructure Task authors the provisioning intent; runs the suite command the repository declares once as a baseline; loops Red until a new test fails with no new collection error and no regression; loops Green until the whole suite exits 0, routing tests the implementer names to Red in update mode; refactors, restoring the pre-refactor snapshot when the suite goes red; for a web-ui Task audits the files it changed by its design source — against the cds bundle the owner supplied (bundle) with the cds plugin's tools/audit-app.py, cds:audit-against-system ruling the findings the script cannot rule on; against the live CDS design system with cds:audit-against-system (cds); not at all for a change with no design impact (none) — sends violations back through the Green loop once and stops with cds-audit when they remain (blocked-upstream when required cds configuration, design artifacts or capabilities remain unresolved), returning the verdict as cdsAudit; updates the documentation; then commits to the Story branch after a final green run. Stops with red-unsatisfied, blocked-upstream or no-progress when the contract cannot be built. It deploys nothing and opens no pull request: the Story deploys and opens one pull request once its last Task is done. Returns { ok, stage, beadId, storyId, headline, detailPath, branch, worktree, commit }.",
  phases: [
    { title: 'Workspace', detail: "establishes or reuses the Story's worktree every writing phase operates in" },
    { title: 'Infra Intent', detail: 'authors the provisioning intent for an infrastructure Task' },
    { title: 'Baseline', detail: "resolves the repository's suite command and runs it before any change" },
    { title: 'Red' },
    { title: 'Green' },
    { title: 'Refactor' },
    { title: 'CDS Audit', detail: "audits a web-ui Task's changed files against its supplied cds bundle or the live CDS design system, by its design source, and sends violations back through the Green loop once" },
    { title: 'Documentation' },
    { title: 'Commit', detail: 'runs the suite a final time and commits the Task to the Story branch' },
    { title: 'Run Ledger', detail: 'writes the run journal on every exit path' },
  ],
}

// args: {
//   bead: { id, repoPath, story: { id, title? }, type?, labels?, title?, description?, specPath?, specPaths?, specSections?,
//           requirementIds?, definitionOfDone?, decisionIds?, acceptanceCriteria?, surfaces?, apiSpec?, eventContracts?, testStrategy?,
//           cdsDesignSource?: 'bundle' | 'cds' | 'none', cdsBundlePath?, cdsBuildSpecs? },
//   infraVocabulary: { types, labels } (the plugin's scripts/infra-vocabulary.json),
//   spec?: object (defaults to bead), implementer?: string, worktreeRoot?: string,
//   cdsRoot?: string (the cds plugin install; else the cds install $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json records),
//   maxRedRounds?: number (default 4), maxGreenRounds?: number (default 8)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const spec = a.spec || bead
const story = bead.story && typeof bead.story === 'object' ? bead.story : {}
const MAX_RED_ROUNDS = a.maxRedRounds || 4
const MAX_GREEN_ROUNDS = a.maxGreenRounds || 8
const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'
const TAIL_CHARS = 4000

// An infrastructure Task, by the same type and label test route-build applies.
const norm = (v) => String(v || '').trim().toLowerCase()
const vocabulary = a.infraVocabulary || {}
const INFRA_TYPES = (Array.isArray(vocabulary.types) ? vocabulary.types : []).map(norm).filter(Boolean)
const INFRA_LABELS = (Array.isArray(vocabulary.labels) ? vocabulary.labels : []).map(norm).filter(Boolean)
const beadLabels = (Array.isArray(bead.labels) ? bead.labels : []).map(norm)
const isInfra = INFRA_TYPES.includes(norm(bead.type)) || beadLabels.some((l) => INFRA_LABELS.includes(l))

// A Task whose surfaces include web-ui takes one design source: bundle (built from the cds bundle the owner
// supplied and audited against it), cds (designed with the CDS design system and audited against the live
// design system) or none (no design impact: no cds design step and no cds audit). A contract that records
// no design source takes bundle when it names a bundle, else cds.
const UI_SURFACE = 'web-ui'
const isUiTask = (Array.isArray(bead.surfaces) ? bead.surfaces : []).map(norm).includes(UI_SURFACE)
const DESIGN_SOURCES = ['bundle', 'cds', 'none']
const designSource = !isUiTask
  ? null
  : DESIGN_SOURCES.includes(norm(bead.cdsDesignSource))
    ? norm(bead.cdsDesignSource)
    : String(bead.cdsBundlePath || '').trim()
      ? 'bundle'
      : 'cds'

if (!bead.id) return { ok: false, stage: 'input', error: 'no bead.id supplied' }
if (!INFRA_TYPES.length || !INFRA_LABELS.length) {
  return { ok: false, stage: 'input', error: 'no infraVocabulary supplied: pass the types and labels from scripts/infra-vocabulary.json' }
}

const runLedger = []
let runDetail = null
let workspaceOut = null
// The cds audit verdict, { verdict: pass | fail | blocked | error, findings, scriptVersion }, once the audit ran.
let cdsVerdict = null

// Logs the journal payload as `RUN-JOURNAL {json}`, or as `RUN-JOURNAL-PART i/n <chunk>` lines when
// it exceeds JOURNAL_CHUNK characters; the host concatenates the parts and writes the journal file.
const JOURNAL_CHUNK = 4000
function emitRunJournal(payload) {
  const body = JSON.stringify(payload)
  if (body.length <= JOURNAL_CHUNK) {
    log(`RUN-JOURNAL ${body}`)
    return
  }
  const parts = []
  for (let i = 0; i < body.length; ) {
    let end = Math.min(i + JOURNAL_CHUNK, body.length)
    const last = body.charCodeAt(end - 1)
    if (end < body.length && last >= 0xd800 && last <= 0xdbff) end -= 1
    parts.push(body.slice(i, end))
    i = end
  }
  parts.forEach((part, i) => log(`RUN-JOURNAL-PART ${i + 1}/${parts.length} ${part}`))
}
function persistRun(outcome) {
  if (!runLedger.length && !runDetail) return null
  try {
    emitRunJournal({ composite: 'task-to-deploy', bead: null, subject: bead.id || null, outcome, runLedger, detail: runDetail })
  } catch (e) {
    log(`run journal could not be serialized: ${e && e.message ? e.message : e}`)
  }
  return null
}

let currentPhase = null
function enterPhase(title) {
  currentPhase = title
  phase(title)
}

// Returns the caller-facing result; `detail` goes to the run journal only.
function handback(ok, stage, headline, detail) {
  runDetail = detail === undefined ? null : detail
  return {
    ok,
    stage,
    beadId: bead.id || null,
    storyId: story.id || null,
    headline: String(headline || ''),
    branch: (workspaceOut && workspaceOut.branch) || null,
    worktree: (workspaceOut && workspaceOut.repoPath) || null,
    ...(cdsVerdict ? { cdsAudit: cdsVerdict } : {}),
  }
}

// Returns the stage for a failed phase result: dispatch failure, or `stage`.
const stageOf = (stage, r) => (!r || r.dispatchFailed ? DISPATCH_FAILED_STAGE : stage)

function implementersOf(artifact) {
  const l = artifact && artifact.ledger
  return l && (l.mode === 'selected' || l.mode === 'reused') && Array.isArray(l.chosen) && l.chosen.length ? l.chosen : undefined
}

const list = (v) => (Array.isArray(v) ? v.filter(Boolean) : [])

// A suite-run failure, { kind: test | load, file, test, line }, keyed the same way in every run.
const entryOf = (f) =>
  f && typeof f === 'object'
    ? { kind: f.kind === 'load' ? 'load' : 'test', file: String(f.file || '').trim().replace(/^\.\//, ''), test: String(f.test || '').trim(), line: String(f.line || '').trim() }
    : null
const idOf = (e) => `${e.kind}|${e.file}|${e.test}`
const describe = (e) => (e.kind === 'load' ? `${e.file || e.line} could not be loaded` : `${e.file}${e.test ? ` ${e.test}` : ''}`)
const failures = (run) => {
  const byId = new Map()
  for (const e of list(run && run.failing).map(entryOf)) if (e && (e.file || e.test)) byId.set(idOf(e), e)
  return byId
}
const failingIds = (run) => new Set(failures(run).keys())
const sameFile = (p, f) => {
  const x = String(p || '').replace(/^\.\//, '')
  const y = String(f || '').replace(/^\.\//, '')
  return !!x && !!y && (x === y || x.endsWith(`/${y}`) || y.endsWith(`/${x}`))
}

// The runner's report as feedback text for the next session.
const runText = (run) =>
  [
    `The suite runner ran \`${(run && run.command) || '(no command)'}\` and it exited ${run ? run.exitCode : 'with no result'}.`,
    run && run.summary ? `Summary: ${run.summary}` : '',
    failures(run).size ? `Failing:\n${[...failures(run).values()].map((e) => e.line || describe(e)).join('\n')}` : '',
    run && run.tail ? `Output (last part):\n${String(run.tail).slice(-TAIL_CHARS)}` : '',
  ]
    .filter(Boolean)
    .join('\n')

const validRun = (r) => !!r && !r.dispatchFailed && Number.isInteger(r.exitCode) && r.exitCode >= 0

const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const FINGERPRINT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['exitCode', 'stdout'],
  properties: { exitCode: { type: 'integer' }, stdout: { type: 'string' } },
}
/** Returns { files: { <path>: <git blob hash or "missing"> } } for the given test files in the tree, or { error }. */
async function fingerprint(tree, files, label) {
  if (!files.length) return { files: {} }
  const command = `cd ${shq(tree)} && for f in ${files.map(shq).join(' ')}; do if [ -f "$f" ]; then printf '%s\\t%s\\n' "$f" "$(git hash-object -- "$f")"; else printf '%s\\tmissing\\n' "$f"; fi; done`
  let out = null
  try {
    out = await agent(
      `Run exactly this one shell command, once, and change nothing else:

${command}

Return its exit code as \`exitCode\` and everything it printed on stdout, verbatim, as \`stdout\`. Do not retry, do not repair, do not run any other command.`,
      { label, phase: currentPhase || 'Green', model: 'haiku', effort: 'low', schema: FINGERPRINT_SCHEMA }
    )
  } catch (err) {
    return { error: String((err && err.message) || err).slice(0, 300) }
  }
  if (!out || out.exitCode !== 0) return { error: `the fingerprint of the test files did not run${out ? `: exit ${out.exitCode}` : ''}` }
  const got = {}
  for (const row of String(out.stdout || '').split('\n')) {
    const [f, h] = row.split('\t')
    if (f && h) got[f.trim()] = h.trim()
  }
  const missing = files.filter((f) => !(f in got))
  return missing.length ? { error: `the fingerprint names no hash for ${missing.join(', ')}` } : { files: got }
}

// ── cds audit: the cds plugin's tools/audit-app.py over the files the Task changed (uncommitted
// against HEAD, untracked included: the Task commits only at the end), then a judgment session on
// the findings the script cannot rule on ──
const CDS_AUDIT_MAX_FINDINGS = 60
const CDS_AUDIT_RUN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['exitCode', 'output'],
  properties: { exitCode: { type: 'integer' }, output: { type: 'object' } },
}
const CDS_JUDGMENT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['rulings'],
  properties: {
    rulings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'line', 'value', 'ruling', 'reason'],
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          value: { type: 'string' },
          ruling: { type: 'string', enum: ['violation', 'allowed', 'cds-gap'] },
          reason: { type: 'string' },
        },
      },
    },
  },
}
// Resolves tools/audit-app.py (cdsRoot, else the cds install the plugin registry records for
// $ATW_CONTROL_REPO, else the user-scope one) and runs it; its exit status is the script's.
const RUN_CDS_AUDIT_PY = `import json, os, subprocess, sys
from pathlib import Path
repo, bundle, override, cap = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
script = Path(override, "tools", "audit-app.py") if override else None
problem = f"{script} does not exist" if script and not script.is_file() else ""
if script is None:
    control = os.environ.get("ATW_CONTROL_REPO", "").strip()
    config = os.environ.get("CLAUDE_CONFIG_DIR", "").strip() or str(Path.home() / ".claude")
    reg = Path(config) / "plugins" / "installed_plugins.json"
    try:
        plugins = json.loads(reg.read_text(encoding="utf-8")).get("plugins", {})
    except (OSError, ValueError) as exc:
        plugins, problem = {}, f"{reg} is unreadable: {exc}"
    ranked = []
    for key, entries in plugins.items():
        if not key.startswith("cds@") or not isinstance(entries, list):
            continue
        for e in entries:
            path = Path(str(e.get("installPath") or ""), "tools", "audit-app.py") if isinstance(e, dict) else None
            if not path or not path.is_file():
                continue
            if e.get("scope") in ("local", "project") and control and os.path.normpath(str(e.get("projectPath") or "")) == os.path.normpath(control):
                ranked.append((0, str(path)))
            elif e.get("scope") == "user":
                ranked.append((1, str(path)))
    if ranked:
        script = Path(sorted(ranked)[0][1])
    elif not problem:
        problem = f"{reg} lists no cds install shipping tools/audit-app.py at user scope or for $ATW_CONTROL_REPO"
if problem:
    print(json.dumps({"error": problem}))
    sys.exit(2)
done = subprocess.run([sys.executable, str(script), "--repo", repo, "--bundle", bundle], capture_output=True, text=True)
try:
    report = json.loads(done.stdout)
except ValueError:
    print(json.dumps({"error": (done.stdout + done.stderr).strip()[-2000:] or f"audit-app.py exited {done.returncode} and printed nothing"}))
    sys.exit(2)
findings = report.get("findings") or []
if len(findings) > int(cap):
    report["findings"], report["truncated"] = findings[: int(cap)], len(findings)
def cell(v):
    return "" if v is None else str(v)
canon = "\\n".join("\\t".join(cell(f.get(k)) for k in ("file", "line", "rule", "value", "ruling")) for f in report.get("findings") or [] if isinstance(f, dict))
h = 0x811C9DC5
for ch in f"{cell(report.get('scriptVersion'))}\\n{done.returncode}\\n{cell(report.get('truncated'))}\\n{canon}":
    h = ((h ^ ord(ch)) * 0x01000193) & 0xFFFFFFFF
report["digest"] = format(h, "08x")
print(json.dumps(report))
sys.exit(done.returncode)`

// The digest RUN_CDS_AUDIT_PY prints: FNV-1a (32-bit) over the script version, the exit status, the
// truncated count and each finding's file, line, rule, value and ruling, by code point. The verdict is
// computed from the relayed report only when this recomputes to the digest the script printed, so a
// relay that drops, adds or alters a finding is refused instead of acted on.
const cell = (v) => (v === null || v === undefined ? '' : String(v))
function auditDigest(report, exitCode) {
  const canon = list(report.findings)
    .filter((f) => f && typeof f === 'object')
    .map((f) => ['file', 'line', 'rule', 'value', 'ruling'].map((k) => cell(f[k])).join('\t'))
    .join('\n')
  let h = 0x811c9dc5
  for (const ch of `${cell(report.scriptVersion)}\n${exitCode}\n${cell(report.truncated)}\n${canon}`) {
    h = Math.imul(h ^ ch.codePointAt(0), 0x01000193) >>> 0
  }
  return h.toString(16).padStart(8, '0')
}

const findingText = (f) => `${f.file}:${f.line} ${f.rule} ${f.value}${f.reason ? ` (${f.reason})` : ''}`

/** Runs the audit script over the Task's changes and rules its judgment findings; returns { error } or { report, violations, gaps, allowed, scriptVersion }. */
async function auditCds(tree, bundle, label) {
  let out = null
  try {
    out = await agent(
      `Run exactly this one shell command, once, in the FOREGROUND, and change nothing else:

python3 -c ${shq(RUN_CDS_AUDIT_PY)} ${shq(tree)} ${shq(bundle)} ${shq(String(a.cdsRoot || '').trim())} ${CDS_AUDIT_MAX_FINDINGS}

It prints one JSON object on stdout and exits 0 (clean), 1 (findings) or 2 (it could not audit). Return the exit code as \`exitCode\` and that JSON object, parsed and unaltered (every key and value, the \`digest\` included), as \`output\`. If stdout is not JSON, return {"error": "<stdout and stderr, verbatim>"} as \`output\`. Do not retry, do not repair, do not run any other command.`,
      { label, phase: currentPhase || 'CDS Audit', model: 'haiku', effort: 'low', schema: CDS_AUDIT_RUN_SCHEMA }
    )
  } catch (err) {
    return { error: String((err && err.message) || err).slice(0, 300) }
  }
  const report = (out && out.output) || {}
  if (!out || ![0, 1].includes(out.exitCode) || report.error || !Array.isArray(report.findings)) {
    return { error: String(report.error || `the cds audit did not run${out ? `: exit ${out.exitCode}` : ''}`).slice(0, 500), scriptVersion: report.scriptVersion || null }
  }
  if (String(report.digest || '') !== auditDigest(report, out.exitCode)) {
    return { error: 'the relayed cds audit report does not match the digest the audit script printed, so its findings are not the script\'s own', scriptVersion: report.scriptVersion || null }
  }
  if ((out.exitCode === 0) !== (report.findings.length === 0 && !report.truncated)) {
    return { error: `the cds audit exited ${out.exitCode} with ${report.truncated || report.findings.length} finding(s)`, scriptVersion: report.scriptVersion || null }
  }
  const scriptVersion = String(report.scriptVersion || 'unknown')
  const findings = report.findings.filter((f) => f && typeof f === 'object')
  const violations = findings.filter((f) => f.ruling !== 'judgment')
  const gaps = []
  const allowed = []
  const toJudge = findings.filter((f) => f.ruling === 'judgment')
  const sameFinding = (x, f) => x && x.file === f.file && Number(x.line) === Number(f.line) && x.value === f.value
  let unruled = toJudge
  for (let pass = 1; unruled.length && pass <= 2; pass++) {
    let judged = null
    try {
      judged = await agent(
        `Use the Skill tool to load cds:audit-against-system, then rule on findings a deterministic cds audit could not rule on. They come from the files this Task changed in the work tree at ${tree}, audited against the cds bundle at ${bundle} (its stylesheet set is the only design system the app may use).

Each finding is a class name the bundle's stylesheets do not name. Read the line in the file, the applicable bundle design artifacts and stylesheets, and the audit-against-system skill. Use supplied applicable mock/build-spec choices, graphics and stylesheets as design inputs. A static mock communicates design intent without specifying every detail; preserve its established intent and any explicit precision requirements, and use judgment with the Task requirements, configured cds and approved application standards for unspecified interactions, states and responsive behavior. When no mock is supplied and the Task delegates UI design, judge that design against configured cds and the approved application standards; absence of a pre-existing Page or Section preset is not itself a missing capability.

Consider supported configuration/composition and generated-stylesheet freshness when identifying the remedy. Missing output in this bundle does not by itself prove that the cds plugin needs an extension. Distinguish a configuration or artifact correction from a genuinely missing capability; do not invent off-system styling or treat unverified output as allowed. Rule each finding:
- violation: the class styles the UI outside cds (a utility class, a component class of the app's own, a value cds tokens cover) and the code must use the cds classes and tokens instead;
- allowed: the class carries no styling (a behaviour or test hook, a third-party library's own class the cds bundle does not style);
- cds-gap: required system-provided UI remains unavailable in the applicable bundle; name the unresolved configuration, generated artifact or actual missing capability and the evidence. A plugin extension is required only when the evidence establishes a capability the configured system cannot supply.

Findings, one per line (file:line rule value):
${unruled.map(findingText).join('\n')}

Return one ruling per finding, with its file, line and value exactly as given, the ruling, and a one-sentence reason. Change no file.`,
        { label: `${label}:judgment${pass > 1 ? `-${pass}` : ''}`, phase: currentPhase || 'CDS Audit', schema: CDS_JUDGMENT_SCHEMA }
      )
    } catch (err) {
      return { error: `the judgment on ${unruled.length} cds finding(s) threw: ${String((err && err.message) || err).slice(0, 300)}`, scriptVersion }
    }
    const rulings = list(judged && judged.rulings)
    const still = []
    for (const f of unruled) {
      const r = rulings.find((x) => sameFinding(x, f))
      if (!r) {
        still.push(f)
        continue
      }
      const ruled = { ...f, ruling: r.ruling, reason: r.reason }
      if (ruled.ruling === 'allowed') allowed.push(ruled)
      else if (ruled.ruling === 'cds-gap') gaps.push(ruled)
      else violations.push(ruled)
    }
    unruled = still
  }
  if (unruled.length) {
    return { error: `cds:audit-against-system returned no ruling, after being asked twice, on ${unruled.length} finding(s): ${unruled.slice(0, 5).map(findingText).join('; ')}`, scriptVersion }
  }
  if (report.truncated) log(`cds audit: ${report.truncated} finding(s); the first ${CDS_AUDIT_MAX_FINDINGS} are ruled on`)
  return { report, violations, gaps, allowed, scriptVersion }
}

const LIVE_AUDIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['audited', 'findings'],
  properties: {
    audited: { type: 'boolean' },
    error: { type: 'string' },
    files: { type: 'array', items: { type: 'string' } },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'line', 'rule', 'value', 'ruling', 'reason'],
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          rule: { type: 'string' },
          value: { type: 'string' },
          ruling: { type: 'string', enum: ['violation', 'allowed', 'cds-gap'] },
          reason: { type: 'string' },
        },
      },
    },
  },
}
/** Audits the Task's changes against the live CDS design system with cds:audit-against-system; returns { error } or { report, violations, gaps, allowed, scriptVersion }. */
async function auditCdsLive(tree, label) {
  let out = null
  try {
    out = await agent(
      `Use the Skill tool to load cds:audit-against-system, then audit the UI files this Task changed against the live Configurable Design System (cds) — the project's design system config and the stylesheets, tokens and components it defines. No mockup was supplied for this Task: its UI was designed with cds, so the live design system is the only standard it is held to.

The files: those the work tree at ${tree} changed against HEAD, untracked included (\`git -C ${shq(tree)} status --porcelain\`), restricted to markup, component, script and stylesheet files. Change no file.

Report every finding as { file (relative to the tree), line, rule (the compliance rule the skill names), value (the offending class, property or literal), ruling, reason (one sentence) }, ruling each:
- violation: the code styles the UI outside cds (a raw color or length, an inline style, a stylesheet or token of its own, a class cds does not define that carries styling) and must use the cds classes and tokens instead;
- allowed: it carries no styling (a behaviour or test hook, a third-party library's own class);
- cds-gap: the UI needs something the configured design system does not supply; name the missing configuration or capability and the evidence.

Return \`audited\` true with the files you audited and the findings (an empty list when there are none), or \`audited\` false with \`error\` naming what stopped the audit.`,
      { label, phase: currentPhase || 'CDS Audit', schema: LIVE_AUDIT_SCHEMA }
    )
  } catch (err) {
    return { error: String((err && err.message) || err).slice(0, 300), scriptVersion: 'audit-against-system' }
  }
  if (!out || out.audited !== true || !Array.isArray(out.findings)) {
    return { error: String((out && out.error) || 'cds:audit-against-system returned no audit').slice(0, 500), scriptVersion: 'audit-against-system' }
  }
  const findings = out.findings.filter((f) => f && typeof f === 'object')
  return {
    report: { findings, files: list(out.files) },
    violations: findings.filter((f) => f.ruling === 'violation'),
    gaps: findings.filter((f) => f.ruling === 'cds-gap'),
    allowed: findings.filter((f) => f.ruling === 'allowed'),
    scriptVersion: 'audit-against-system',
  }
}

let result
try {
  result = await (async () => {
    if (!String(bead.repoPath || '').trim()) {
      return {
        ...handback(false, 'input', `${bead.id} carries no repoPath, so its build contract is incomplete. The repository is ruled during elaboration: re-elaborate the Task's Story, or record the repository on the Task as its repoPath.`),
        incompleteContract: ['repoPath'],
        requiredHumanActions: [`re-elaborate the Story of ${bead.id}, or record the ruled repository on it as its repoPath`],
      }
    }
    if (!String(story.id || '').trim()) {
      return {
        ...handback(false, 'input', `${bead.id} names no Story. A Task is built on its Story's branch and deploys with its Story, so it needs one: parent it to the Story of its repository.`),
        incompleteContract: ['story'],
        requiredHumanActions: [`parent ${bead.id} to the Story of its repository`],
      }
    }
    if (designSource === 'bundle' && !String(bead.cdsBundlePath || '').trim()) {
      return {
        ...handback(false, 'input', `${bead.id} takes design source bundle but its build contract names no cds bundle (cds_bundle_path), so it cannot be built from the supplied bundle or audited against it.`),
        incompleteContract: ['cdsBundlePath'],
        requiredHumanActions: [`record the supplied cds bundle on ${bead.id} as cds_bundle_path, or set its cds_design_source to cds when no mockup is supplied`],
      }
    }

    enterPhase('Workspace')
    const workspace = await workflow('agent-teams-workforce:workspace', {
      repoPath: bead.repoPath,
      beadId: story.id,
      branchPrefix: 'story',
      purpose: story.title || `Story ${story.id}`,
      worktreeRoot: a.worktreeRoot,
      stashUncommitted: true,
      stashLabel: bead.id,
    })
    if (!workspace || workspace.ok !== true || !workspace.repoPath) {
      const why = (workspace && Array.isArray(workspace.blocked) && workspace.blocked[0]) || 'the workspace step returned nothing'
      return handback(false, stageOf('workspace', workspace), `no worktree was established: ${why}`, { workspace: workspace || null })
    }
    workspaceOut = workspace
    const workRepoPath = workspace.repoPath
    if (workspace.ledger) runLedger.push(workspace.ledger)

    const declaredSurfaces = Array.isArray(bead.surfaces) ? bead.surfaces : null
    const structuralSurfaces = [
      bead.apiSpec ? 'api-contract' : null,
      Array.isArray(bead.eventContracts) && bead.eventContracts.length ? 'event-chain' : null,
    ].filter(Boolean)
    const contractSurfaces = declaredSurfaces
      ? [...new Set([...declaredSurfaces, ...structuralSurfaces])]
      : structuralSurfaces.length
        ? structuralSurfaces
        : null
    const contract = {
      spec,
      bead: { id: bead.id, title: bead.title || null, description: bead.description || null, repoPath: workRepoPath },
      repoPath: workRepoPath,
      acceptanceCriteria: Array.isArray(bead.acceptanceCriteria) ? bead.acceptanceCriteria : [],
      decisionIds: [
        ...new Set(
          [...(Array.isArray(spec && spec.decisionIds) ? spec.decisionIds : []), ...(Array.isArray(bead.decisionIds) ? bead.decisionIds : [])]
            .map((x) => String(x || '').trim())
            .filter(Boolean)
        ),
      ],
      surfaces: contractSurfaces,
      testStrategy: bead.testStrategy && typeof bead.testStrategy === 'object' ? bead.testStrategy : null,
      cdsDesignSource: designSource,
      cdsBundlePath: String(bead.cdsBundlePath || '').trim() || null,
      cdsBuildSpecs: list(bead.cdsBuildSpecs).map((x) => String(x).trim()).filter(Boolean),
    }

    let intent = null
    if (isInfra) {
      enterPhase('Infra Intent')
      intent = await workflow('agent-teams-workforce:infra-intent', {
        change: { id: bead.id, title: bead.title, description: bead.description, repoPath: workRepoPath },
      })
      if (!intent || !intent.provisioningIntent) {
        return handback(false, stageOf('infra-intent', intent), `infra-intent: ${(intent && intent.reason) || 'no provisioning intent was produced'}`, { intent: intent || null })
      }
      const stacks = Array.isArray(intent.affectedStacks) ? intent.affectedStacks : []
      contract.affectedStacks = stacks
      contract.provisioningIntent = intent.provisioningIntent
      contract.acceptanceCriteria = [
        ...contract.acceptanceCriteria.filter(Boolean),
        {
          given: `the provisioning intent for ${bead.title || 'this infrastructure change'} on stacks ${stacks.join(', ') || '(affected stacks)'}`,
          when: 'cdk synth runs against the changed stacks',
          then: 'the synthesized template asserts the intended resources and their properties, the cross-stack references the stacks write and read, and the IAM permissions the intent names',
        },
      ]
    }
    const implementer = a.implementer || (isInfra ? 'cdk-stack-author' : undefined)

    // ── Baseline: the suite command the repository declares, resolved once and reused ──
    enterPhase('Baseline')
    const baseline = await workflow('agent-teams-workforce:suite-run', { repoPath: workRepoPath, label: 'baseline' })
    if (baseline && baseline.resolveError) {
      return {
        ...handback(false, 'baseline', `baseline: ${workRepoPath} declares no test command (${baseline.resolveError}). A Task is committed only when the repository's whole suite passes, so the repository must say how its suite runs.`, { baseline }),
        requiredHumanActions: [`declare the command that runs the whole test suite in the AGENTS.md or CLAUDE.md of the repository at ${bead.repoPath}, or as the \`test\` task in its Taskfile`],
      }
    }
    if (!validRun(baseline) || !String(baseline.command || '').trim()) {
      return handback(false, stageOf('baseline', baseline), `baseline: the suite runner returned no exit code: ${(baseline && baseline.reason) || 'no result'}`, { baseline: baseline || null })
    }
    const suiteCommand = String(baseline.command).trim()
    contract.suiteCommand = suiteCommand
    const baselineIds = failingIds(baseline)
    const runSuite = async (label) => {
      const r = await workflow('agent-teams-workforce:suite-run', { repoPath: workRepoPath, command: suiteCommand, label })
      return r || null
    }
    log(`Baseline: \`${suiteCommand}\` exited ${baseline.exitCode}; ${baselineIds.size} failing before any change`)

    // ── Red: loops until a new test fails, with no new collection error and no regression ──
    const redFiles = []
    const addRedFiles = (r) => {
      for (const f of list(r && r.testFiles).map(String)) if (!redFiles.includes(f)) redFiles.push(f)
    }
    const judgeRed = (run) => {
      const inRedFile = (e) => redFiles.some((f) => sameFile(e.file, f))
      const fresh = [...failures(run).entries()].filter(([id]) => !baselineIds.has(id)).map(([, e]) => e)
      const collection = fresh.filter((e) => e.kind === 'load').map(describe)
      const redFails = fresh.filter((e) => e.kind === 'test' && inRedFile(e)).map(describe)
      const regressions = fresh.filter((e) => e.kind === 'test' && !inRedFile(e)).map(describe)
      const reasons = [
        redFails.length ? '' : 'no test in a file Red wrote or edited fails',
        collection.length ? `test files that no longer load: ${collection.join('; ')}` : '',
        regressions.length ? `tests outside Red's files that did not fail at baseline now fail: ${regressions.join('; ')}` : '',
      ].filter(Boolean)
      return { ok: run.exitCode !== 0 && !reasons.length, reasons, redFails, collection, regressions }
    }

    let red = null
    let redRun = null
    let redFeedback = ''
    let previousRedKey = null
    for (let round = 1; ; round++) {
      enterPhase('Red')
      red = await workflow('agent-teams-workforce:tdd-red', {
        contract,
        feedback: redFeedback,
        ...(redFiles.length ? { red: { testFiles: [...redFiles] } } : {}),
      })
      if (red && red.ledger) runLedger.push(red.ledger)
      if (!red || red.dispatchFailed) {
        return handback(false, stageOf('red', red), `red: ${(red && red.reason) || 'the Red phase returned nothing'}`, { red })
      }
      addRedFiles(red)
      redRun = await runSuite(`red-${round}`)
      if (!validRun(redRun)) {
        return handback(false, stageOf('red', redRun), `red: the suite runner returned no exit code: ${(redRun && redRun.reason) || 'no result'}`, { red, run: redRun })
      }
      const verdict = judgeRed(redRun)
      if (verdict.ok) {
        log(`Red: round ${round} satisfied — ${verdict.redFails.length} new failing test(s) in Red's files`)
        break
      }
      log(`Red: round ${round} not satisfied — ${verdict.reasons.join('; ')}`)
      if (round >= MAX_RED_ROUNDS) {
        return {
          ...handback(
            false,
            'red-unsatisfied',
            `red-unsatisfied: after ${round} Red round(s) the suite does not show the Task's new tests failing cleanly: ${verdict.reasons.join('; ')}`,
            { red, run: redRun, verdict, baseline }
          ),
          evidence: runText(redRun).slice(0, TAIL_CHARS),
        }
      }
      // A round whose suite fails exactly as the round before gives Red the same input again.
      const redKey = JSON.stringify([redRun.exitCode, ...[...failingIds(redRun)].sort(), ...verdict.reasons])
      if (redKey === previousRedKey) {
        return {
          ...handback(false, 'no-progress', `no-progress: Red round ${round} left the suite exactly as the round before: ${verdict.reasons.join('; ')}`, { red, run: redRun, verdict }),
          evidence: runText(redRun).slice(0, TAIL_CHARS),
        }
      }
      previousRedKey = redKey
      redFeedback = `The suite does not show Red yet: ${verdict.reasons.join('; ')}.\n${runText(redRun)}`
      runLedger.push({ phase: 'retry:red', round: round + 1, whatChanged: `Red round ${round + 1} is given round ${round}'s suite result: ${verdict.reasons.join('; ')}` })
    }

    // ── Green: loops until the whole suite exits 0. The CDS Audit sends its violations back through
    // this same loop, with tag 'cds-green' and the findings as the first round's feedback. ──
    const baselineNote = baselineIds.size
      ? `\nThe suite already failed before this Task on: ${[...failures(baseline).values()].map(describe).join('; ')}. Green means the whole suite exits 0, so these must pass too.`
      : ''
    let green = null
    let finalRun = null
    /** Runs Green rounds until the suite exits 0; returns { run } when green, or { stop } (a handback) when the loop ends without it. */
    const greenLoop = async (firstFeedback, tag, what) => {
      let greenFeedback = firstFeedback
      let previousKey = null
      for (let round = 1; ; round++) {
        enterPhase('Green')
        const testPrint = await fingerprint(workRepoPath, [...redFiles], `${tag}-${round}:tests-before`)
        if (testPrint.error) return { stop: handback(false, 'green', `${what}: Red's test files could not be fingerprinted before Green round ${round}: ${testPrint.error}`, {}) }
        const g = await workflow('agent-teams-workforce:tdd-green', {
          contract,
          red: { ...red, testFiles: [...redFiles], evidence: runText(redRun) },
          implementer,
          implementers: implementersOf(green),
          feedback: greenFeedback,
        })
        if (g && g.ledger) runLedger.push(g.ledger)
        if (!g || g.dispatchFailed) {
          return { stop: handback(false, stageOf('green', g), `${what}: ${(g && g.reason) || 'the Green phase returned nothing'}`, { green: g }) }
        }
        green = g
        const testsAfter = await fingerprint(workRepoPath, Object.keys(testPrint.files), `${tag}-${round}:tests-after`)
        if (testsAfter.error) return { stop: handback(false, 'green', `${what}: Red's test files could not be fingerprinted after Green round ${round}: ${testsAfter.error}`, { green: g }) }
        const touchedTests = Object.keys(testPrint.files).filter((f) => testPrint.files[f] !== testsAfter.files[f])
        if (touchedTests.length) {
          return {
            stop: handback(
              false,
              'green-modified-tests',
              `green-modified-tests: ${what} round ${round} changed test files Red wrote, which Green leaves to Red (a test Green believes is wrong goes in testIssues): ${touchedTests.join(', ')}`,
              { green: g, touchedTests }
            ),
          }
        }
        let run = await runSuite(`${tag}-${round}`)
        if (!validRun(run)) {
          return { stop: handback(false, stageOf('green', run), `${what}: the suite runner returned no exit code: ${(run && run.reason) || 'no result'}`, { green: g, run }) }
        }
        if (run.exitCode === 0) return { run }

        const upstream = list(g.upstreamMissing)
        if (upstream.length) {
          return {
            stop: {
              ...handback(
                false,
                'blocked-upstream',
                `blocked-upstream: the suite cannot pass until something outside this Task exists: ${upstream.map((u) => u.what).join('; ')}`,
                { green: g, run, upstreamMissing: upstream }
              ),
              upstreamMissing: upstream,
              evidence: runText(run).slice(0, TAIL_CHARS),
            },
          }
        }

        let redUpdated = false
        const issues = list(g.testIssues)
        if (issues.length) {
          enterPhase('Red')
          const updated = await workflow('agent-teams-workforce:tdd-red', {
            contract,
            testIssues: issues,
            red: { testFiles: [...redFiles] },
            feedback: runText(run),
          })
          if (updated && updated.ledger) runLedger.push(updated.ledger)
          if (!updated || updated.dispatchFailed) {
            return { stop: handback(false, stageOf('red', updated), `red (update): ${(updated && updated.reason) || 'the Red update returned nothing'}`, { green: g, red: updated, issues }) }
          }
          addRedFiles(updated)
          redUpdated = true
          run = await runSuite(`${tag === 'green' ? '' : `${tag}-`}red-update-${round}`)
          if (!validRun(run)) {
            return { stop: handback(false, stageOf('red', run), `red (update): the suite runner returned no exit code: ${(run && run.reason) || 'no result'}`, { red: updated, run }) }
          }
          if (run.exitCode === 0) return { run }
        }

        const key = JSON.stringify([run.exitCode, ...[...failingIds(run)].sort()])
        const changedNothing = !list(g.changedFiles).length && !redUpdated
        if (changedNothing && key === previousKey) {
          return {
            stop: {
              ...handback(false, 'no-progress', `no-progress: ${what} round ${round} changed no file and the suite fails exactly as it did the round before`, { green: g, run }),
              evidence: runText(run).slice(0, TAIL_CHARS),
            },
          }
        }
        previousKey = key
        if (round >= MAX_GREEN_ROUNDS) {
          return { stop: handback(false, 'green', `${what}: the suite is not green after ${round} Green round(s): ${run.summary || `exit ${run.exitCode}`}`, { green: g, run }) }
        }
        greenFeedback = `The suite is not green yet.${redUpdated ? ' The test author has ruled on the tests you named; their decisions are in the tests now.' : ''}\n${runText(run)}${baselineNote}`
        runLedger.push({
          phase: 'retry:green',
          round: `${tag}-${round + 1}`,
          whatChanged: `Green round ${round + 1} is given round ${round}'s suite result${list(g.changedFiles).length ? ` after round ${round} changed ${list(g.changedFiles).join(', ')}` : ''}${redUpdated ? ', and the tests the test author updated' : ''}`,
        })
      }
    }
    const built = await greenLoop(`${runText(redRun)}${baselineNote}`, 'green', 'green')
    if (built.stop) return built.stop
    finalRun = built.run

    // ── Refactor: ends green, refactored or restored to its snapshot ──
    enterPhase('Refactor')
    const refactor = await workflow('agent-teams-workforce:tdd-refactor', { contract, green })
    if (refactor && refactor.ledger) runLedger.push(refactor.ledger)
    if (!refactor || refactor.dispatchFailed) {
      return handback(false, stageOf('refactor', refactor), `refactor: ${(refactor && refactor.reason) || 'the Refactor phase returned nothing'}`, { refactor })
    }
    let refactorRun = await runSuite('refactor')
    if (!validRun(refactorRun)) {
      return handback(false, stageOf('refactor', refactorRun), `refactor: the suite runner returned no exit code: ${(refactorRun && refactorRun.reason) || 'no result'}`, { refactor, run: refactorRun })
    }
    let restored = null
    if (refactorRun.exitCode !== 0) {
      const snapshot = String(refactor.snapshotTree || '').trim()
      if (!snapshot) {
        return handback(false, 'refactor', `refactor: the suite is red after the refactor and the refactor recorded no snapshot to restore: ${refactorRun.summary || `exit ${refactorRun.exitCode}`}`, { refactor, run: refactorRun })
      }
      restored = await workflow('agent-teams-workforce:tdd-refactor', { contract, restoreTo: snapshot })
      if (!restored || restored.dispatchFailed || restored.restored !== true) {
        return handback(false, stageOf('refactor', restored), `refactor: the suite is red after the refactor and the tree could not be restored to ${snapshot}`, { refactor, restored, run: refactorRun })
      }
      refactorRun = await runSuite('refactor-restored')
      if (!validRun(refactorRun) || refactorRun.exitCode !== 0) {
        return handback(false, stageOf('refactor', refactorRun), `refactor: the suite is red after restoring the pre-refactor snapshot ${snapshot}: ${(refactorRun && refactorRun.summary) || 'no result'}`, { refactor, restored, run: refactorRun })
      }
      log(`Refactor: the suite went red, so the tree was restored to ${snapshot}`)
    }

    // ── CDS Audit: a web-ui Task's changes against its supplied cds bundle (bundle) or the live CDS design
    // system (cds); a change with no design impact (none) is not audited. Violations go back through the Green loop once ──
    if (isUiTask && designSource !== 'none') {
      enterPhase('CDS Audit')
      const bundle = designSource === 'bundle' ? contract.cdsBundlePath : null
      const runAudit = (label) => (bundle ? auditCds(workRepoPath, bundle, label) : auditCdsLive(workRepoPath, label))
      const standard = bundle
        ? `The cds bundle at ${bundle} (its styles/ stylesheet set) is the only source of visual design: replace each finding with the classes and custom properties the bundle ships`
        : 'No mockup was supplied: the live CDS design system (the project\'s design system config and the stylesheets, tokens and components it defines) is the only source of visual design: replace each finding with the cds classes and custom properties'
      const verdictOf = (audit) => ({
        verdict: audit.violations.length ? 'fail' : audit.gaps.length ? 'blocked' : 'pass',
        findings: audit.violations.length + audit.gaps.length,
        scriptVersion: audit.scriptVersion,
      })
      const auditFailed = (audit, when) => {
        cdsVerdict = { verdict: 'error', findings: 0, scriptVersion: audit.scriptVersion || null }
        return handback(false, 'cds-audit', `cds-audit: the cds audit ${when} could not rule: ${audit.error}`, { cdsAudit: audit })
      }
      let audit = await runAudit('cds-audit-1')
      if (audit.error) return auditFailed(audit, 'after Refactor')
      log(`CDS Audit: ${audit.violations.length} violation(s), ${audit.gaps.length} cds gap(s), ${audit.allowed.length} allowed`)
      if (audit.violations.length) {
        const brief = `The cds audit found UI code that styles outside the cds design system. ${standard}, and add no stylesheet, inline style, color or length of your own. Use supplied applicable mock/build-spec choices, graphics and stylesheets as design inputs that need not specify every detail. Preserve their established intent and any explicit precision requirements; use judgment with the Task requirements and configured cds for unspecified interactions, states and responsive behavior; when this Task instead owns UI design without a mock, use configured cds and the approved application standards. Resolve findings through supported configuration/composition or generated-artifact correction where applicable. If an input or capability outside this Task remains necessary, name it with evidence in upstreamMissing; do not assume a cds plugin extension is required merely because the current bundle lacks the output. The whole suite has to stay green.
Findings (file:line rule value):
${audit.violations.map(findingText).join('\n')}${baselineNote}`
        runLedger.push({ phase: 'retry:green', round: 'cds-audit', whatChanged: `Green is given the ${audit.violations.length} cds audit violation(s) as its brief` })
        const fixed = await greenLoop(brief, 'cds-green', 'green (cds audit)')
        if (fixed.stop) {
          cdsVerdict = { verdict: fixed.stop.stage === 'blocked-upstream' ? 'blocked' : 'fail', findings: audit.violations.length, scriptVersion: audit.scriptVersion }
          return { ...fixed.stop, cdsAudit: cdsVerdict }
        }
        const upstream = list(green && green.upstreamMissing)
        if (upstream.length) {
          cdsVerdict = { verdict: 'blocked', findings: audit.violations.length, scriptVersion: audit.scriptVersion }
          return {
            ...handback(false, 'blocked-upstream', `blocked-upstream: the cds audit violations cannot be fixed until something outside this Task exists: ${upstream.map((u) => u.what).join('; ')}`, { green, cdsAudit: audit, upstreamMissing: upstream }),
            upstreamMissing: upstream,
            evidence: audit.violations.map(findingText).join('\n').slice(0, TAIL_CHARS),
          }
        }
        enterPhase('CDS Audit')
        audit = await runAudit('cds-audit-2')
        if (audit.error) return auditFailed(audit, 'after the Green round')
        log(`CDS Audit (after Green): ${audit.violations.length} violation(s), ${audit.gaps.length} cds gap(s), ${audit.allowed.length} allowed`)
      }
      cdsVerdict = verdictOf(audit)
      if (audit.violations.length) {
        return {
          ...handback(false, 'cds-audit', `cds-audit: ${audit.violations.length} cds violation(s) remain after one Green round: ${audit.violations.slice(0, 5).map(findingText).join('; ')}`, { cdsAudit: audit }),
          evidence: audit.violations.map(findingText).join('\n').slice(0, TAIL_CHARS),
        }
      }
      if (audit.gaps.length) {
        const upstream = audit.gaps.map((f) => ({ what: `cds: ${f.reason || f.value} (${f.file}:${f.line})` }))
        return {
          ...handback(false, 'blocked-upstream', `blocked-upstream: required cds configuration, design artifacts or capabilities remain unresolved: ${audit.gaps.map(findingText).join('; ')}`, { cdsAudit: audit, upstreamMissing: upstream }),
          upstreamMissing: upstream,
          evidence: audit.gaps.map(findingText).join('\n').slice(0, TAIL_CHARS),
        }
      }
    }

    enterPhase('Documentation')
    const docs = await workflow('agent-teams-workforce:documentation', { contract, green })
    if (docs && docs.ledger) runLedger.push(docs.ledger)

    enterPhase('Commit')
    finalRun = await runSuite('final')
    if (!validRun(finalRun) || finalRun.exitCode !== 0) {
      return handback(false, stageOf('commit', finalRun), `commit: the final suite run did not exit 0 (${(finalRun && (finalRun.summary || `exit ${finalRun.exitCode}`)) || 'no result'}), so nothing was committed`, { run: finalRun })
    }
    const committed = await workflow('agent-teams-workforce:settle', {
      repoPath: workRepoPath,
      commitOnly: true,
      branch: workspace.branch || null,
      defaultBranch: workspace.defaultBranch || null,
      message: `${bead.id} ${bead.title || ''}`.trim(),
    })
    if (!committed || committed.status !== 'reported' || (Array.isArray(committed.blocked) && committed.blocked.length)) {
      const why =
        (committed && (committed.error || committed.reason || (Array.isArray(committed.blocked) && committed.blocked.join('; ')))) ||
        'the commit step returned nothing'
      return handback(false, !committed || committed.status === 'error' ? DISPATCH_FAILED_STAGE : 'commit', `commit: ${why}`, { commit: committed || null })
    }

    return {
      ...handback(
        true,
        'committed',
        `${bead.id} built on ${workspace.branch}: \`${suiteCommand}\` exits 0${finalRun.summary ? ` (${finalRun.summary})` : ''} and the work is committed to the branch of Story ${story.id} (${committed.commit || 'no new commit'}).`,
        {
          contract,
          stashed: workspace.stashed || null,
          results: { intent, baseline, red, green, refactor, restored, documentation: docs, final: finalRun, commit: committed },
        }
      ),
      commit: committed.commit || null,
      suite: { command: suiteCommand, summary: finalRun.summary || '' },
    }
  })()
} catch (err) {
  const message = String((err && err.message) || err)
  const environmental = /overload|rate[ _-]?limit|too many requests|quota|capacity|session limit|usage limit|spend limit|credit balance|out of credits|timed? ?out|network/i.test(message)
  const where = currentPhase || 'unknown'
  const slug = String(where).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'unknown'
  log(`RUN ABORTED in ${where}: ${message.slice(0, 300)}`)
  result = handback(false, environmental ? DISPATCH_FAILED_STAGE : slug, `${where}: the run threw — ${message.slice(0, 300)}`, {
    reason: message.slice(0, 400),
    dispatchFailed: environmental,
  })
} finally {
  enterPhase('Run Ledger')
  const detailPath = persistRun(result && result.ok ? 'ok' : `failed:${(result && result.stage) || 'unknown'}`)
  if (result) result.detailPath = detailPath || null
}
return result
