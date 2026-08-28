// The repo span is an OUTPUT of the run, ruled by architecture — not caller input.
//
// It used to arrive as `args.repos`, defaulting to `[repoPath]`, computed at module scope
// before a single phase had run. Nothing in the pipeline ever decided it, so a PRD that
// genuinely spanned three repositories produced ONE Story in whichever repository the
// caller happened to be standing in, and the other two repositories' worth of work was
// specified nowhere. Nothing said so: a wrongly-narrowed span and a correctly-scoped
// single-repo PRD are indistinguishable once the run is under way.
//
// It cannot be supplied because it cannot be KNOWN in advance — the span is a property of
// the delta (work no repository contains yet) and of the design ruled for it, and both are
// outputs of the same run. It equally must not be pre-staged into a file: a stored span is
// an answer computed against a PRD that has since been adjusted, and a re-run that reads
// one succeeds against the wrong repositories, silently.
//
// These tests pin the three things that make that true: the greenfield firewall (the
// shaper never sees what exists), the refusal to fall back to the launch repository, and
// the fact that a repository the project does not have is RETURNED, never created.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, agentCalls, workflowCalls, journalPayload } from './helpers/run-workflow.mjs'
import { beadWriter } from './helpers/bead-writer.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const WF = path.resolve(HERE, '..', '..', 'workflows')
const SCOPING = path.join(WF, 'repo-scoping.js')
const PRD_TO_SPEC = path.join(WF, 'prd-to-spec.js')

const PRD = { id: 'PRD-1', title: 'PRD One', body: 'the delta requirements' }

/** A shaper/surveyor/decider/verifier fixture that agrees on one repository. */
function scopingAgents({ placements, newRepos = [], inventory, verified = true } = {}) {
  const repos = placements || [{ repoPath: '/repos/alpha', repoName: 'alpha', workUnitIds: ['W1'], rationale: 'owns it' }]
  const inv = inventory || repos.map((p) => ({ repoPath: p.repoPath, name: p.repoName, owns: 'the capability' }))
  return (call) => {
    if (call.label === 'scope:greenfield-shape') {
      return {
        workUnits: [{ id: 'W1', summary: 'build the thing', homeKind: 'service', boundaryRationale: 'own context' }],
        designSummary: 'one service',
      }
    }
    if (call.label === 'scope:repository-survey') return { repositories: inv, surveySummary: `${inv.length} repos` }
    if (call.label === 'scope:rule-span') return { placements: repos, newRepos, reclassified: [], spanRationale: 'ruled' }
    if (call.label === 'scope:verify-span') {
      return { results: repos.map((p) => ({ repoPath: p.repoPath, exists: verified, evidence: 'checked' })) }
    }
    return null
  }
}

// ── The greenfield firewall ────────────────────────────────────────────────────

test('the greenfield shaper is told NOTHING about which repositories exist', async () => {
  // The whole ordering rests on this. Show a model a repository that already does
  // something adjacent and it reasons backwards from it, producing a rationalization of
  // the status quo wearing the vocabulary of a design. The firewall is the prompt.
  const { calls } = await runWorkflowScript(SCOPING, {
    args: {
      prd: PRD,
      seedRepos: ['/repos/where-the-human-stood'],
      reconciliation: { sizing: { deltaRepos: ['/repos/where-the-code-already-is'] } },
    },
    agentImpl: scopingAgents(),
  })

  const [shaper] = agentCalls(calls, 'scope:greenfield-shape')
  assert.ok(shaper, 'the shaper must run')
  assert.ok(
    !shaper.prompt.includes('/repos/where-the-code-already-is'),
    'deltaRepos is the single most biasing input there is — it names where the EXISTING work lives, ' +
      'and it must not reach the step whose whole job is to ignore what exists',
  )
  assert.ok(
    !shaper.prompt.includes('/repos/where-the-human-stood'),
    'the launch repository carries no authority and must not be shown to the shaper either',
  )
})

test('the existing-code evidence DOES reach the ruling step — the firewall is ordering, not censorship', async () => {
  // The other half. Withholding deltaRepos from the decider too would make the ruling
  // blind to what exists, which is a different defect: recognizing existing repositories
  // is step 2 of the ordering and the whole point of the ruling step.
  const { calls } = await runWorkflowScript(SCOPING, {
    args: { prd: PRD, seedRepos: ['/repos/alpha'], reconciliation: { sizing: { deltaRepos: ['/repos/where-the-code-already-is'] } } },
    agentImpl: scopingAgents(),
  })

  const [decider] = agentCalls(calls, 'scope:rule-span')
  assert.ok(decider.prompt.includes('/repos/where-the-code-already-is'), 'the ruling step must see the evidence')
})

test('the shaper and the surveyor run CONCURRENTLY, so neither can influence the other', async () => {
  const { calls } = await runWorkflowScript(SCOPING, { args: { prd: PRD }, agentImpl: scopingAgents() })
  const labels = calls.filter((c) => c.kind === 'agent').map((c) => c.label)
  assert.deepEqual(
    labels,
    ['scope:greenfield-shape', 'scope:repository-survey', 'scope:rule-span', 'scope:verify-span'],
    'shape and survey are one parallel pair, then the ruling, then an independent verification',
  )
})

// ── Segregation of duties ──────────────────────────────────────────────────────

test('whoever rules the span does not verify its own ruling', async () => {
  const { calls } = await runWorkflowScript(SCOPING, { args: { prd: PRD }, agentImpl: scopingAgents() })
  const [decider] = agentCalls(calls, 'scope:rule-span')
  const [verifier] = agentCalls(calls, 'scope:verify-span')
  assert.notEqual(
    decider.opts.agentType,
    verifier.opts.agentType,
    'a decider that verifies its own placement confirms it every time',
  )
  assert.ok(
    !verifier.prompt.includes('owns it'),
    'the verifier is given paths and nothing else — told the rationale it grades the argument instead of ' +
      'reporting the one thing that is actually checkable',
  )
})

// ── The reduction is where the enforcement lives ───────────────────────────────

test('a repository the verifier could not confirm is DROPPED from the span, not argued with', async () => {
  const { result } = await runWorkflowScript(SCOPING, {
    args: { prd: PRD },
    agentImpl: scopingAgents({ verified: false }),
  })
  assert.deepEqual(result.repos, [], 'an unconfirmed repository must never reach a Story, a spec pass, or a worktree')
  assert.equal(result.blocked.length, 1)
  assert.equal(result.spanVerified, false)
  assert.equal(result.ok, false, 'nothing usable was ruled and nothing was proposed — that is a failed ruling, not a span')
})

test('a placement naming a repository the survey never listed is refused as composed, not ruled', async () => {
  const { result } = await runWorkflowScript(SCOPING, {
    args: { prd: PRD },
    agentImpl: scopingAgents({
      placements: [{ repoPath: '/repos/invented', repoName: 'invented', workUnitIds: ['W1'], rationale: 'r' }],
      inventory: [{ repoPath: '/repos/alpha', name: 'alpha', owns: 'x' }],
    }),
  })
  assert.deepEqual(result.repos, [])
  assert.match(result.reason, /inventory/, 'the refusal must say the path was composed rather than surveyed')
})

test('a ruled path that could reshape a command is refused, never sanitized', async () => {
  // These become the downstream repoPath, which gets interpolated into `git -C "<path>"`
  // command text another agent runs verbatim. Here the author is an AGENT, which makes
  // the guard more necessary rather than less.
  const hostile = '/repos/alpha" && rm -rf / && echo "'
  const { result } = await runWorkflowScript(SCOPING, {
    args: { prd: PRD },
    agentImpl: scopingAgents({
      placements: [{ repoPath: hostile, repoName: 'alpha', workUnitIds: ['W1'], rationale: 'r' }],
      inventory: [{ repoPath: hostile, name: 'alpha', owns: 'x' }],
    }),
  })
  assert.deepEqual(result.repos, [], 'a path that can reshape a command must never reach one')
  assert.ok(result.blocked.length, 'and the refusal must say what was wrong')
})

test('an empty PRD body is REFUSED rather than returning an empty span', async () => {
  // "No repository could be ruled" and "no PRD was supplied" both reduce to `repos: []`,
  // and the caller treats the first as a real ruling that the work needs repositories
  // nobody has. Conflating them invents a repository requirement out of a missing argument.
  const { result, calls } = await runWorkflowScript(SCOPING, { args: { prd: { id: 'X', body: '' } }, agentImpl: () => null })
  assert.equal(result.ok, false)
  assert.deepEqual(result.repos, [])
  assert.deepEqual(calls, [], 'refusing after dispatching is not refusing')
})

// ── A new repository is RETURNED, never created ────────────────────────────────

test('a required NEW repository comes back as a human action and is never in the span', async () => {
  const { result } = await runWorkflowScript(SCOPING, {
    args: { prd: PRD },
    agentImpl: scopingAgents({
      placements: [],
      inventory: [{ repoPath: '/repos/alpha', name: 'alpha', owns: 'something else' }],
      newRepos: [{ proposedName: 'SkillSpoke-newthing', purpose: 'hosts W1', workUnitIds: ['W1'], whyNoExistingRepoFits: 'alpha owns a different context' }],
    }),
  })
  assert.equal(result.ok, true, 'ruling that a repository must be created is a successful ruling')
  assert.deepEqual(result.repos, [], 'a repository that does not exist is not part of the span')
  assert.equal(result.newRepos.length, 1)
  assert.ok(
    result.requiredHumanActions.some((x) => /polyrepo-steward/.test(x)),
    'the action must route through the steward, so the manifest is written with the repository',
  )
})

// ── The composite: how the span reaches the per-repo fan-out ───────────────────

/** Every gate passes; every mini answers minimally. `scopingResult` is what repo-scoping returns. */
function compositeWorkflows({ scopingResult, outOfRepoFindings = [] }) {
  let storyN = 0
  return (call) => {
    const name = String(call.name || '')
    if (name.endsWith('gate-enforce') || name.endsWith('gate-constitutional')) return { verdict: 'pass', criteria: [], flags: [] }
    if (name.endsWith('prd-reconciliation')) {
      return {
        ok: true,
        verdict: 'partial',
        requirements: [{ id: 'R1', requirement: 'r', status: 'absent', evidence: ['f.py:1'] }],
        deltaCount: 1,
        deltaPrdPath: '/prd/PRD-1.delta.md',
        deltaPrd: { path: '/prd/PRD-1.delta.md', body: 'b' },
        sizeVerdict: 'story',
        infraOnly: false,
        sizing: { deltaRepos: ['/repos/where-the-code-already-is'] },
      }
    }
    if (name.endsWith('prd-validation')) return { ok: true, validatedPrd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, findings: [] }
    if (name.endsWith('architecture')) return { ok: true, decision: { id: 'AD-1' }, sad: { path: 's' } }
    if (name.endsWith('repo-scoping')) return scopingResult
    if (name.endsWith('trd-authoring')) return { ok: true, trd: { id: 'TRD-1', summary: 'sum' } }
    if (name.endsWith('spec-authoring')) {
      storyN += 1
      const repoPath = (call.payload && call.payload.repoPath) || null
      return {
        ok: true,
        specSet: { apiSpec: {} },
        story: { key: `S${storyN}`, type: 'story', title: `Story for ${repoPath}`, description: 'd', repoPath, parentEpicKey: 'E1' },
        outOfRepoFindings,
      }
    }
    if (name.endsWith('task-decomposition')) {
      const sk = ((call.payload && call.payload.story) || {}).key || 'S?'
      return { ok: true, beadSet: [{ key: `${sk}-T1`, type: 'task', parentStoryId: sk, title: 't', description: 'd', acceptanceCriteria: ['a'] }] }
    }
    return null
  }
}

const RULED = (repos, extra = {}) => ({
  ok: true,
  repos,
  placements: repos.map((r) => ({ repoPath: r, repoName: r, workUnitIds: [], rationale: 'ruled', verified: true })),
  newRepos: [],
  requiredHumanActions: [],
  reclassified: [],
  blocked: [],
  spanVerified: true,
  ...extra,
})

test('with no args.repos the composite RULES the span and fans out over what it ruled', async () => {
  const ruled = ['/repos/alpha', '/repos/beta', '/repos/gamma']
  const { result, calls } = await runWorkflowScript(PRD_TO_SPEC, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repos/where-the-human-stood' },
    workflowImpl: compositeWorkflows({ scopingResult: RULED(ruled) }),
    agentImpl: beadWriter(),
  })

  assert.equal(result.ok, true, `composite failed at ${result.stage}: ${result.headline || ''}`)
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:repo-scoping').length, 1, 'the span must be ruled, once')
  assert.deepEqual(result.repoSpan, ruled)
  assert.deepEqual(
    result.hierarchy.stories.map((s) => s.repoPath),
    ruled,
    'one Story per RULED repository — not one per repository the caller happened to be standing in',
  )
})

test('the launch repository is passed to scoping as a seed, and is NOT the span', async () => {
  const { result, calls } = await runWorkflowScript(PRD_TO_SPEC, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repos/where-the-human-stood' },
    workflowImpl: compositeWorkflows({ scopingResult: RULED(['/repos/alpha']) }),
    agentImpl: beadWriter(),
  })
  const [scoping] = workflowCalls(calls, 'agent-teams-workforce:repo-scoping')
  assert.deepEqual(scoping.payload.seedRepos, ['/repos/where-the-human-stood'], 'the seed travels as a seed')
  assert.deepEqual(result.repoSpan, ['/repos/alpha'], 'and it loses to the ruling')
})

test('an explicit args.repos OVERRIDES the ruling for that run, and nothing is dispatched', async () => {
  // The override exists for a deliberate re-run and for tests. It is an argument passed in
  // band, never a stored artifact — which is what keeps the next run scoped afresh.
  const { result, calls } = await runWorkflowScript(PRD_TO_SPEC, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repos/alpha', repos: ['/repos/alpha', '/repos/beta'] },
    workflowImpl: compositeWorkflows({ scopingResult: RULED(['/repos/never-used']) }),
    agentImpl: beadWriter(),
  })
  assert.equal(result.ok, true, `composite failed at ${result.stage}: ${result.headline || ''}`)
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:repo-scoping').length, 0, 'a pinned span spends nothing')
  assert.deepEqual(result.repoSpan, ['/repos/alpha', '/repos/beta'])
})

test('a failed ruling STOPS the run — it never falls back to the launch repository', async () => {
  // Falling back would restore exactly the defect this phase removes, and would do it on
  // the one run where the span was least certain.
  const { result, calls } = await runWorkflowScript(PRD_TO_SPEC, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repos/where-the-human-stood' },
    workflowImpl: compositeWorkflows({ scopingResult: { ok: false, reason: 'could not establish the span' } }),
    agentImpl: beadWriter(),
  })
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'repo-scoping')
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:spec-authoring').length, 0, 'nothing may be specified against a guessed span')
})

test('a span that is entirely NEW repositories hands back the actions and creates nothing', async () => {
  const { result, calls } = await runWorkflowScript(PRD_TO_SPEC, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repos/alpha' },
    workflowImpl: compositeWorkflows({
      scopingResult: RULED([], {
        newRepos: [{ proposedName: 'SkillSpoke-newthing', purpose: 'p', whyNoExistingRepoFits: 'w' }],
        requiredHumanActions: ['Create SkillSpoke-newthing through the polyrepo-steward'],
        spanVerified: false,
      }),
    }),
    agentImpl: beadWriter(),
  })
  assert.equal(result.action, 'create-repos')
  assert.equal(result.newRepos.length, 1)
  assert.ok(result.requiredHumanActions.length)
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:spec-authoring').length, 0, 'there is nothing to author a Spec against')
  assert.match(result.headline, /re-run/, 'the caller has to be told what closes the loop')
})

test('the run attempt ceiling is RESCALED to the ruled span, before the first per-repo gate', async () => {
  // The ceiling is denominated in repo count and used to be computed at module scope, when
  // the span was still caller input. Now it cannot be known until the ruling lands, so it is
  // SEEDED from the launch repository and rescaled once. Without the rescale a PRD ruled
  // into four repositories runs against a ceiling sized for one: the Stories all get
  // authored, the budget runs out partway through decomposition, and the run returns
  // DEGRADED with three of the four Stories carrying no tasks — a shortfall caused entirely
  // by a ceiling for a span it no longer has.
  const ruled = ['/repos/a', '/repos/b', '/repos/c', '/repos/d']
  const { result, calls } = await runWorkflowScript(PRD_TO_SPEC, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repos/a' },
    workflowImpl: compositeWorkflows({ scopingResult: RULED(ruled) }),
    agentImpl: beadWriter(),
  })

  assert.equal(result.ok, true, `composite failed at ${result.stage}: ${String(result.headline || '').slice(0, 300)}`)
  assert.equal(result.hierarchy.stories.length, 4)
  assert.equal(result.hierarchy.tasks.length, 4, 'every Story decomposed — none starved by a ceiling sized for the seed')

  const budget = (journalPayload(calls) || {}).detail
  // Seeded at 3 + 2*1 + 3 = 8; a zero-retry 4-repo run costs 3 + 2*4 = 11 attempts.
  assert.ok(
    budget && budget.budget && budget.budget.maxTotalAttempts >= 11,
    `the ceiling must clear the ruled span's zero-retry cost, found ${JSON.stringify(budget && budget.budget)}`,
  )
})

test('a caller who PINNED maxTotalAttempts keeps exactly that, rescale or not', async () => {
  const { calls } = await runWorkflowScript(PRD_TO_SPEC, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repos/a', maxTotalAttempts: 99 },
    workflowImpl: compositeWorkflows({ scopingResult: RULED(['/repos/a', '/repos/b', '/repos/c', '/repos/d']) }),
    agentImpl: beadWriter(),
  })
  const detail = (journalPayload(calls) || {}).detail
  assert.equal(detail.budget.maxTotalAttempts, 99, 'pinning it is what pinning it means')
})

test('spec authoring finding work OUTSIDE the ruled span is surfaced, not dropped', async () => {
  // The only independent evidence the pipeline produces that the ruled span was WRONG. The
  // scoping phase ruled before any spec existed; a spec author who then needs a contract in
  // a repository outside the span has seen the hole from the one vantage point that could.
  const { result } = await runWorkflowScript(PRD_TO_SPEC, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repos/alpha' },
    workflowImpl: compositeWorkflows({
      scopingResult: RULED(['/repos/alpha']),
      outOfRepoFindings: ['the consumer for order.placed lives in /repos/beta and does not exist'],
    }),
    agentImpl: beadWriter(),
  })
  assert.equal(result.ok, true, `composite failed at ${result.stage}: ${result.headline || ''}`)
  assert.ok(Array.isArray(result.outOfSpanFindings) && result.outOfSpanFindings.length, 'it must cross the boundary, not go to the journal')
  assert.equal(result.outOfSpanFindings[0].repoPath, '/repos/alpha')
  assert.match(result.headline, /TOO NARROW/, 'and it must be visible without opening anything')
})
