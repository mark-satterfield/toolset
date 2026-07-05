export const meta = {
  name: 'spec-freshness',
  description:
    'Leaf mini — Spec Freshness. Fans three independent freshness checkers out in parallel (spec-vs-reality drift, ADR currency, upstream dependency changes), then a read-only lead aggregates the three verdicts into one fresh/stale ruling with reasons. Read-only — judges currency, changes no artifacts. Makers (the three checkers) and the aggregating router are distinct agents; the lead routes and aggregates, it never authors content.',
  phases: [
    { title: 'Freshness checks', detail: 'three independent currency checkers fan out in parallel' },
    { title: 'Aggregate', detail: 'read-only router rolls the three verdicts into one fresh/stale verdict' },
  ],
}

// args: {
//   spec: {                     // the spec under freshness review
//     id?: string,              // spec identifier
//     title?: string,           // human title
//     path?: string,            // path to the spec document
//     repoPath?: string,        // repo the spec governs
//     adrRefs?: string[],       // ADR ids/paths the spec references
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
const adrRefs = Array.isArray(spec.adrRefs) ? spec.adrRefs : []
const dependencies = Array.isArray(spec.dependencies) ? spec.dependencies : []

const specHeader = `Spec ${specId}${specTitle ? `: ${specTitle}` : ''}
Spec document: ${specPath}
Governing repository: ${repo}`

// ── Phase 1: Freshness checks — three INDEPENDENT checkers in parallel ──────────
// Segregation of duties: each checker is a distinct maker/checker agent; none of
// them judges another's output, and the read-only lead (phase 2) judges none of
// the content — it only aggregates the three verdicts.
phase('Freshness checks')

const [specCurrency, adrCurrency, dependencyChanges] = await parallel([
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

  // 2) ADR currency: are the ADRs this spec leans on still authoritative?
  () =>
    agent(
      `Validate that the ADRs this spec references are still current — not superseded, dissolved, or otherwise no longer authoritative. You are READ-ONLY: change nothing.

${specHeader}

ADRs referenced by the spec:
${adrRefs.length ? adrRefs.map((r, i) => `${i + 1}. ${r}`).join('\n') : '(none declared in args — discover referenced ADRs from the spec document itself)'}

For each referenced ADR, determine its current status and whether the spec relies on a decision that has since changed.

Deliver:
- current: true if every referenced ADR is still authoritative for what the spec depends on, false otherwise.
- adrFindings: each ADR with a problem (adr, status one of current/superseded/dissolved/missing, impact on the spec).
- evidence: how you verified ADR currency.`,
      {
        label: 'freshness:adr-currency',
        phase: 'Freshness checks',
        agentType: 'agent-teams-workforce:adr-currency-checker',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['current', 'adrFindings', 'evidence'],
          properties: {
            current: { type: 'boolean' },
            adrFindings: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['adr', 'status', 'impact'],
                properties: {
                  adr: { type: 'string' },
                  status: {
                    type: 'string',
                    enum: ['current', 'superseded', 'dissolved', 'missing'],
                  },
                  impact: { type: 'string' },
                },
              },
            },
            evidence: { type: 'string' },
            notes: { type: 'string' },
          },
        },
      }
    ),

  // 3) Dependency-change detection: did anything upstream the spec relies on change?
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
  `You are the spec-freshness lead — a READ-ONLY router. You do NOT inspect the spec or code yourself and you do NOT author content. Synthesize the three independent freshness verdicts below into ONE fresh/stale ruling. The spec is FRESH only if all three checkers report current=true; if any reports current=false, the spec is STALE.

${specHeader}

Spec-vs-reality currency verdict:
${JSON.stringify(specCurrency ?? {}, null, 2)}

ADR currency verdict:
${JSON.stringify(adrCurrency ?? {}, null, 2)}

Upstream dependency-change verdict:
${JSON.stringify(dependencyChanges ?? {}, null, 2)}

Deliver:
- fresh: true only if all three checkers are current; false if any is not.
- staleReasons: a flat list of the concrete reasons the spec is stale (empty if fresh), each attributed to its source check (spec-currency / adr-currency / dependency-change).`,
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
                enum: ['spec-currency', 'adr-currency', 'dependency-change'],
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
  chosen: ['spec-currency-validator', 'adr-currency-checker', 'dependency-change-detector', 'spec-freshness-lead'],
  mode: 'fixed', // design-mandated full fan-out — correct, not a gap
  ok: aggregate ? !!aggregate.fresh : false,
}

return {
  fresh: aggregate ? aggregate.fresh : false,
  specCurrency,
  adrCurrency,
  dependencyChanges,
  staleReasons: (aggregate && aggregate.staleReasons) || [],
  contract: a.contract || null,
  ledger,
}
