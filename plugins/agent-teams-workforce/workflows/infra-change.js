export const meta = {
  name: 'infra-change',
  description:
    'Composite — provisions or changes infrastructure. Stitches the infra-intent front-end onto a TRIMMED shared build-and-ship tail (Red, Green, Integration, Adversarial, Deploy) via mini workflows, with an independent gate between phases and Documentation as a parallel track. The Refactor phase is omitted on the infra path. Adversarial runs a TRIMMED lane (infra-security + dependency-CVE + data-exposure only) and is optional/skipped by default. The script owns loop (retry-in-phase) and escalate (upstream) control flow; producing agents never judge their own work. Deploy DEPLOYS TO DEV and smoke-checks the deployed endpoints — that is how code reaches AWS and is not human-gated; only outward-facing qa/prod rollout is.',
  phases: [
    { title: 'Workspace', detail: 'establishes the linked worktree every writing phase then operates in' },
    { title: 'Infra Intent' },
    { title: 'Red' },
    { title: 'Green' },
    { title: 'Integration' },
    { title: 'Adversarial' },
    { title: 'Deploy-to-dev' },
    { title: 'Settle', detail: 'lands the work — commit, push, PR — on EVERY exit path; never evidence a work phase completed' },
    { title: 'Run Ledger', detail: 'telemetry — runs on EVERY exit path, including failure; never evidence the run succeeded' },
  ],
}

// args: {
//   bead: { id, title, description, repoPath },  // the infra change bead. repoPath is
//                                                 // REQUIRED and names the REPOSITORY; the
//                                                 // tree the phases write in comes from the
//                                                 // Workspace step, not from this value.
//   runAdversarial?: boolean,                     // run the TRIMMED adversarial lane (default false)
//   maxLoops?: number,                            // gate retry budget per phase (default 3)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const RUN_ADVERSARIAL = a.runAdversarial === true
// Gate retry budget. One rework round, then proceed with the finding recorded.
//
// This was 3, and nested minis carried their own bound of 2 on top, so a single
// phase could burn six expensive attempts before anyone saw a result — the
// dominant cost in every run that stalled. A checker's objection is information;
// it does not have to be a veto. One revision is where nearly all the value is:
// if a maker cannot address a finding on the second try, a third rarely helps and
// the finding is better carried forward than ground against.
//
// Callers who want the old behaviour pass args.maxLoops explicitly.
const MAX_LOOPS = a.maxLoops || 2
if (!bead.id) return { ok: false, stage: 'input', error: 'no bead.id supplied — refusing to run without a work item' }
// A code-writing composite with no repository cannot write anywhere it can later land
// from, and a run that proceeded blind then reported a phantom orphan at the end. Refuse
// at the input stage instead, the same way a missing bead.id is refused.
if (!String(bead.repoPath || '').trim()) {
  return { ok: false, stage: 'input', error: 'no bead.repoPath supplied — refusing to write code without a repository to establish a worktree in' }
}

// Decision ledger for over-time mining (see run-ledger-writer). Each instrumented
// mini returns a `ledger` on its artifact; collected here and persisted ONCE in a
// finally so it runs on success, early-return, and throw alike.//
// It gets its OWN phase, and that is load-bearing. This agent used to be tagged
// `phase: 'Deploy-to-dev'`, and because the finally runs on every exit path, a
// run that died at an early gate still ticked the terminal phase green — the
// progress panel reported a deploy for a run that never built anything.
// Telemetry must never be able to paint a work phase complete, so it reports
// under a phase that claims nothing about the work.
const runLedger = []
async function persistRun(outcome) {
  if (!runLedger.length) return
  try {
    await agent(
      `Persist this SDLC workflow run's decision ledger. JSON payload:\n${JSON.stringify({ composite: 'infra-change', bead: { id: bead.id || null, title: bead.title || null }, outcome, runLedger })}`,
      {
        label: 'ledger:persist',
        phase: 'Run Ledger',
        agentType: 'agent-teams-workforce:run-ledger-writer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['written'],
          properties: {
            written: { type: 'boolean' },
            path: { type: 'string' },
            lines: { type: 'number' },
            runId: { type: 'string' },
          },
        },
      }
    )
  } catch (e) {
    log(`ledger persist failed (non-fatal): ${e && e.message ? e.message : e}`)
  }
}

// The worktree the settle step lands. `contract.repoPath` is built inside the run's
// async body and is out of scope in the `finally`, so the resolved path is captured
// on this mutable as the run establishes it.
// It starts NULL, not `bead.repoPath`. The caller-supplied path is the repository, and
// settle COMMITS in whatever it is handed: seeding it with the caller's repo meant a run
// that died before or inside the workspace step sent settle into the MAIN working tree
// to commit there. Nothing writes before the workspace step, so until that step verifies
// a tree there is genuinely nothing to land.
let settleRepoPath = null
// What the workspace step VERIFIED about that tree. Settle re-checks both before it is
// willing to commit — see the guard in settleRun.
let settleBranch = null
let settleIsLinkedWorktree = false
// THIS repository's default branch, as the workspace step's independent check read it
// from origin/HEAD. A repo whose default is `develop` or `trunk` was completely
// unprotected while the hardcoded pair below was the only test. Null means the ref was
// unobtainable, which narrows the guard back to the floor rather than widening it to a
// guess.
let settleDefaultBranch = null
// A FLOOR, never the whole test. `main` and `master` are refused in every repository
// because they are the fleet convention; the repository's actual default is refused as
// well, and it is read, not assumed.
const SETTLE_DEFAULT_BRANCHES = new Set(['main', 'master'])
const settleNormalizeBranch = (b) =>
  String(b || '')
    .trim()
    .replace(/^refs\/heads\//, '')
    .replace(/^origin\//, '')
    .toLowerCase()

// ── PATH SAFETY: the worktree path is COMMAND TEXT in the settle prompt ───────
//
// settle interpolates the path verbatim into `git -C "<path>"` lines and into a
// `cd "<path>" && skillspoke-pr ...` line, and the agent that receives that prompt is told
// to run those commands exactly as written. A path carrying a double quote closes the
// quoting; a backtick, a dollar sign, a semicolon or a pipe appends commands of the path
// author's choosing to a shell that then COMMITS AND PUSHES. The path travels here from
// the workspace step, which is the one place it is validated at the source — so it is
// re-checked here rather than trusted, because settle is the step that acts irreversibly.
//
// REFUSE, never sanitize: a rewritten path names a different tree, and settle would commit
// in it without anyone learning of the substitution. Absolute is required because a
// relative path resolves against whatever directory the agent is standing in.
const SETTLE_UNSAFE_IN_COMMAND_TEXT = /[`'"\\$;&|<>(){}[\]*?!#~\u0000-\u001f\u007f]/
const settlePathFault = (p) => {
  const v = String(p == null ? '' : p)
  if (!v.trim()) return 'it is empty'
  if (!v.startsWith('/')) return `${JSON.stringify(v)} is not an absolute path, and every settle command runs as \`git -C "<path>"\``
  const bad = v.match(SETTLE_UNSAFE_IN_COMMAND_TEXT)
  if (bad) {
    return (
      `${JSON.stringify(v)} contains ${JSON.stringify(bad[0])}, which would change the SHAPE of the commands ` +
      'the settle agent is told to run verbatim rather than merely name a directory'
    )
  }
  return null
}

// ── Settle: land the work, or name what stopped it ────────────────────────────
// The telemetry `finally` below is the ONE construct that observes every exit path —
// every failure return and the success return alike. Persisting a ledger there while
// the change sat unlanded in a worktree is how finished work went missing: no mini in
// this pipeline touches git before the deploy mini's ship step, so a run that dies at
// Integration or Adversarial leaves the work UNCOMMITTED — not merely unpushed, but
// with no commit to find later. This lands it or reports exactly why it could not be
// landed, and it can never report success over an orphan.
//
// It gets its OWN phase for the same reason the ledger does: running on every exit
// path, it must never be able to tick a work phase green.
// Three worlds, three answers. A run with no repo path, a settle agent that threw, and a
// genuine orphan used to be indistinguishable — all three returned null, and the first two
// then flipped a successful run to ok:false and blamed a PR URL that was never withheld
// because the agent never ran.
async function settleRun() {
  const wt = settleRepoPath
  if (!wt) return { status: 'not-applicable', reason: 'the run established no repo path, so nothing was written through the contract' }
  // Before the path becomes command text in the prompt below. A path that could reshape
  // those commands is a blocked orphan: the work is named and left where a human can find
  // it, never committed by a shell somebody else wrote.
  const wtFault = settlePathFault(wt)
  if (wtFault) {
    return {
      status: 'blocked',
      reason:
        `settle refused to act on the worktree path it was handed because ${wtFault}. The path is ` +
        'interpolated into git and skillspoke-pr commands another agent runs exactly as written, so it ' +
        'is refused rather than rewritten.',
    }
  }
  // Settle COMMITS, and then opens a PR on the CURRENT branch. Both are irreversible in
  // the way that matters: the original incident left work uncommitted on main and
  // therefore recoverable, whereas an unguarded settle in that same tree would have
  // COMMITTED it onto main. So the tree settle is about to act in must still be the
  // verified linked worktree the workspace step established, on a branch that is not the
  // default one. An unverified tree is refused and reported as a blocked orphan — the
  // work is named and left where a human can find it, never committed to find out.
  const settleNormalized = settleNormalizeBranch(settleBranch || '')
  if (settleIsLinkedWorktree !== true) {
    return {
      status: 'blocked',
      reason:
        `settle refused to commit in ${wt}: the workspace step did not affirm it is a linked worktree ` +
        '(isLinkedWorktree=true). Committing into an unverified tree is how a fix lands on main.',
    }
  }
  const settleRepoDefault = settleNormalizeBranch(settleDefaultBranch || '')
  if (
    !settleNormalized ||
    SETTLE_DEFAULT_BRANCHES.has(settleNormalized) ||
    settleNormalized === 'head' ||
    (settleRepoDefault && settleNormalized === settleRepoDefault)
  ) {
    return {
      status: 'blocked',
      reason:
        `settle refused to commit in ${wt}: its branch is "${settleBranch || '(none reported)'}" — a default ` +
        'branch, a detached HEAD, or unreported. skillspoke-pr runs on the CURRENT branch, so this would ' +
        'commit and push the work onto the default branch rather than onto a reviewable branch.' +
        (settleRepoDefault && settleNormalized === settleRepoDefault
          ? ` This repository's default branch is "${settleDefaultBranch}", as origin/HEAD names it — not every repo defaults to main.`
          : ''),
    }
  }
  try {
    const reported = await agent(
      `Land every change in this worktree, or say exactly why it could not be landed. Worktree: ${wt}\n` +
        `Run every git command as \`git -C "${wt}"\`, and \`cd "${wt}"\` before skillspoke-pr — it has no -C flag and must run inside the tree.\n` +
        `1. \`git -C "${wt}" status --porcelain\`. Commit anything uncommitted as \`type(scope): description\` with NO Co-Authored-By header. Run the repo's gates first. \`--no-verify\` is forbidden in every form; if a hook finding cannot be fixed, abort with NO commit and name it in \`blocked\` — that is the only sanctioned way work stays local.\n` +
        `2. If \`git -C "${wt}" rev-parse --abbrev-ref --symbolic-full-name @{u}\` resolves to origin/main, run \`git -C "${wt}" branch --unset-upstream\`. Never push to main.\n` +
        `3. Report \`hasWork\`: true if the tree was dirty or the branch has commits not reachable from origin/main.\n` +
        `4. If hasWork, \`cd "${wt}" && /Users/msat1971/.local/bin/skillspoke-pr --title "<type(scope): description>" --body "<what changed and why>"\`. It pushes the branch itself. NEVER open the PR any other way — CodeRabbit does not scan PRs opened under an agent token, so the raw \`gh\` PR-create path yields an unreviewed PR. NEVER \`gh pr merge\`. If a PR already exists for this head skillspoke-pr returns that PR's URL — success, not failure.\n` +
        `5. Report the literal PR URL, the branch, and whether the tree is clean.`,
      {
        label: 'settle:land-work',
        phase: 'Settle',
        agentType: 'agent-teams-workforce:github-actions-pipeline-implementer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['treeClean', 'hasWork', 'branch', 'prUrl'],
          properties: {
            treeClean: { type: 'boolean' },
            hasWork: { type: 'boolean' },
            branch: { type: 'string' },
            prUrl: { type: 'string' },
            blocked: { type: 'array', items: { type: 'string' } },
          },
        },
      }
    )
    if (!reported) return { status: 'error', error: 'the settle agent returned no result' }
    return { status: 'reported', ...reported }
  } catch (e) {
    const error = e && e.message ? e.message : String(e)
    log(`settle failed: ${error}`)
    return { status: 'error', error }
  }
}

// Translate a settle report into the run's landing verdict. Three worlds:
//   not-applicable — no repo path was ever established, so nothing could be written
//                    through the contract and nothing can be orphaned. It does NOT
//                    touch result.ok; forcing a successful run to false here reported
//                    failure over correct work and taught the operator to disbelieve
//                    the orphan signal that exists to be believed.
//   error          — the settle agent threw or returned nothing. The run is unlanded,
//                    but say WHY, and never claim a URL was withheld by an agent that
//                    never ran.
//   reported       — the only world in which "orphaned" is an honest word.
function applySettle(res, settle) {
  const status = (settle && settle.status) || 'error'
  if (status === 'not-applicable') {
    res.landed = false
    res.settled = 'not-applicable'
    res.settleNote = (settle && settle.reason) || 'no repo path was established'
    log(`Settle: not applicable — ${res.settleNote}`)
    return
  }
  if (status === 'error') {
    res.landed = false
    res.ok = false
    res.settleFailed = { error: (settle && settle.error) || 'the settle step failed without an error message' }
    return
  }
  // blocked — settle declined to commit because the tree it was pointed at was not the
  // verified worktree. That IS an orphan: the work exists and was not landed. Saying so
  // is the whole point; proceeding would have committed onto the default branch.
  if (status === 'blocked') {
    res.landed = false
    res.ok = false
    res.settled = 'blocked'
    res.orphaned = {
      worktree: settleRepoPath,
      branch: settleBranch || null,
      blocked: [(settle && settle.reason) || 'settle refused to commit into an unverified tree'],
    }
    log(`Settle: REFUSED — ${(settle && settle.reason) || 'unverified tree'}`)
    return
  }
  const PR_OK = /^https:\/\/github\.com\/[^/]+\/[^/]+\/pull\/\d+$/.test(String(settle.prUrl || '').trim())
  const landed = settle.treeClean === true && (settle.hasWork === false || PR_OK)
  res.landed = landed
  res.prUrl = PR_OK ? String(settle.prUrl).trim() : null
  res.settled = 'reported'
  if (!landed) {
    res.ok = false
    res.orphaned = {
      worktree: settleRepoPath,
      branch: settle.branch || null,
      blocked: (settle.blocked && settle.blocked.length ? settle.blocked : null) || ['settle returned no verifiable PR URL'],
    }
  }
}

// Every adjudication goes to the ledger. Without the verdict and its per-criterion
// evidence, a run that stops at a gate records only `failed:<phase>` — which cannot
// distinguish a genuine defect from an over-strict criterion or a loop exhaustion.
// Module-scoped here (not nested in gateLoop) because this pipeline also has a
// standalone G1 gate call that must be recorded the same way.
function recordGate(gate, phaseName, attempt, verdict, extra) {
  return runLedger.push({
    phase: `gate:${gate}`,
    gate,
    gatePhase: phaseName,
    attempt,
    maxLoops: MAX_LOOPS,
    verdict: (verdict && verdict.verdict) || 'no-verdict',
    criteria: ((verdict && verdict.criteria) || []).map((c) => ({
      criterion: c.criterion,
      met: c.met,
      evidence: c.evidence,
    })),
    unmetCriteria: ((verdict && verdict.criteria) || [])
      .filter((c) => !c.met)
      .map((c) => c.criterion),
    feedback: (verdict && verdict.feedback) || null,
    escalateTo: (verdict && verdict.escalateTo) || null,
    flags: (verdict && verdict.flags) || [],
    ...(extra || {}),
  })
}

// Run a phase, judge it at an INDEPENDENT gate, apply the verdict.
async function gateLoop({ gate, phaseName, criteria, checks, escalateTargets, phaseFn, gateWorkflow, initialFeedback }) {
  // Seed EVERY attempt with findings already known from a previous run. Without this a
  // re-dispatch after a gate failure starts blind and must spend a full expensive attempt
  // rediscovering what the prior gate already proved — which on infra-intent is the single
  // costliest thing this pipeline does. The seed is a persistent channel, not an initial
  // value: a later gate verdict replaces only the per-attempt gate feedback, never the seed.
  const seed = initialFeedback || ''
  let gateFeedback = ''
  let artifact
  // Carried across attempts so loop exhaustion can say WHAT was unmet and on what
  // evidence, instead of a bare count. Both are computed at every attempt already;
  // the exhaustion path simply never saw them.
  let lastVerdict = null
  const attempts = []
  for (let attempt = 1; attempt <= MAX_LOOPS; attempt++) {
    // Announce the START of the attempt. The progress panel cannot tick this phase:
    // its work happens inside a nested workflow(), whose agents the engine puts in
    // their own "▸ <mini>" group rather than counting toward the parent phase. So
    // without this line a phase that is actively running reads as "Not started yet",
    // and only its verdict — logged below, after the fact — ever proves it ran.
    log(`Gate ${gate} (${phaseName}): running attempt ${attempt}/${MAX_LOOPS}`)
    const feedback = [seed, gateFeedback].filter(Boolean).join('\n')
    // The second argument is the STRUCTURED loop channel. A free-text string cannot
    // carry which criteria were unmet, nor what the phase produced last time — and a
    // phase re-judged with no memory of the prior round regenerates the prior round's
    // contradiction. Existing call sites that take only `feedback` are unaffected.
    const priorArtifact = artifact
    artifact = await phaseFn(feedback, {
      attempt,
      maxLoops: MAX_LOOPS,
      feedback,
      priorArtifact,
      priorVerdicts: attempts.map((x) => x.verdict).filter(Boolean),
      unmetCriteria: lastVerdict ? ((lastVerdict.criteria || []).filter((cc) => !cc.met).map((cc) => ({ criterion: cc.criterion, evidence: cc.evidence }))) : [],
    })
    // A phase may report that its work was ALREADY DONE — Red finding the contract
    // satisfied by passing tests, for instance. There is nothing for the gate to
    // judge and no rework that could change the answer, so gating it would fail a
    // criterion nothing can meet and burn the entire loop budget proving it.
    if (artifact && artifact.alreadySatisfied === true) {
      log(`${phaseName}: ALREADY SATISFIED — nothing to build; gate ${gate} skipped`)
      return { ok: true, artifact, alreadySatisfied: true }
    }
    const verdict = await workflow(gateWorkflow || 'agent-teams-workforce:gate-enforce', {
      gate, phaseName, criteria, checks, artifact, escalateTargets,
    })
    if (!verdict) {
      recordGate(gate, phaseName, attempt, null, { terminal: 'no-verdict' })
      return { ok: false, reason: `gate ${gate} returned no verdict`, artifact }
    }
    recordGate(gate, phaseName, attempt, verdict)
    lastVerdict = verdict
    attempts.push({
      attempt,
      verdict,
      feedback: verdict.feedback || null,
      unmetCriteria: (verdict.criteria || []).filter((cc) => !cc.met).map((cc) => ({ criterion: cc.criterion, evidence: cc.evidence })),
    })
    if (verdict.verdict === 'pass') {
      log(`Gate ${gate} (${phaseName}): PASS${verdict.flags && verdict.flags.length ? ` — flags: ${verdict.flags.join('; ')}` : ''}`)
      return { ok: true, artifact, verdict }
    }
    if (verdict.verdict === 'escalate') {
      log(`Gate ${gate} (${phaseName}): ESCALATE -> ${verdict.escalateTo || 'upstream'}`)
      return { ok: false, escalate: verdict.escalateTo || 'upstream', artifact, verdict }
    }
    log(`Gate ${gate} (${phaseName}): LOOP ${attempt}/${MAX_LOOPS} — ${verdict.feedback}`)
    gateFeedback = verdict.feedback || ''
  }
  // Record the REAL final verdict, not null. A terminal ledger row with `criteria: []`
  // cannot distinguish a genuine defect from an over-strict criterion — which is the one
  // question anyone asks about an exhausted gate.
  recordGate(gate, phaseName, MAX_LOOPS, lastVerdict, { verdict: 'loop-exhausted', terminal: 'loop-exhausted' })
  // Carry the last-authored artifact like every other non-ok exit does — loop exhaustion
  // is exactly where the caller most needs the final intent for diagnosis.
  return {
    ok: false,
    reason: `gate ${gate} exceeded ${MAX_LOOPS} loops`,
    loopExhausted: true,
    artifact,
    verdict: lastVerdict,
    unmetCriteria: lastVerdict ? (lastVerdict.criteria || []).filter((cc) => !cc.met).map((cc) => ({ criterion: cc.criterion, evidence: cc.evidence })) : [],
    attempts,
  }
}

// ── Front-end: infrastructure provisioning intent ───────────────────────────────
let result
try {
  result = await (async () => {
// ── Workspace: establish the tree every writing phase then operates in ─────────
// This is the structural mirror of the settle step above: settle LANDS the tree on
// every exit path, workspace ESTABLISHES it before the first write. Nothing else in
// this pipeline creates one, so without this step every writing phase edits whatever
// tree the caller pointed at — which twice meant `main` in a main working tree, the
// one place the project's own rules forbid, with no branch for settle to push.
phase('Workspace')
const workspace = await workflow('agent-teams-workforce:workspace', {
  repoPath: bead.repoPath,
  beadId: bead.id,
  branchPrefix: 'infra',
  purpose: bead.title || 'infra change',
})
// RESIDUAL 5 — the writing phases get the same backstop settle already had.
// `ok === true && repoPath` accepts a 6.0.5-shaped result: a version skew, a bypassed or
// stale plugin cache, or any workspace mini that never ran the independent check returns
// exactly that shape, and tdd-red, tdd-green and tdd-refactor would each receive whatever
// path it carried while only settle refused. The phases that WRITE deserve the guard the
// phase that commits already has, so the shape is validated here: the tree must be
// affirmatively verified, not merely reported.
const workspaceShapeFault = !workspace
  ? 'the workspace step returned nothing'
  : workspace.ok !== true
    ? 'the workspace step did not report ok=true'
    : !workspace.repoPath
      ? 'the workspace step reported no repoPath'
      : workspace.isLinkedWorktree !== true
        ? 'the workspace step did not affirm isLinkedWorktree=true'
        : workspace.independentlyVerified !== true
          ? 'the workspace step carries no independent verification of the tree (independentlyVerified !== true) — ' +
            'this is the shape a pre-6.0.7 workspace mini returns, so the result may come from a stale or ' +
            'bypassed plugin cache'
          : !String(workspace.branch || '').trim()
            ? 'the workspace step named no branch'
            : null
if (workspaceShapeFault) {
  return {
    ok: false,
    stage: 'workspace',
    workspaceShapeFault,
    bead: bead.id,
    reason: `no verified worktree was established (${workspaceShapeFault}) — refusing to write into the tree the caller pointed at`,
    detail: workspace || null,
  }
}
// THE tree, from here on. Not the caller's path: the caller supplies a repository,
// this step supplies the worktree, and every downstream phase inherits THIS value.
const workRepoPath = workspace.repoPath
settleRepoPath = workRepoPath
// Carry the workspace step's VERIFIED facts, not an assumption, to the settle guard.
// Absent fields stay falsy on purpose: settle then refuses rather than committing on a
// claim nobody made.
settleBranch = workspace.branch || null
settleIsLinkedWorktree = workspace.isLinkedWorktree === true
// Read, never assumed: null here narrows the settle guard to its hardcoded floor.
settleDefaultBranch = workspace.defaultBranch || null
if (workspace.ledger) runLedger.push(workspace.ledger)

phase('Infra Intent')
log(`Infra change ${bead.id || '(no id)'} — ${bead.title || ''}`)
// ── Gate 1: Infra Intent (provisioning contract is concrete + fresh + clean) ─────
// G1 USED TO BE A STANDALONE GATE THAT COULD NOT LOOP. It called gate-enforce once and
// returned on anything but 'pass' — so a verdict of 'loop', which means "retry this phase
// with my feedback", ended the run instead. This is the same defect class as ssbd-wmtw
// (escalation as a labelled exit rather than control flow), which was repaired for the
// Red/Green pair but never here.
// It is expensive precisely because infra-intent is expensive. On ssbd-w1r9 the gate
// returned 'loop' with a detailed, reproducible feedback packet naming exactly what the
// maker had to change — and the run died anyway, 486k subagent tokens spent, the feedback
// salvageable only by hand. Route it through gateLoop so the maker re-authors against the
// gate's own findings, bounded by MAX_LOOPS.
const g1Loop = await gateLoop({
  gate: 'G1',
  phaseName: 'Infra Intent',
  criteria: [
    'Provisioning intent is concrete and CDK-expressible (S3 versioning+SSE-S3 where buckets exist, no banned constructs)',
    'No dependency change invalidates the intent',
    'Security and cost reviewers raised no open blocking finding',
  ],
  escalateTargets: ['infra-intent'],
  initialFeedback: a.priorFindings || '',
  phaseFn: (feedback) =>
    workflow('agent-teams-workforce:infra-intent', {
      change: { id: bead.id, title: bead.title, description: bead.description, repoPath: workRepoPath },
      feedback,
    }),
})
if (!g1Loop.ok) {
  return { ok: false, stage: 'infra-intent', bead: bead.id, gate: 'G1', detail: g1Loop, intent: g1Loop.artifact }
}
const intent = g1Loop.artifact
if (!intent) return { ok: false, stage: 'infra-intent', reason: 'infra-intent produced nothing' }

// Tail-facing contract: carries the repo + a change descriptor the tail prompts
// render, plus the provisioning intent and the infra assertion the Red test encodes.
const tailContract = {
  bead: { id: bead.id, title: bead.title || 'infra change' },
  repoPath: workRepoPath,
  affectedStacks: intent.affectedStacks || [],
  provisioningIntent: intent.provisioningIntent || null,
  // Infra is verified by synth assertions, not by specialist surface writers. The
  // empty list is a positive statement — unit/synth coverage only — not an omission.
  surfaces: [],
  testStrategy: null,
  acceptanceCriteria: [
    {
      given: `the provisioning intent for ${bead.title || 'this infra change'} on stacks ${(intent.affectedStacks || []).join(', ') || '(affected stacks)'}`,
      when: 'cdk synth runs against the changed stacks',
      then: 'the synthesized template asserts the intended resources/properties (incl. S3 versioning + SSE-S3 where buckets exist) and no banned constructs are present',
    },
  ],
}
// tailContract.repoPath IS the workspace step's return value; nothing downstream may
// substitute the caller's path for it.
settleRepoPath = tailContract.repoPath

// ── Red (Gate 2a) — author the FAILING infra synth/policy assertion ──────────────
phase('Red')
const red = await gateLoop({
  gate: '2a', phaseName: 'TDD Red',
  criteria: [
    'Tests assert against freshly generated artifacts, not checked-in build output (a test reading a committed cdk.out template or similar passes forever regardless of the code)',
    'A failing infra test/synth assertion encodes the provisioning intent',
    'The assertion fails for the intended reason (the intent is not yet expressed in CDK)',
    'No production CDK code changed yet — tests/assertions only',
  ],
  checks: [
    { field: 'redConfirmed', equals: true, label: 'the phase reports Red confirmed' },
    { field: 'evidence', nonEmpty: true, label: 'executed failing output was captured as evidence' },
    // Red proves an assertion fails NOW. It must also establish that a pass is
    // REACHABLE — an assertion pinned to a stack or path the change does not touch
    // fails correctly and can never go green (ssbd-vtnl).
    { field: 'greenReachable', equals: true, label: 'every authored assertion names the CDK file whose change makes it pass' },
  ],
  escalateTargets: ['infra-intent'],
  // From attempt 2 the previous attempt's test is ON DISK. Discovery would re-find it,
  // report no gaps, and the confirm-existing branch would hand the gate back the very
  // test it just rejected — through a code path the gate's objection never reaches.
  // A re-run after a rejection authors; it does not shop for what it already wrote.
  phaseFn: (feedback, loop) => workflow('agent-teams-workforce:tdd-red', { contract: tailContract, feedback, skipDiscovery: !!(loop && loop.attempt > 1) }),
})
if (red.artifact && red.artifact.ledger) runLedger.push(red.artifact.ledger)
if (!red.ok) return { ok: false, stage: 'red', bead: bead.id, detail: red }
// Red found the provisioning intent already asserted by PASSING checks: the infra
// already expresses it. Green would be asked to make a failing assertion pass when
// none fails, so the run ends here — successfully, with nothing changed.
if (red.alreadySatisfied) {
  return {
    ok: true, stage: 'red', bead: bead.id, alreadySatisfied: true, built: false,
    reason: 'the provisioning intent is already expressed and asserted by passing checks — no Red is obtainable and nothing was authored or changed',
    detail: red.artifact,
  }
}

// ── Green (Gate 2b) — make synth/test pass via the CDK stack author ──────────────
phase('Green')
const green = await gateLoop({
  gate: 'G2b', phaseName: 'TDD Green',
  criteria: [
    'The previously-failing infra test/synth assertion now passes',
    'No other stacks regressed',
    'cdk synth succeeds with the change',
  ],
  escalateTargets: ['infra-intent', 'red'],
  phaseFn: (feedback) =>
    workflow('agent-teams-workforce:tdd-green', { contract: tailContract, red: red.artifact, implementer: 'cdk-stack-author', feedback }),
})
if (green.artifact && green.artifact.ledger) runLedger.push(green.artifact.ledger)
if (!green.ok) return { ok: false, stage: 'green', bead: bead.id, detail: green }

// Documentation runs ALONGSIDE the rest of the tail (started after Green, awaited before deploy).
const docTrack = workflow('agent-teams-workforce:documentation', { contract: tailContract, green: green.artifact })

// Settle the parallel documentation track before any early failure return, so a
// failed run never leaves docTrack as an unhandled rejection or orphaned work.
async function failAfterDoc(stage, detail) {
  await Promise.allSettled([docTrack])
  return { ok: false, stage, bead: bead.id, detail }
}

// ── Integration (Gate 3) — infra contract/drift checks across stacks ─────────────
phase('Integration')
const integration = await gateLoop({
  gate: 'G3', phaseName: 'Integration Testing',
  criteria: [
    'Infra integration/contract checks pass',
    'No drift introduced across stacks',
    'Cross-stack SSM references resolve (no CloudFormation exports)',
  ],
  escalateTargets: ['green', 'red', 'infra-intent'],
  // Infra declares surfaces: [] because it needs no specialist TEST WRITERS, but it
  // absolutely needs integration verification — a provisioned stack has to be exercised.
  // Naming the suite explicitly stops the surface-derived selection from reading that
  // empty list as "no integration applies" and skipping the phase.
  phaseFn: (feedback) => workflow('agent-teams-workforce:integration', { contract: tailContract, green: green.artifact, suites: ['aws-integration-test-runner'], feedback }),
})
if (integration.artifact && integration.artifact.ledger) runLedger.push(integration.artifact.ledger)
if (!integration.ok) return await failAfterDoc('integration', integration)

// ── Adversarial (Gate 4 — constitutional) — TRIMMED lane, optional ───────────────
// Trimmed to infra-relevant attack classes; full attack lanes are skipped by
// default. Security findings are constitutive — judged at a constitutional gate.
let adversarial = { skipped: true }
if (RUN_ADVERSARIAL) {
  phase('Adversarial')
  const adv = await gateLoop({
    gate: 'G4', phaseName: 'Adversarial Validation', gateWorkflow: 'agent-teams-workforce:gate-constitutional',
    criteria: [
      'No open constitutive findings (no infra misconfiguration, unpatched CVE, or data exposure)',
      'All confirmed findings adjudicated',
    ],
    escalateTargets: ['green', 'infra-intent'],
    // priorRulings is what makes a re-run adjudication accountable to the one before
    // it. Without it the adjudicator is a fresh instance every round with no knowledge
    // that it ever ruled — it is not reversing a ruling, it has never been shown one.
    phaseFn: (feedback, loop) =>
      workflow('agent-teams-workforce:adversarial', {
        contract: tailContract,
        green: green.artifact,
        trimmedScope: ['infrastructure-security-scanner', 'dependency-cve-auditor', 'data-exposure-scanner'],
        feedback,
        priorRulings: (loop && loop.priorArtifact && loop.priorArtifact.adjudication && loop.priorArtifact.adjudication.rulings) || [],
      }),
  })
  if (!adv.ok) return await failAfterDoc('adversarial', adv)
  adversarial = adv.artifact
} else {
  log('Adversarial lane skipped (runAdversarial=false) — trimmed infra path')
}

// Documentation must be current before the deploy.
const docCurrency = await docTrack
if (docCurrency && docCurrency.ledger) runLedger.push(docCurrency.ledger)

// ── Deploy to dev (Gate 5) — dev IS deployed; only qa/prod is human-gated ───────
// Deploying to dev is how infrastructure reaches AWS and is part of the
// development lifecycle, not a release. A stack cannot be validated against AWS
// until it is IN AWS. Outward-facing qa/prod rollout never happens here.
phase('Deploy-to-dev')
const deployReady = await gateLoop({
  gate: 'G5', phaseName: 'Deploy to dev',
  criteria: [
    'CDK synth valid, no unresolved drift',
    'Smoke tests present',
    'Deployed to the dev environment',
    'Smoke tests pass against the deployed dev endpoints',
  ],
  checks: [
    { field: 'prOpened', equals: true, label: 'a pull request was opened for this work' },
    { field: 'prUrl', nonEmpty: true, label: 'the PR URL was reported' },
  ],
  escalateTargets: ['integration', 'green'],
  phaseFn: (feedback) => workflow('agent-teams-workforce:deploy', { contract: tailContract, green: green.artifact, docCurrency, feedback }),
})
if (deployReady.artifact && deployReady.artifact.ledger) runLedger.push(deployReady.artifact.ledger)
if (!deployReady.ok) return { ok: false, stage: 'deploy-to-dev', bead: bead.id, detail: deployReady }

return {
  ok: true,
  bead: bead.id,
  stagesComplete: [
    'infra-intent',
    'red',
    'green',
    'integration',
    ...(RUN_ADVERSARIAL ? ['adversarial'] : []),
    'deploy-to-dev',
  ],
  adversarialRun: RUN_ADVERSARIAL,
  note: 'DEPLOYED TO DEV and smoke-checked against the deployed endpoints. Outward-facing qa/prod rollout is a separate human-gated action and did not happen here. Refactor phase is omitted on the infra path.',
  contract: tailContract,
  results: {
    intent,
    red: red.artifact,
    green: green.artifact,
    integration: integration.artifact,
    adversarial,
    deployReadiness: deployReady.artifact,
    documentation: docCurrency,
  },
}
  })()
} finally {
  await persistRun(result && result.ok ? 'ok' : `failed:${(result && result.stage) || 'unknown'}`)
  const settle = await settleRun()
  if (result) applySettle(result, settle)
}
return result
