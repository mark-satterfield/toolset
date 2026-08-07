export const meta = {
  name: 'spec-authoring',
  description:
    'Leaf mini — Spec authoring. Turns an approved requirements/TRD packet into the implementation-ready specification set: the API/OpenAPI contract, the per-service data model, the event contracts, the error-handling spec, the acceptance criteria, and the Definition of Done. A Spec and its Story are created together, so this mini also emits exactly ONE Story bead specification paired with the Spec — a container scoped to the single repo in args.repoPath, with no task breakdown and no WSJF score; work the spec set implies in any other repo is returned as a finding, never a second Story (the caller runs this mini once per repo and writes the bead with bd). Maker agents author each artifact in parallel; INDEPENDENT reviewer agents judge the reviewable artifacts (segregation of duties — no author reviews its own work); a bounded maker/checker loop re-runs the maker on rejection and the spec-decider breaks any deadlock. Read-and-author only — no nested workflow(); the downstream gate owns final acceptance.',
  phases: [
    { title: 'Author specs', detail: 'makers author each spec artifact in parallel' },
    { title: 'Review specs', detail: 'independent reviewers judge the reviewable artifacts' },
    { title: 'Decide', detail: 'spec-decider breaks any maker/checker deadlock' },
    { title: 'Emit story', detail: 'author the ONE Story bead this Spec pairs with — container only, single repo' },
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
//   repoPath: string,             // the ONE repo this Spec/Story covers (required) — a Story is scoped to a single repo
//   storyKey?: string,            // key for the emitted Story (default 'S1'). The caller runs this
//                                 // mini once per repo and must give each Story a distinct key.
//   epic: { key?, id?, title? },  // the parent Epic the Story hangs under; missing -> Story emitted unparented
//   maxLoops?: number,            // bounded maker/checker retries per reviewable artifact (default 2)
// }
//
// returns { ok, story, spec, apiSpec, dataModelSpec, eventContracts, errorSpec,
// acceptanceCriteria, definitionOfDone, reviewFindings, decision, outOfRepoFindings, note }
// where story is the ONE Story bead specification this Spec pairs with (a Spec and its
// Story are created together; nothing here writes to .beads — the caller writes it with bd):
//   story: {
//     key:           string,   // stable local key ("S1") — parent links in the bead set are by key
//     type:          'story',  // literal — a Story is a container, never worked, only decomposed
//     title:         string,
//     description:   string,
//     repoPath:      string,   // the single repo this Story covers — copied from args.repoPath
//     parentEpicKey: string,   // epic.key || epic.id; null when no Epic was supplied
//   }
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

// The story maker returns only prose plus scope findings. Key, type, repoPath, and
// parentEpicKey are assembled deterministically below — an agent must never pick the
// repo the Story covers or the Epic it hangs under. outOfRepoFindings is required
// (empty when clean) so the maker always answers the single-repo scope question.
const STORY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['title', 'description', 'outOfRepoFindings'],
  properties: {
    title: { type: 'string' },
    description: { type: 'string' },
    outOfRepoFindings: { type: 'array', items: { type: 'string' } },
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
  // A Story is scoped to a single repo, so the repo is what makes it well-formed —
  // without one there is nothing to deploy, test, or own. Emitting a repo-less Story
  // that reads as valid downstream is worse than refusing: the caller writes it with
  // bd, its tasks inherit a parent that names no repo, and the defect only surfaces
  // when an implementer is handed work with nowhere to do it. The caller runs this
  // mini once per repo and always knows which one.
  const repoPath = (a && a.repoPath) || (s && s.repoPath) || null
  const epic = (a && a.epic) || null
  if (!repoPath) {
    return {
      ok: false,
      stage: 'story',
      reason:
        'no repoPath supplied — a Story is scoped to a single repo and cannot be emitted without one. Run this mini once per repo, passing args.repoPath each time.',
    }
  }
  const MAX_LOOPS = (a && a.maxLoops) || 2
  const ctx = ctxBlock(s, trd, constraints)

  // ── Phase 1: Author specs (makers, in parallel) ───────────────────────────────
  phase('Author specs')

  // parallel() takes an ARRAY of thunks — that is the runner's contract and what
  // every other workflow in this directory passes. An object map is iterated as
  // an empty list, so all six specs came back undefined.
  const [apiSpecDraft, dataModelSpecDraft, eventContractsDraft, errorSpecDraft, acceptanceDraft, dodDraft] =
    await parallel([
    () =>
      agent(
        `Author the API/OpenAPI contract specification for this feature (spec-first). REST API v1 only — HTTP API v2 is banned. Define resources, methods, request/response schemas, status codes, and auth. Author only — do not review your own work.\n\n${ctx}`,
        {
          label: 'author:api-spec',
          phase: 'Author specs',
          agentType: 'agent-teams-workforce:api-specification-author',
          schema: SPEC_SCHEMA,
        }
      ),
    () =>
      agent(
        `Author the data-model specification for this feature. Per-service DynamoDB design (no tables shared across services). Define tables, keys, indexes, and item shapes that satisfy every access pattern below. Author only — do not review your own work.\n\nKnown access patterns:\n${accessPatterns.length ? accessPatterns.map((p, i) => `${i + 1}. ${p}`).join('\n') : '(derive the access patterns from the spec context)'}\n\n${ctx}`,
        {
          label: 'author:data-model',
          phase: 'Author specs',
          agentType: 'agent-teams-workforce:data-model-specification-author',
          schema: SPEC_SCHEMA,
        }
      ),
    () =>
      agent(
        `Author the event contracts/schemas for this feature. Use dot-form event naming and the standard event envelope. Events (not Step Functions) carry every orchestration/scheduling case. Define each event's name, envelope, and payload schema. Author only — do not review your own work.\n\n${ctx}`,
        {
          label: 'author:event-contracts',
          phase: 'Author specs',
          agentType: 'agent-teams-workforce:event-contract-author',
          schema: SPEC_SCHEMA,
        }
      ),
    () =>
      agent(
        `Author the error-handling specification for this feature: error taxonomy, error responses (aligned to the REST v1 API), retry/backoff and idempotency expectations, and how failures surface (errors stay visible — never silently swallowed). Author only — do not review your own work.\n\n${ctx}`,
        {
          label: 'author:error-spec',
          phase: 'Author specs',
          agentType: 'agent-teams-workforce:error-handling-specification-author',
          schema: SPEC_SCHEMA,
        }
      ),
    () =>
      agent(
        `Author the acceptance criteria for this spec as testable given/when/then statements covering the happy path, error paths, and boundary conditions. Author only — do not review your own work.\n\n${ctx}`,
        {
          label: 'author:acceptance-criteria',
          phase: 'Author specs',
          agentType: 'agent-teams-workforce:acceptance-criteria-writer',
          schema: AC_SCHEMA,
        }
      ),
    () =>
      agent(
        `Codify the Definition of Done for this spec as a concrete, verifiable checklist (spec-first OpenAPI present, schemas typed at boundaries, tests defined, docs current, etc.). Author only — do not review your own work.\n\n${ctx}`,
        {
          label: 'author:definition-of-done',
          phase: 'Author specs',
          agentType: 'agent-teams-workforce:definition-of-done-enforcer',
          schema: DOD_SCHEMA,
        }
      ),
    ])
  const authored = {
    apiSpec: apiSpecDraft,
    dataModelSpec: dataModelSpecDraft,
    eventContracts: eventContractsDraft,
    errorSpec: errorSpecDraft,
    acceptance: acceptanceDraft,
    dod: dodDraft,
  }

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

  // ── Phase 4: Emit story — a Spec and its Story are created together ────────────
  phase('Emit story')

  if (!repoPath) {
    log(
      'spec-authoring: no repoPath supplied — a Story is scoped to a single repo, so the emitted Story carries repoPath null and downstream decomposition cannot scope its tasks'
    )
  }

  // Parent links are by key. An Epic is created with its PRD upstream of here; when
  // none was passed in we still emit the Story (unparented) so the Spec/Story pairing
  // holds, and the caller backfills the Epic and reparents before tasks can route.
  const parentEpicKey = (epic && (epic.key || epic.id)) || null
  if (!parentEpicKey) {
    log(
      'spec-authoring: no parent Epic supplied — the Story bead is emitted UNPARENTED (parentEpicKey null); backfill its Epic and reparent before its tasks can route as workable'
    )
  }

  const specSet = {
    apiSpec: finalArtifacts.apiSpec,
    dataModelSpec: finalArtifacts.dataModelSpec,
    eventContracts: finalArtifacts.eventContracts,
    errorSpec: authored.errorSpec,
    acceptanceCriteria: finalArtifacts.acceptance,
    definitionOfDone: authored.dod,
  }

  const storyDraft = await agent(
    `Author the Story bead this Spec pairs with. A Spec and its Story are created together, and a Story is scoped to a SINGLE repository — the one named below. Write a title and a description stating what this Story contains in terms of the authored spec set. The Story is a CONTAINER: it is never worked, only decomposed downstream — do NOT include a task breakdown, a WSJF score, or any priority. If the spec set implies work in any OTHER repository, do not fold that work into this Story and do not mint a second story: report each such case in outOfRepoFindings instead (the caller runs this mini once per repo). Author only — do not review your own work.\n\nThis Story's single repository: ${repoPath || '(none supplied)'}\n\nAuthored spec set to summarize and scope-check:\n${JSON.stringify(specSet, null, 2)}\n\n${ctx}`,
    {
      label: 'author:story-bead',
      phase: 'Emit story',
      agentType: 'agent-teams-workforce:user-story-writer',
      schema: STORY_SCHEMA,
    }
  )

  // Exactly ONE Story per invocation, so the local key is fixed. Key, type, repoPath,
  // and parentEpicKey are assembled here, not by the maker — the single-repo scope and
  // the Epic parentage are caller-supplied facts, never an agent's choice. Nothing
  // here writes to .beads; the caller writes the bead with bd, linking by key.
  // The caller runs this mini once per repo, so a hardcoded key would give every
  // Story in a multi-repo Epic the same one — collapsing the parent links and the
  // Story dependency graph onto a single phantom Story. The caller supplies the key
  // because only it knows how many repos the Epic spans; 'S1' is the single-repo
  // default.
  const story = {
    key: (a && a.storyKey) || 'S1',
    type: 'story',
    title: storyDraft.title,
    description: storyDraft.description,
    repoPath,
    parentEpicKey,
  }

  // ── Return: one object threading every phase output ───────────────────────────
  const allResolved = deadlocked.length === 0
  return {
    ok: allResolved || (decision && decision.ruling !== 'revise'),
    story,
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
    outOfRepoFindings: storyDraft.outOfRepoFindings || [],
    note:
      'errorSpec, definitionOfDone, and the story bead have no dedicated peer reviewer in this mini; they are carried to the downstream phase gate for acceptance. No maker judged its own work; the spec-decider only ruled on deadlocks. The story is a CONTAINER (no tasks, no WSJF) covering exactly one repo — outOfRepoFindings lists any work the spec set implies elsewhere; the caller runs this mini once per repo and writes the bead set with bd.',
  }
}

// Top-level return, as every sibling workflow does: the runner takes the script's
// completion value as the mini's result. `await main(...)` alone discarded it, so
// every caller — including prd-to-spec's per-repo Story collection — saw undefined.
return await main(typeof args === 'string' ? JSON.parse(args) : (args || {}))
