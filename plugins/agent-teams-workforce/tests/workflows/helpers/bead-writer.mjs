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
 * Compose the writer stub in front of a test's own agentImpl.
 *
 * @param {(call: object, calls: object[]) => any} [inner] the test's own agent answers
 * @param {object} [opts] passed to `beadWriter`
 */
export function withBeadWriter(inner, opts) {
  const writer = beadWriter(opts)
  return (call, calls) => {
    const written = writer(call)
    if (written) return written
    return inner ? inner(call, calls) : null
  }
}
