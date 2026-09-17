export const meta = {
  name: 'spec-freshness',
  description:
    'Leaf mini — Spec Freshness. Fans two independent freshness checkers out in parallel (spec-vs-reality drift, upstream dependency changes), then a read-only lead aggregates the two verdicts into one fresh/stale ruling with reasons. Read-only — judges currency, changes no artifacts. Makers (the two checkers) and the aggregating router are distinct agents; the lead routes and aggregates, it never authors content.',
  phases: [
    { title: 'Freshness checks', detail: 'two independent currency checkers fan out in parallel' },
    { title: 'Aggregate', detail: 'read-only router rolls the two verdicts into one fresh/stale verdict' },
  ],
}
// ── EVERY DISPATCH IS SETTLED ────────────────────────────────────────────────────
//
// `agent()` fails in two different ways and the scripts used to conflate them. It
// RETURNS NULL when a subagent is skipped or dies on a terminal API error after the
// runtime's own retries. It THROWS when a subagent finishes without calling
// StructuredOutput — and an uncaught throw leaves this script, leaves whatever
// composite called it, and kills the run: two recorded crashes cost 1.13M and 1.88M
// tokens and discarded every artifact the run had already paid for.
//
// So every dispatch in this file goes through settleAgent(). A throw never escapes it,
// and it records what the engine's error text loses — that text reads
// `agent({schema}): subagent completed without calling StructuredOutput`, which names
// neither the agent, nor the phase, nor the schema, and points at no transcript. The
// caller receives null, which every call site already handles, and `dispatchFailures`
// carries the identity of what died, for the `dispatchFailed` report this script owes
// its caller: a phase whose producing agents died is NOT adjudicated.
//
// This block is identical in every workflow script on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text everywhere.
const dispatchFailures = []
// The dispatch deaths belonging to the named phases (every death when none is named).
// A phase whose PRODUCING agents died has no artifact to judge, so its caller must not
// adjudicate it and must not spend a retry on it — that is the `dispatchFailed` contract.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
function settleSchemaName(o) {
  if (typeof o.schemaName === 'string' && o.schemaName) return o.schemaName
  const s = o.schema
  if (!s || typeof s !== 'object') return null
  if (typeof s.title === 'string' && s.title) return s.title
  const req = Array.isArray(s.required) && s.required.length ? s.required : Object.keys(s.properties || {})
  return req.length ? `{${req.join(', ')}}` : null
}
function settleTranscript(err, label) {
  const e = err && typeof err === 'object' ? err : {}
  for (const k of ['transcriptPath', 'transcript', 'agentPath', 'logPath']) {
    if (typeof e[k] === 'string' && e[k]) return e[k]
  }
  const id = typeof e.agentId === 'string' && e.agentId ? e.agentId : null
  if (id) return `agent-${id}.jsonl in this run's workflow transcript directory`
  return `the agent-<id>.jsonl in this run's workflow transcript directory whose agent-<id>.meta.json description is ${JSON.stringify(label)}`
}
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const call = { ...o }
  delete call.schemaName
  const who = {
    agentType: o.agentType || null,
    label: o.label || null,
    phase: o.phase || null,
    schema: settleSchemaName(o),
  }
  const name = who.label || who.agentType || 'agent'
  const whose = `${name}${who.agentType && who.agentType !== name ? ` (${who.agentType})` : ''}${who.phase ? ` in ${who.phase}` : ''}`
  let out = null
  try {
    out = await agent(prompt, call)
  } catch (err) {
    const message = String((err && err.message) || err)
    dispatchFailures.push({
      ...who,
      outcome: 'threw',
      message: message.slice(0, 300),
      transcript: settleTranscript(err, name),
      note: `${whose} finished without a structured result${who.schema ? ` for schema ${who.schema}` : ''}: ${message.slice(0, 160)}`,
    })
    log(`${name}: session ended without a structured result — ${message.slice(0, 160)}`)
    return null
  }
  if (out) return out
  dispatchFailures.push({
    ...who,
    outcome: 'skipped',
    message: null,
    transcript: settleTranscript(null, name),
    note: `${whose} returned nothing — skipped, or died on a terminal API error after the runtime's own retries`,
  })
  log(`${name}: returned nothing — skipped, or died on a terminal API error after the runtime's own retries`)
  return null
}

// args: {
//   spec: {                     // the spec under freshness review
//     id?: string,              // spec identifier
//     title?: string,           // human title
//     path?: string,            // path to the spec document
//     repoPath?: string,        // repo the spec governs
//     dependencies?: string[],  // upstream contracts/specs/libs the spec relies on
//   },
//   contract?: any,             // optional upstream contract this freshness check sits under (threaded back out)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const spec = a.spec || {}
const specId = spec.id || '(no spec id)'
const specTitle = spec.title || ''
const specPath = spec.path || '(spec path not provided — ask before reading files)'
const repo = spec.repoPath || '(repo path not provided — ask before reading files)'
const dependencies = Array.isArray(spec.dependencies) ? spec.dependencies : []

const specHeader = `Spec ${specId}${specTitle ? `: ${specTitle}` : ''}
Spec document: ${specPath}
Governing repository: ${repo}`

// ── Phase 1: Freshness checks — two INDEPENDENT checkers in parallel ───────────
// Segregation of duties: each checker is a distinct maker/checker agent; none of
// them judges another's output, and the read-only lead (phase 2) judges none of
// the content — it only aggregates the two verdicts.
phase('Freshness checks')

const [specCurrency, dependencyChanges] = await parallel([
  // 1) Spec-vs-reality currency: has the implemented code/behavior drifted from the spec?
  () =>
    settleAgent(
      `Validate that this spec still matches current code and reality — detect spec drift. You are READ-ONLY: do not change the spec or any code.

${specHeader}

Determine whether the spec still describes the system as it is actually built and behaves now. Look for: contracts the spec asserts that the code no longer honors, behaviors the code added/removed that the spec does not reflect, endpoints/schemas/flows that diverge, and anything the spec claims as current that is no longer true.

Deliver:
- current: true if the spec still matches reality with no material drift, false otherwise.
- driftFindings: each concrete divergence between the spec and the implemented reality (specClaim, observedReality, location file:line where possible).
- evidence: how you verified currency (files inspected, behaviors traced).`,
      {
        label: 'freshness:spec-currency',
        phase: 'Freshness checks',
        agentType: 'agent-teams-workforce:spec-currency-validator',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['current', 'driftFindings', 'evidence'],
          properties: {
            current: { type: 'boolean' },
            driftFindings: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['specClaim', 'observedReality', 'location'],
                properties: {
                  specClaim: { type: 'string' },
                  observedReality: { type: 'string' },
                  location: { type: 'string' },
                },
              },
            },
            evidence: { type: 'string' },
            notes: { type: 'string' },
          },
        },
      }
    ),

  // 2) Dependency-change detection: did anything upstream the spec relies on change?
  () =>
    settleAgent(
      `Detect upstream dependency changes that would invalidate this spec. You are READ-ONLY: change nothing.

${specHeader}

Upstream dependencies the spec relies on:
${dependencies.length ? dependencies.map((d, i) => `${i + 1}. ${d}`).join('\n') : '(none declared in args — discover dependencies the spec relies on from the spec document itself)'}

Determine whether any upstream contract, shared schema, event, library version, or interface the spec depends on has changed in a way that invalidates the spec's assumptions.

Deliver:
- current: true if no invalidating upstream change is found, false otherwise.
- changeFindings: each invalidating change (dependency, change describing what changed, invalidates describing what spec assumption it breaks).
- evidence: how you verified the dependency state.`,
      {
        label: 'freshness:dependency-changes',
        phase: 'Freshness checks',
        agentType: 'agent-teams-workforce:dependency-change-detector',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['current', 'changeFindings', 'evidence'],
          properties: {
            current: { type: 'boolean' },
            changeFindings: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['dependency', 'change', 'invalidates'],
                properties: {
                  dependency: { type: 'string' },
                  change: { type: 'string' },
                  invalidates: { type: 'string' },
                },
              },
            },
            evidence: { type: 'string' },
            notes: { type: 'string' },
          },
        },
      }
    ),
])

// ── Phase 2: Aggregate — read-only router rolls the three verdicts into one ─────
// The lead is a read-only router: it does not re-judge the underlying code/spec,
// it only synthesizes the three checker verdicts into a single fresh/stale ruling.
phase('Aggregate')

const aggregate = await settleAgent(
  `You are the spec-freshness lead — a READ-ONLY router. You do NOT inspect the spec or code yourself and you do NOT author content. Synthesize the two independent freshness verdicts below into ONE fresh/stale ruling. The spec is FRESH only if both checkers report current=true; if either reports current=false, the spec is STALE.

${specHeader}

Spec-vs-reality currency verdict:
${JSON.stringify(specCurrency ?? {}, null, 2)}

Upstream dependency-change verdict:
${JSON.stringify(dependencyChanges ?? {}, null, 2)}

Deliver:
- fresh: true only if both checkers are current; false if either is not.
- staleReasons: a flat list of the concrete reasons the spec is stale (empty if fresh), each attributed to its source check (spec-currency / dependency-change).`,
  {
    label: 'aggregate:freshness-verdict',
    phase: 'Aggregate',
    agentType: 'agent-teams-workforce:spec-freshness-lead',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['fresh', 'staleReasons'],
      properties: {
        fresh: { type: 'boolean' },
        staleReasons: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['source', 'reason'],
            properties: {
              source: {
                type: 'string',
                enum: ['spec-currency', 'dependency-change'],
              },
              reason: { type: 'string' },
            },
          },
        },
        summary: { type: 'string' },
      },
    },
  }
)

const ledger = {
  phase: 'spec-freshness',
  beadId: null,
  subject: specId,
  chosen: ['spec-currency-validator', 'dependency-change-detector', 'spec-freshness-lead'],
  mode: 'fixed', // design-mandated full fan-out — correct, not a gap
  ok: aggregate ? !!aggregate.fresh : false,
}

return {
  fresh: aggregate ? aggregate.fresh : false,
  specCurrency,
  dependencyChanges,
  staleReasons: (aggregate && aggregate.staleReasons) || [],
  contract: a.contract || null,
  ledger,
}
