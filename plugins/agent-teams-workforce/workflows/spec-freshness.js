export const meta = {
  name: 'spec-freshness',
  description:
    'Leaf mini — Spec Freshness. Fans two independent freshness checkers out in parallel (spec-vs-reality drift, upstream dependency changes), then a read-only lead aggregates the two verdicts into one fresh/stale ruling with reasons. Read-only — judges currency, changes no artifacts. Makers (the two checkers) and the aggregating router are distinct agents; the lead routes and aggregates, it never authors content.',
  phases: [
    { title: 'Freshness checks', detail: 'two independent currency checkers fan out in parallel' },
    { title: 'Aggregate', detail: 'read-only router rolls the two verdicts into one fresh/stale verdict' },
  ],
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
    agent(
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
    agent(
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

const aggregate = await agent(
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
