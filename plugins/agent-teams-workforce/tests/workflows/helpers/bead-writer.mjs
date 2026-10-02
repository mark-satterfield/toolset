// Stand-ins for the depscore.py runner sessions prd-to-spec and its minis dispatch.
//
// Each bead is written by the session that authors it: the Story author runs one
// `depscore.py write-story --out` and returns its short stdout as `write`; the decomposer runs
// `plan-tasks` and one `write-task` per Task, and the cross-Story mapper runs one
// `write-all-task-edges`, each returning the commands' stdout as `writes`. On a replay a
// runner session runs the same commands (`beads:write-story`, `beads:write-tasks`,
// `beads:write-all-task-edges`). `epic:finish`, `prd:parse`, `arch:delta` and
// `arch:target-remove` are runner sessions. A
// fixture that expects a successful run answers them the way the commands answer when every
// write landed.

/** True for the depscore.py runner sessions: the bead writes and the Epic lifecycle. */
export function isWriterCall(call) {
  return call.kind === 'agent' && /^(beads:write-|epic:)/.test(String(call.label || ''))
}

/**
 * The artifact arguments prd-to-spec saves its documents under: without a working directory
 * there is no saved document for a write command to read, so every fixture that expects a
 * written hierarchy passes these.
 */
export const ARTIFACT_ARGS = Object.freeze({ artifactScript: '/opt/sdlc/artifactio.py', projectRoot: '/proj' })

/**
 * The Epic every prd-to-spec fixture elaborates: an existing, scored Epic bead. prd-to-spec
 * refuses at its start without one.
 */
export const TEST_EPIC = Object.freeze({ id: 'bd-E1', key: 'E1', title: 'Test Epic' })

/** The cds design system paths the prd-to-spec fixtures pass. */
export const TEST_DESIGN_SYSTEM = Object.freeze({ packagesDir: '/cds/packages', mocksDir: '/cds/mocks', shellsDir: '/cds/shells' })

/** The delta items `depscore.py arch-delta` lists for the fixtures' approved target. */
export const TEST_DELTA_ITEMS = Object.freeze([
  Object.freeze({ id: 'D1', element: 'auth-service', views: ['/arch/target/mfa/delta/05-building-block-view/mfa.md'] }),
])

/** An architecture result with an approved target and its delta, as the architecture mini returns it. */
export const TEST_ARCHITECTURE = Object.freeze({
  ok: true,
  subject: 'mfa',
  targetDir: '/arch/target/mfa',
  deltaDir: '/arch/target/mfa/delta',
  decisionPath: '/proj/art/architecture/decision.md',
  architectureUpdate: { changedFiles: [], createdFiles: [] },
})

/** The Epic's judged values, as the lifecycle check reads them off the Epic bead. */
export const TEST_EPIC_VALUE = Object.freeze({ id: 'bd-E1', userBusinessValue: 8, timeCriticality: 3, confidence: 80 })

/** The stdout of one successful command, as its session records it. */
const ran = (out) => ({ exitCode: 0, stdout: JSON.stringify(out) })

/** The `plan-tasks` and `write-task` outputs for a Story's Tasks, as the writing session records them. */
function taskWrites(slug, keys) {
  return [
    ran({ ok: true, slug, tasks: keys.map((key) => ({ key, elabKey: `task:${slug}:${key}`, title: key, dependsOn: [] })), summary: { tasks: keys.length } }),
    ...keys.map((key) =>
      ran({
        ok: true,
        story: `bd-${slug}`,
        task: { key, elabKey: `task:${slug}:${key}`, id: `bd-${slug}-${key}`, action: 'created', title: key, dependsOn: [], outsideBlockers: [] },
        edges: { added: 0, removed: 0, standing: 0 },
        summary: { key, id: `bd-${slug}-${key}`, action: 'created', added: 0, removed: 0, standing: 0 },
      })
    ),
  ]
}

/** The `write-all-task-edges` output for the mapper's edges, as the writing session records it. */
function edgeWrites(edges) {
  const blockers = {}
  for (const e of edges) (blockers[e.to] = blockers[e.to] || []).push(e.from)
  return [
    ran({ command: 'write-all-task-edges', out: 'all.json', warnings: [], summary: { edges: edges.length, rejected: 0, blockers, written: Object.keys(blockers), added: edges.length, removed: 0, standing: 0 } }),
  ]
}

/** The `write-story` output for a Story, as the Story author records it. */
function storyWrite(slug) {
  return ran({ command: 'write-story', out: `story-${slug}.written.json`, warnings: [], summary: { id: `bd-${slug}`, elabKey: `story:${slug}`, action: 'created', created: 1, updated: 0 } })
}

/** The `--slug` value of a write command prompt. */
function slugOf(call) {
  const m = /--slug '([^']*)'/.exec(String(call.prompt || ''))
  return m ? m[1] : 'repo'
}

/**
 * An agentImpl fragment that answers the depscore.py runner sessions — the start check, the
 * bead writes, the finish and the release — as `depscore.py` does for an Epic that may be
 * elaborated and a write that landed, and the cross-Story dependency mapper with no edges.
 *
 * @param {object} [opts]
 * @param {object} [opts.refusal] the start check's refusal, `{code, reason}`
 * @param {object[]} [opts.crossStoryEdges] the cross-Story Task edges the mapper returns
 * @param {string[]} [opts.taskKeys] the Task keys a replayed `beads:write-tasks` reports as created
 * @returns {(call: object) => object|null} the reply, or null when it is not one of those calls
 */
export function lifecycleRunner({ refusal = null, crossStoryEdges = [], taskKeys = ['T1'], deltaItems = TEST_DELTA_ITEMS } = {}) {
  return (call) => {
    if (call.kind !== 'agent') return null
    if (call.label === 'resolve-plugin-root') return { exitCode: 0, output: { pluginRoot: '/opt/plugins/agent-teams-workforce', problem: null } }
    if (call.label === 'prd:parse') return { exitCode: 0, output: { ok: true, requirementHeadings: ['R1'], failed: [] } }
    if (call.label === 'arch:delta') {
      return { exitCode: 0, output: { ok: true, refusals: [], items: deltaItems, summary: { ok: true, items: deltaItems.length } } }
    }
    if (call.label === 'scope:check-placements') {
      const repos = String(call.prompt || '').split('\n').filter((l) => /^- \//.test(l)).map((l) => l.slice(2).trim())
      return { verdicts: repos.map((repoPath) => ({ repoPath, buildable: true, active: true, controlRepository: false, reason: 'an active service repository' })) }
    }
    if (call.label === 'arch:target-remove') return { exitCode: 0, output: { ok: true, refusals: [], removed: true, commit: 'abc1234' } }
    if (call.label === 'epic:start') {
      return {
        pluginRoot: '/opt/plugins/agent-teams-workforce',
        exitCode: 0,
        output: refusal
          ? { ok: false, refusal, epic: { id: TEST_EPIC.id, title: TEST_EPIC.title } }
          : { ok: true, refusal: null, epic: { ...TEST_EPIC_VALUE, title: TEST_EPIC.title }, owner: 'test-owner', previousState: 'ready' },
      }
    }
    if (call.label === 'beads:write-story') {
      const slug = slugOf(call)
      return {
        exitCode: 0,
        output: { command: 'write-story', out: `story-${slug}.written.json`, warnings: [], summary: { id: `bd-${slug}`, elabKey: `story:${slug}`, action: 'created', created: 1, updated: 0 } },
      }
    }
    if (call.label === 'beads:write-tasks') return { writes: taskWrites(slugOf(call), taskKeys) }
    if (call.label === 'beads:write-all-task-edges') return { writes: edgeWrites([]) }
    if (call.label === 'epic:finish') {
      const done = /\s--done(\s|$)/.test(String(call.prompt || ''))
      return {
        exitCode: 0,
        output: {
          ok: true,
          epic: TEST_EPIC.id,
          lifecycle: done ? { elaboration_state: 'done', elaboration_state_cause: 'decomposed-into-tasks' } : null,
          missing: [],
          summary: { ok: true, epic: TEST_EPIC.id, tasksScored: 0, unscored: 0, done, persisted: true, missing: [] },
        },
      }
    }
    if (call.label === 'epic:release') return { exitCode: 0, output: { ok: true, epic: TEST_EPIC.id, released: true } }
    if (call.label === 'sequence:cross-story-tasks') return { edges: crossStoryEdges, acyclic: true, writes: edgeWrites(crossStoryEdges) }
    return null
  }
}

/**
 * Add the bead writes a test's own answer for an authoring session leaves out: the Story
 * author's `write`, the decomposer's `writes`, the cross-Story mapper's `writes`.
 *
 * @param {object} call the agent call
 * @param {any} out the test's answer
 * @returns {any} the answer, with the writes its session records
 */
function withWrites(call, out) {
  if (!out || typeof out !== 'object' || call.kind !== 'agent') return out
  if (call.label === 'author:story-bead' && !out.write) return { ...out, write: storyWrite(slugOf(call)) }
  if (call.label === 'decompose:sequence-and-score' && !out.writes && Array.isArray(out.tasks)) {
    return { ...out, writes: taskWrites(slugOf(call), out.tasks.map((t) => t.key)) }
  }
  if (call.label === 'sequence:cross-story-tasks' && !out.writes) return { ...out, writes: edgeWrites(Array.isArray(out.edges) ? out.edges : []) }
  return out
}

/**
 * Compose the runner stub in front of a test's own agentImpl.
 *
 * @param {(call: object, calls: object[]) => any} [inner] the test's own agent answers
 * @param {object} [opts] passed to `lifecycleRunner`
 */
export function withLifecycle(inner, opts) {
  const runner = lifecycleRunner(opts)
  return (call, calls) => {
    const answered = runner(call)
    if (answered) return answered
    const out = inner ? inner(call, calls) : null
    return withWrites(call, out)
  }
}
