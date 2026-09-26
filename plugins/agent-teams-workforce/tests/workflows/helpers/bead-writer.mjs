// A stand-in for the `bead-writer` agent, for tests that run prd-to-spec.
//
// prd-to-spec WRITES its hierarchy now — it does not hand it back with an instruction to
// write it — so a fixture whose agentImpl answers null for the write waves is modelling a
// run in which nothing was persisted, and that run is correctly ok:false. Every fixture
// that expects a successful composite therefore has to answer the writer, exactly as it
// already answers the minis and the gates.
//
// The stub is deliberately faithful in the one way that matters: it reports back ONLY the
// keys it was handed, so a composite that forgets to include a bead in a wave, or that
// asks for a bead twice, shows up as a discrepancy rather than being papered over.

/** Pull the JSON payload out of a bead-writer prompt. */
export function writerPayload(call) {
  const marker = 'JSON payload:\n'
  const i = String(call.prompt || '').indexOf(marker)
  if (i < 0) return null
  try {
    return JSON.parse(String(call.prompt).slice(i + marker.length))
  } catch {
    return null
  }
}

/** True for the write/link/survey/heal dispatches this composite makes. */
export function isWriterCall(call) {
  return call.kind === 'agent' && /^beads:(write-|link|survey|heal)/.test(String(call.label || ''))
}

/**
 * An agentImpl fragment that answers the bead-writer waves and nothing else.
 *
 * @param {object} [opts]
 * @param {string[]} [opts.failKeys]  local keys whose create must come back failed
 * @param {boolean}  [opts.failLinks] refuse every dependency edge
 * @param {(key: string) => string} [opts.idFor] id minting, default `bd-<key>`
 * @param {(parentId: string) => object[]} [opts.nodesFor] survey answer, default no children
 * @param {string[]} [opts.failMutations] mutation keys whose apply must come back failed
 * @returns {(call: object) => object|null} the reply, or null when it is not a writer call
 */
export function beadWriter({ failKeys = [], failLinks = false, idFor = (k) => `bd-${k}`, nodesFor = () => [], failMutations = [] } = {}) {
  const fail = new Set(failKeys)
  const failMut = new Set(failMutations)
  return (call) => {
    if (!isWriterCall(call)) return null
    const payload = writerPayload(call) || { beads: [], links: [] }
    return {
      surveys: (payload.surveys || []).map((s) => ({ key: s.key, ok: true, nodes: nodesFor(s.parentId) })),
      mutations: (payload.mutations || []).map((m) =>
        failMut.has(m.key) ? { key: m.key, ok: false, error: 'scripted failure' } : { key: m.key, ok: true },
      ),
      results: (payload.beads || []).map((b) =>
        fail.has(b.key)
          ? { key: b.key, id: null, ok: false, error: 'scripted failure' }
          : { key: b.key, id: idFor(b.key), ok: true },
      ),
      links: (payload.links || []).map((l) => ({
        fromId: l.fromId,
        dependsOnId: l.dependsOnId,
        ok: !failLinks,
        ...(failLinks ? { error: 'scripted failure' } : {}),
      })),
    }
  }
}

/**
 * The artifact arguments prd-to-spec writes its hierarchy from: without a working directory
 * it has no saved documents to emit, so every fixture that expects a written hierarchy
 * passes these.
 */
export const ARTIFACT_ARGS = Object.freeze({ artifactScript: '/opt/sdlc/artifactio.py', projectRoot: '/proj' })

/**
 * The Epic every prd-to-spec fixture elaborates: an existing, scored Epic bead. prd-to-spec
 * refuses at its start without one.
 */
export const TEST_EPIC = Object.freeze({ id: 'bd-E1', key: 'E1', title: 'Test Epic' })

/** The Epic's judged values, as the lifecycle check reads them off the Epic bead. */
export const TEST_EPIC_VALUE = Object.freeze({ id: 'bd-E1', userBusinessValue: 8, timeCriticality: 3, confidence: 80 })

/**
 * An agentImpl fragment that answers prd-to-spec's Epic lifecycle runners — the start check,
 * the emission and finish (`elaboration-complete`) and the release — as `depscore.py` would for an
 * Epic that may be elaborated, and the cross-Story dependency mapper with no edges.
 *
 * @param {object} [opts]
 * @param {object} [opts.refusal] the start check's refusal, `{code, reason}`
 * @param {object[]} [opts.crossStoryEdges] the cross-Story Task edges the mapper returns
 * @returns {(call: object) => object|null} the reply, or null when it is not a lifecycle call
 */
export function lifecycleRunner({ refusal = null, crossStoryEdges = [] } = {}) {
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
    if (call.label === 'epic:complete') {
      // `depscore.py elaboration-complete` reads the saved documents and writes them; this stub
      // answers as it does when every bead landed, for every key a fixture can mint.
      const done = !/\s--hold\s/.test(String(call.prompt || ''))
      const tasks = {}
      const stories = {}
      for (let s = 1; s <= 10; s++) {
        stories[`S${s}`] = `bd-S${s}`
        for (let t = 1; t <= 20; t++) tasks[`S${s}-T${t}`] = `bd-S${s}-T${t}`
      }
      for (let n = 1; n <= 20; n++) {
        tasks[`REMOVAL-${n}`] = `bd-REMOVAL-${n}`
        tasks[`IMPACT-${n}`] = `bd-IMPACT-${n}`
      }
      return {
        exitCode: 0,
        output: {
          ok: true,
          epic: TEST_EPIC.id,
          emission: {
            target: '/repo',
            attempted: 0,
            created: 0,
            adopted: 0,
            written: [],
            failed: [],
            skipped: [],
            specReferenceMissing: [],
            knockOnWithoutSpec: [],
            links: { attempted: 0, linked: 0, failed: [] },
            heal: { ran: false, reason: null, wrappers: 0, reparented: 0, closed: 0, failed: [] },
            reelaboration: null,
            verdict: 'complete',
            reason: 'all bead(s) of this hierarchy are durable',
          },
          stories,
          tasks,
          done,
          finish: {
            ok: true,
            epic: TEST_EPIC.id,
            lifecycle: done ? { elaboration_state: 'done', elaboration_state_cause: 'decomposed-into-tasks' } : null,
            summary: { ok: true, epic: TEST_EPIC.id, tasksScored: 0, unscored: 0, done },
          },
        },
      }
    }
    if (call.label === 'epic:release') return { exitCode: 0, output: { ok: true, epic: TEST_EPIC.id, released: true } }
    if (call.label === 'sequence:cross-story-tasks') return { edges: crossStoryEdges, acyclic: true }
    return null
  }
}

/**
 * Compose the lifecycle stub in front of a test's own agentImpl.
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

/**
 * Compose the writer stub and the lifecycle stub in front of a test's own agentImpl.
 *
 * @param {(call: object, calls: object[]) => any} [inner] the test's own agent answers
 * @param {object} [opts] passed to `beadWriter`
 */
export function withBeadWriter(inner, opts) {
  const writer = beadWriter(opts)
  return withLifecycle((call, calls) => {
    const written = writer(call)
    if (written) return written
    return inner ? inner(call, calls) : null
  })
}
