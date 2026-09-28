// Stand-ins for the depscore.py runner sessions prd-to-spec and its minis dispatch.
//
// Each bead write is one runner session that runs one `depscore.py` command and returns its
// JSON output: `beads:write-story` inside spec-authoring, `beads:write-tasks` inside
// task-decomposition, `beads:write-task-edges` and `epic:finish` in prd-to-spec. A fixture
// that expects a successful run answers them the way the command answers when every write
// landed.

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

/** The Epic's judged values, as the lifecycle check reads them off the Epic bead. */
export const TEST_EPIC_VALUE = Object.freeze({ id: 'bd-E1', userBusinessValue: 8, timeCriticality: 3, confidence: 80 })

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
 * @param {string[]} [opts.taskKeys] the Task keys `beads:write-tasks` reports as created
 * @returns {(call: object) => object|null} the reply, or null when it is not one of those calls
 */
export function lifecycleRunner({ refusal = null, crossStoryEdges = [], taskKeys = ['T1'] } = {}) {
  return (call) => {
    if (call.kind !== 'agent') return null
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
        output: {
          ok: true,
          epic: TEST_EPIC.id,
          story: { id: `bd-${slug}`, elabKey: `story:${slug}`, action: 'created', title: `Story ${slug}`, description: 'd', decisionIds: [] },
          existingTasks: [],
          summary: { created: 1, updated: 0 },
        },
      }
    }
    if (call.label === 'beads:write-tasks') {
      const slug = slugOf(call)
      return {
        exitCode: 0,
        output: {
          ok: true,
          epic: TEST_EPIC.id,
          story: { id: `bd-${slug}`, elabKey: `story:${slug}` },
          tasks: taskKeys.map((key) => ({ key, elabKey: `task:${slug}:${key}`, id: `bd-${slug}-${key}`, action: 'created', title: key, dependsOn: [] })),
          closed: [],
          edges: { added: 0, removed: 0, standing: 0 },
          fingerprinted: taskKeys.length,
          summary: { created: taskKeys.length, updated: 0, unchanged: 0, closed: 0 },
        },
      }
    }
    if (call.label === 'beads:write-task-edges') {
      return { exitCode: 0, output: { ok: true, epic: TEST_EPIC.id, edges: [], rejected: [], summary: { added: 0, removed: 0, standing: 0 } } }
    }
    if (call.label === 'epic:finish') {
      const done = /\s--done(\s|$)/.test(String(call.prompt || ''))
      return {
        exitCode: 0,
        output: {
          ok: true,
          epic: TEST_EPIC.id,
          lifecycle: done ? { elaboration_state: 'done', elaboration_state_cause: 'decomposed-into-tasks' } : null,
          summary: { ok: true, epic: TEST_EPIC.id, tasksScored: 0, unscored: 0, done },
        },
      }
    }
    if (call.label === 'epic:release') return { exitCode: 0, output: { ok: true, epic: TEST_EPIC.id, released: true } }
    if (call.label === 'sequence:cross-story-tasks') return { edges: crossStoryEdges, acyclic: true }
    return null
  }
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
    return inner ? inner(call, calls) : null
  }
}
