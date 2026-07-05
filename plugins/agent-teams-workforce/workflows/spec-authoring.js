export const meta = {
  name: 'spec-authoring',
  description:
    'Leaf mini — Spec authoring. Turns an approved requirements/TRD packet into the implementation-ready specification set: the API/OpenAPI contract, the per-service data model, the event contracts, the error-handling spec, the acceptance criteria, and the Definition of Done. Maker agents author each artifact in parallel; INDEPENDENT reviewer agents judge the reviewable artifacts (segregation of duties — no author reviews its own work); a bounded maker/checker loop re-runs the maker on rejection and the spec-decider breaks any deadlock. Read-and-author only — no nested workflow(); the downstream gate owns final acceptance.',
  phases: [
    { title: 'Author specs', detail: 'makers author each spec artifact in parallel' },
    { title: 'Review specs', detail: 'independent reviewers judge the reviewable artifacts' },
    { title: 'Decide', detail: 'spec-decider breaks any maker/checker deadlock' },
  ],
}

// args: {
//   spec: {                       // the spec context being authored against
//     id?: string,                // spec/feature identifier
//     title?: string,
//     summary?: string,           // what the spec must cover (WHAT, not HOW)
//     service?: string,           // owning service / repo (per-service isolation)
//     repoPath?: string,          // where the spec artifacts live (read-only here)
//   },
//   trd?: any,                    // upstream TRD / requirements packet to author from
//   constraints?: string[],       // architectural constraints (REST v1, no Step Functions, etc.)
//   accessPatterns?: string[],    // known data access patterns for the data model
//   maxLoops?: number,            // bounded maker/checker retries per reviewable artifact (default 2)
// }
//
// MODULE FORM: all logic lives inside async main(); the file's last top-level
// statement is `await main(args)`. This keeps the file a clean standalone ES module
// (top-level await is legal; a bare top-level `return` is NOT) and remains valid
// under the Workflow harness, which permits top-level await in a mini body.

// ── Schemas (strict: additionalProperties:false + explicit required) ─────────────

const SPEC_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['artifactPaths', 'summary', 'content'],
  properties: {
    artifactPaths: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    content: { type: 'string' },
    openQuestions: { type: 'array', items: { type: 'string' } },
  },
}

const AC_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['acceptanceCriteria'],
  properties: {
    acceptanceCriteria: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['given', 'when', 'then'],
        properties: {
          given: { type: 'string' },
          when: { type: 'string' },
          then: { type: 'string' },
        },
      },
    },
    notes: { type: 'string' },
  },
}

const DOD_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['definitionOfDone'],
  properties: {
    definitionOfDone: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
}

const REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['verdict', 'findings'],
  properties: {
    verdict: { type: 'string', enum: ['approve', 'reject'] },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['severity', 'detail'],
        properties: {
          severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
          detail: { type: 'string' },
          location: { type: 'string' },
        },
      },
    },
    feedback: { type: 'string' },
  },
}

const DECISION_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['ruling', 'rationale'],
  properties: {
    ruling: { type: 'string', enum: ['accept-maker', 'accept-reviewer', 'revise'] },
    rationale: { type: 'string' },
    directive: { type: 'string' },
  },
}

// ── Helpers ──────────────────────────────────────────────────────────────────────

function ctxBlock(s, trd, constraints) {
  return [
    `Spec ${s.id || ''}: ${s.title || ''}`,
    s.service
      ? `Owning service: ${s.service} (per-service isolation — no cross-service imports, no shared tables)`
      : '',
    s.summary ? `What this spec must cover:\n${s.summary}` : '',
    `Work within the repository at: ${s.repoPath || '(repo path not provided — author against the supplied context only)'}`,
    constraints && constraints.length
      ? `Architectural constraints (binding):\n${constraints.map((c, i) => `${i + 1}. ${c}`).join('\n')}`
      : 'Architectural constraints (binding): REST API v1 only (HTTP API v2 banned); aws-lambda-powertools only; events over Step Functions (Step Functions banned); spec-first OpenAPI.',
    trd ? `Upstream TRD / requirements packet:\n${JSON.stringify(trd, null, 2)}` : '',
  ]
    .filter(Boolean)
    .join('\n\n')
}

function findingsText(review) {
  if (!review || !Array.isArray(review.findings) || !review.findings.length) {
    return review && review.feedback ? review.feedback : '(no specific findings recorded)'
  }
  const lines = review.findings.map(
    (f, i) => `${i + 1}. [${f.severity}] ${f.detail}${f.location ? ` (at ${f.location})` : ''}`
  )
  return `${review.feedback ? review.feedback + '\n' : ''}${lines.join('\n')}`
}

async function main(a) {
  const s = (a && a.spec) || {}
  const trd = a && a.trd
  const constraints = Array.isArray(a && a.constraints) ? a.constraints : []
  const accessPatterns = Array.isArray(a && a.accessPatterns) ? a.accessPatterns : []
  const MAX_LOOPS = (a && a.maxLoops) || 2
  const ctx = ctxBlock(s, trd, constraints)

  // ── Phase 1: Author specs (makers, in parallel) ───────────────────────────────
  phase('Author specs')

  const authored = await parallel({
    apiSpec: () =>
      agent(
        `Author the API/OpenAPI contract specification for this feature (spec-first). REST API v1 only — HTTP API v2 is banned. Define resources, methods, request/response schemas, status codes, and auth. Author only — do not review your own work.\n\n${ctx}`,
        {
          label: 'author:api-spec',
          phase: 'Author specs',
          agentType: 'agent-teams-workforce:api-specification-author',
          schema: SPEC_SCHEMA,
        }
      ),
    dataModelSpec: () =>
      agent(
        `Author the data-model specification for this feature. Per-service DynamoDB design (no tables shared across services). Define tables, keys, indexes, and item shapes that satisfy every access pattern below. Author only — do not review your own work.\n\nKnown access patterns:\n${accessPatterns.length ? accessPatterns.map((p, i) => `${i + 1}. ${p}`).join('\n') : '(derive the access patterns from the spec context)'}\n\n${ctx}`,
        {
          label: 'author:data-model',
          phase: 'Author specs',
          agentType: 'agent-teams-workforce:data-model-specification-author',
          schema: SPEC_SCHEMA,
        }
      ),
    eventContracts: () =>
      agent(
        `Author the event contracts/schemas for this feature. Use dot-form event naming and the standard event envelope. Events (not Step Functions) carry every orchestration/scheduling case. Define each event's name, envelope, and payload schema. Author only — do not review your own work.\n\n${ctx}`,
        {
          label: 'author:event-contracts',
          phase: 'Author specs',
          agentType: 'agent-teams-workforce:event-contract-author',
          schema: SPEC_SCHEMA,
        }
      ),
    errorSpec: () =>
      agent(
        `Author the error-handling specification for this feature: error taxonomy, error responses (aligned to the REST v1 API), retry/backoff and idempotency expectations, and how failures surface (errors stay visible — never silently swallowed). Author only — do not review your own work.\n\n${ctx}`,
        {
          label: 'author:error-spec',
          phase: 'Author specs',
          agentType: 'agent-teams-workforce:error-handling-specification-author',
          schema: SPEC_SCHEMA,
        }
      ),
    acceptance: () =>
      agent(
        `Author the acceptance criteria for this spec as testable given/when/then statements covering the happy path, error paths, and boundary conditions. Author only — do not review your own work.\n\n${ctx}`,
        {
          label: 'author:acceptance-criteria',
          phase: 'Author specs',
          agentType: 'agent-teams-workforce:acceptance-criteria-writer',
          schema: AC_SCHEMA,
        }
      ),
    dod: () =>
      agent(
        `Codify the Definition of Done for this spec as a concrete, verifiable checklist (spec-first OpenAPI present, schemas typed at boundaries, tests defined, docs current, etc.). Author only — do not review your own work.\n\n${ctx}`,
        {
          label: 'author:definition-of-done',
          phase: 'Author specs',
          agentType: 'agent-teams-workforce:definition-of-done-enforcer',
          schema: DOD_SCHEMA,
        }
      ),
  })

  // ── Phase 2 & 3: independent review + bounded maker/checker loop + decider ──────
  phase('Review specs')

  // One reviewable artifact = { key, makerType, reviewerType, makerSchema, draft, prompts }.
  // makerType !== reviewerType for every entry (no self-approval).
  const reviewables = [
    {
      key: 'apiSpec',
      reviewerType: 'agent-teams-workforce:openapi-contract-reviewer',
      makerType: 'agent-teams-workforce:api-specification-author',
      makerLabel: 'author:api-spec',
      reviewLabel: 'review:api-spec',
      makerSchema: SPEC_SCHEMA,
      draft: authored.apiSpec,
      reviewPrompt: (draft) =>
        `Independently review this API/OpenAPI contract spec for correctness and design rules (REST v1 only, resource/method/schema/status-code/auth completeness, spec-first conformance). You did NOT author it. Verdict approve or reject with specific findings.\n\nSpec under review:\n${JSON.stringify(draft, null, 2)}\n\n${ctx}`,
      makerPrompt: (feedback) =>
        `Revise the API/OpenAPI contract spec to resolve the reviewer's findings. REST API v1 only. Author only.\n\nReviewer findings to address:\n${feedback}\n\n${ctx}`,
    },
    {
      key: 'dataModelSpec',
      reviewerType: 'agent-teams-workforce:dynamodb-schema-access-pattern-reviewer',
      makerType: 'agent-teams-workforce:data-model-specification-author',
      makerLabel: 'author:data-model',
      reviewLabel: 'review:data-model',
      makerSchema: SPEC_SCHEMA,
      draft: authored.dataModelSpec,
      reviewPrompt: (draft) =>
        `Independently review this data-model spec against its access patterns: does every key/index/item shape serve a stated pattern with no hot keys, no cross-service table sharing, and no unsupported pattern? You did NOT author it. Verdict approve or reject with specific findings.\n\nAccess patterns:\n${accessPatterns.length ? accessPatterns.map((p, i) => `${i + 1}. ${p}`).join('\n') : '(as defined in the spec)'}\n\nSpec under review:\n${JSON.stringify(draft, null, 2)}\n\n${ctx}`,
      makerPrompt: (feedback) =>
        `Revise the data-model spec to resolve the reviewer's findings. Per-service isolation; serve every access pattern. Author only.\n\nReviewer findings to address:\n${feedback}\n\n${ctx}`,
    },
    {
      key: 'eventContracts',
      reviewerType: 'agent-teams-workforce:event-schema-reviewer',
      makerType: 'agent-teams-workforce:event-contract-author',
      makerLabel: 'author:event-contracts',
      reviewLabel: 'review:event-contracts',
      makerSchema: SPEC_SCHEMA,
      draft: authored.eventContracts,
      reviewPrompt: (draft) =>
        `Independently review these event schemas: dot-form naming, standard envelope conformance, payload schema completeness and versioning, and that orchestration uses events (not Step Functions). You did NOT author them. Verdict approve or reject with specific findings.\n\nEvent contracts under review:\n${JSON.stringify(draft, null, 2)}\n\n${ctx}`,
      makerPrompt: (feedback) =>
        `Revise the event contracts to resolve the reviewer's findings. Dot-form naming, standard envelope, events over Step Functions. Author only.\n\nReviewer findings to address:\n${feedback}\n\n${ctx}`,
    },
    {
      key: 'acceptance',
      reviewerType: 'agent-teams-workforce:acceptance-criteria-reviewer',
      makerType: 'agent-teams-workforce:acceptance-criteria-writer',
      makerLabel: 'author:acceptance-criteria',
      reviewLabel: 'review:acceptance-criteria',
      makerSchema: AC_SCHEMA,
      draft: authored.acceptance,
      reviewPrompt: (draft) =>
        `Independently review these acceptance criteria for testability and coverage: each is unambiguous given/when/then, the happy path, error paths, and boundaries are all covered, and nothing is unverifiable. You did NOT author them. Verdict approve or reject with specific findings.\n\nAcceptance criteria under review:\n${JSON.stringify(draft, null, 2)}\n\n${ctx}`,
      makerPrompt: (feedback) =>
        `Revise the acceptance criteria to resolve the reviewer's findings. Testable given/when/then; cover happy path, errors, boundaries. Author only.\n\nReviewer findings to address:\n${feedback}\n\n${ctx}`,
    },
  ]

  const reviewFindings = {}
  const finalArtifacts = {}

  for (const r of reviewables) {
    let draft = r.draft
    let lastReview = null
    let resolved = false

    for (let attempt = 1; attempt <= MAX_LOOPS; attempt++) {
      const review = await agent(r.reviewPrompt(draft), {
        label: r.reviewLabel,
        phase: 'Review specs',
        agentType: r.reviewerType,
        schema: REVIEW_SCHEMA,
      })
      lastReview = review

      if (review && review.verdict === 'approve') {
        resolved = true
        break
      }

      log(`Review ${r.key}: REJECT (attempt ${attempt}/${MAX_LOOPS}) — ${findingsText(review)}`)

      // Last attempt: do not re-run the maker; fall through to the decider.
      if (attempt === MAX_LOOPS) break

      // Re-run the MAKER (never the reviewer) with the reviewer's feedback.
      draft = await agent(r.makerPrompt(findingsText(review)), {
        label: r.makerLabel,
        phase: 'Author specs',
        agentType: r.makerType,
        schema: r.makerSchema,
      })
    }

    finalArtifacts[r.key] = draft
    reviewFindings[r.key] = {
      resolved,
      verdict: lastReview ? lastReview.verdict : 'reject',
      findings: lastReview ? lastReview.findings : [],
      feedback: lastReview ? lastReview.feedback : '',
    }
  }

  // ── Phase 3: Decide — break any deadlock the bounded loop could not resolve ─────
  phase('Decide')

  const deadlocked = reviewables.map((r) => r.key).filter((k) => !reviewFindings[k].resolved)

  let decision = null
  if (deadlocked.length) {
    log(
      `spec-authoring: ${deadlocked.length} artifact(s) deadlocked after ${MAX_LOOPS} passes — escalating to spec-decider`
    )
    decision = await agent(
      `A maker/checker loop reached its retry limit without agreement on one or more spec artifacts. You only RULE — you do not author or re-review. For each deadlocked artifact below, rule: accept-maker, accept-reviewer, or revise (with a precise directive).\n\nDeadlocked artifacts and their latest review:\n${deadlocked
        .map(
          (k) =>
            `── ${k} ──\nLatest verdict: ${reviewFindings[k].verdict}\nFindings:\n${findingsText(reviewFindings[k])}\nCurrent draft:\n${JSON.stringify(finalArtifacts[k], null, 2)}`
        )
        .join('\n\n')}\n\n${ctx}`,
      {
        label: 'decide:spec-decider',
        phase: 'Decide',
        agentType: 'agent-teams-workforce:spec-decider',
        schema: DECISION_SCHEMA,
      }
    )
  }

  // ── Return: one object threading every phase output ───────────────────────────
  const allResolved = deadlocked.length === 0
  return {
    ok: allResolved || (decision && decision.ruling !== 'revise'),
    spec: {
      id: s.id || null,
      title: s.title || null,
      service: s.service || null,
      repoPath: s.repoPath || null,
    },
    apiSpec: finalArtifacts.apiSpec,
    dataModelSpec: finalArtifacts.dataModelSpec,
    eventContracts: finalArtifacts.eventContracts,
    errorSpec: authored.errorSpec,
    acceptanceCriteria: finalArtifacts.acceptance,
    definitionOfDone: authored.dod,
    reviewFindings,
    decision,
    note:
      'errorSpec and definitionOfDone have no dedicated peer reviewer in this mini; they are carried to the downstream phase gate for acceptance. No maker judged its own work; the spec-decider only ruled on deadlocks.',
  }
}

await main(typeof args === 'string' ? JSON.parse(args) : (args || {}))
