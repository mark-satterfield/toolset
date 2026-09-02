export const meta = {
  name: 'spec-authoring',
  description:
    'Leaf mini — Spec authoring. Turns an approved requirements/TRD packet into the implementation-ready specification set: the API/OpenAPI contract, the per-service data model, the event contracts, the error-handling spec, the acceptance criteria, and the Definition of Done. A Spec and its Story are created together, so this mini also emits exactly ONE Story bead specification paired with the Spec — a container scoped to the single repo in args.repoPath, with no task breakdown and no WSJF score; work the spec set implies in any other repo is returned as a finding, never a second Story (the caller runs this mini once per repo and writes the bead with bd). Three maker sessions author the six artifacts in parallel (interface contracts, data model, criteria); ONE INDEPENDENT reviewer session judges the reviewable artifacts through every review lens (segregation of duties — no author reviews its own work, and merging checks into one checker session never merges a maker with its checker); a bounded maker/checker loop re-runs only the owning maker on rejection and the spec-decider breaks any deadlock. Read-and-author only — no nested workflow(); the downstream gate owns final acceptance.',
  phases: [
    { title: 'Author specs', detail: 'three maker sessions author the six spec artifacts in parallel' },
    { title: 'Review specs', detail: 'one independent reviewer session judges the reviewable artifacts' },
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
//     type:          'story',  // literal — the bead face of the Spec; a container, never worked (its SPEC is what decomposes)
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
  const MAX_LOOPS = (a && a.maxLoops) || 1
  const ctx = ctxBlock(s, trd, constraints)

  // ── Phase 1: Author specs — THREE maker sessions, six artifacts ───────────────
  // The six artifacts used to be six parallel maker sessions, each paying a full
  // session-start to read the same TRD packet and the same repo. Merging MAKERS
  // costs no segregation of duties — no maker judges anything here, and the
  // independent review below still covers everything — so related artifacts are
  // authored together: the interface contracts in one session (API + events +
  // errors, one behavioural surface), the data model in its own specialist
  // session, and the criteria (AC + DoD) in one small session.
  phase('Author specs')

  const CONTRACTS_SCHEMA = {
    type: 'object',
    additionalProperties: false,
    required: ['apiSpec', 'eventContracts', 'errorSpec'],
    properties: {
      apiSpec: SPEC_SCHEMA,
      eventContracts: SPEC_SCHEMA,
      errorSpec: SPEC_SCHEMA,
    },
  }
  const CRITERIA_SCHEMA = {
    type: 'object',
    additionalProperties: false,
    required: ['acceptanceCriteria', 'definitionOfDone'],
    properties: {
      acceptanceCriteria: AC_SCHEMA.properties.acceptanceCriteria,
      definitionOfDone: DOD_SCHEMA.properties.definitionOfDone,
      notes: { type: 'string' },
    },
  }

  // parallel() takes an ARRAY of thunks — that is the runner's contract and what
  // every other workflow in this directory passes. An object map is iterated as
  // an empty list, so all the specs would come back undefined.
  const [contractsDraft, dataModelSpecDraft, criteriaDraft] = await parallel([
    () =>
      agent(
        `Author the three INTERFACE CONTRACT artifacts for this feature, each under its own key. Author only — do not review your own work.

1. \`apiSpec\` — the API/OpenAPI contract specification (spec-first). REST API v1 only — HTTP API v2 is banned. Define resources, methods, request/response schemas, status codes, and auth.
2. \`eventContracts\` — the event contracts/schemas. Dot-form event naming and the standard event envelope. Events (not Step Functions) carry every orchestration/scheduling case. Define each event's name, envelope, and payload schema.
3. \`errorSpec\` — the error-handling specification: error taxonomy, error responses (aligned to the REST v1 API), retry/backoff and idempotency expectations, and how failures surface (errors stay visible — never silently swallowed).

${ctx}`,
        {
          label: 'author:contracts',
          phase: 'Author specs',
          agentType: 'agent-teams-workforce:api-specification-author',
          schema: CONTRACTS_SCHEMA,
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
        `Author two small artifacts for this spec, each under its own key. Author only — do not review your own work.

1. \`acceptanceCriteria\` — testable given/when/then statements covering the happy path, error paths, and boundary conditions.
2. \`definitionOfDone\` — a concrete, verifiable checklist (spec-first OpenAPI present, schemas typed at boundaries, tests defined, docs current, etc.).

${ctx}`,
        {
          label: 'author:criteria',
          phase: 'Author specs',
          agentType: 'agent-teams-workforce:acceptance-criteria-writer',
          schema: CRITERIA_SCHEMA,
        }
      ),
  ])
  const authored = {
    apiSpec: contractsDraft && contractsDraft.apiSpec,
    dataModelSpec: dataModelSpecDraft,
    eventContracts: contractsDraft && contractsDraft.eventContracts,
    errorSpec: contractsDraft && contractsDraft.errorSpec,
    acceptance: criteriaDraft
      ? { acceptanceCriteria: criteriaDraft.acceptanceCriteria, notes: criteriaDraft.notes }
      : null,
    dod: criteriaDraft ? { definitionOfDone: criteriaDraft.definitionOfDone, notes: criteriaDraft.notes } : null,
  }

  // ── Phase 2 & 3: ONE independent reviewer session + bounded maker re-runs ──────
  // The four reviewable artifacts used to get four separate reviewer sessions per
  // attempt — four session-starts to judge one spec set. All four reviews are CHECKS
  // on maker output, and the reviewer authored none of it, so one session applying
  // all four review lenses preserves segregation of duties (never a maker checking
  // itself) at a quarter of the cost. On rejection only the owning MAKER re-runs
  // (never the reviewer), and only the rejected artifacts are replaced.
  phase('Review specs')

  const REVIEW_KEYS = ['apiSpec', 'dataModelSpec', 'eventContracts', 'acceptance']
  const drafts = {
    apiSpec: authored.apiSpec,
    dataModelSpec: authored.dataModelSpec,
    eventContracts: authored.eventContracts,
    acceptance: authored.acceptance,
  }
  const reviewFindings = {}
  let lastReviews = {}

  for (let attempt = 1; attempt <= MAX_LOOPS; attempt++) {
    const review = await agent(
      `You are an INDEPENDENT spec reviewer. You did NOT author any artifact below; you only judge them. Review all four in one pass, returning a verdict per artifact under its own key. Keep every finding under 40 words — findings, not essays.

1. \`apiSpec\` — the API/OpenAPI contract: correctness and design rules (REST v1 only, resource/method/schema/status-code/auth completeness, spec-first conformance).
2. \`dataModelSpec\` — the data model against its access patterns: does every key/index/item shape serve a stated pattern with no hot keys, no cross-service table sharing, and no unsupported pattern?
   Access patterns:\n${accessPatterns.length ? accessPatterns.map((p, i) => `   ${i + 1}. ${p}`).join('\n') : '   (as defined in the spec)'}
3. \`eventContracts\` — the event schemas: dot-form naming, standard envelope conformance, payload schema completeness and versioning, and that orchestration uses events (not Step Functions).
4. \`acceptance\` — the acceptance criteria: each is unambiguous given/when/then; happy path, error paths, and boundaries are all covered; nothing is unverifiable.

Verdict approve or reject per artifact, with specific findings a maker can act on without interpretation.

Artifacts under review:
${JSON.stringify(drafts, null, 2)}

${ctx}`,
      {
        label: `review:all-specs${attempt > 1 ? `:${attempt}` : ''}`,
        phase: 'Review specs',
        agentType: 'agent-teams-workforce:api-design-reviewer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: REVIEW_KEYS,
          properties: {
            apiSpec: REVIEW_SCHEMA,
            dataModelSpec: REVIEW_SCHEMA,
            eventContracts: REVIEW_SCHEMA,
            acceptance: REVIEW_SCHEMA,
          },
        },
      }
    )
    lastReviews = review || {}
    const rejected = REVIEW_KEYS.filter((k) => !(review && review[k] && review[k].verdict === 'approve'))
    if (!rejected.length) break
    log(`Review: REJECT ${rejected.join(', ')} (attempt ${attempt}/${MAX_LOOPS})`)

    // Last attempt: do not re-run the makers; fall through to the decider.
    if (attempt === MAX_LOOPS) break

    // Re-run only the OWNING makers, and replace only the rejected artifacts.
    const contractRejects = rejected.filter((k) => k === 'apiSpec' || k === 'eventContracts')
    if (contractRejects.length) {
      const fb = contractRejects.map((k) => `${k}:\n${findingsText(lastReviews[k])}`).join('\n\n')
      const redone = await agent(
        `Revise the interface contract artifacts to resolve the reviewer's findings below, returning all three under their keys (apiSpec, eventContracts, errorSpec). REST API v1 only; dot-form event naming; events over Step Functions. Author only — do not review your own work.\n\nReviewer findings to address:\n${fb}\n\nCurrent drafts:\n${JSON.stringify({ apiSpec: drafts.apiSpec, eventContracts: drafts.eventContracts, errorSpec: authored.errorSpec }, null, 2)}\n\n${ctx}`,
        { label: 'author:contracts', phase: 'Author specs', agentType: 'agent-teams-workforce:api-specification-author', schema: CONTRACTS_SCHEMA }
      )
      for (const k of contractRejects) if (redone && redone[k]) drafts[k] = redone[k]
    }
    if (rejected.includes('dataModelSpec')) {
      drafts.dataModelSpec = await agent(
        `Revise the data-model spec to resolve the reviewer's findings. Per-service isolation; serve every access pattern. Author only.\n\nReviewer findings to address:\n${findingsText(lastReviews.dataModelSpec)}\n\n${ctx}`,
        { label: 'author:data-model', phase: 'Author specs', agentType: 'agent-teams-workforce:data-model-specification-author', schema: SPEC_SCHEMA }
      )
    }
    if (rejected.includes('acceptance')) {
      const redone = await agent(
        `Revise the acceptance criteria and Definition of Done to resolve the reviewer's findings. Testable given/when/then; cover happy path, errors, boundaries. Author only.\n\nReviewer findings to address:\n${findingsText(lastReviews.acceptance)}\n\n${ctx}`,
        { label: 'author:criteria', phase: 'Author specs', agentType: 'agent-teams-workforce:acceptance-criteria-writer', schema: CRITERIA_SCHEMA }
      )
      if (redone) {
        drafts.acceptance = { acceptanceCriteria: redone.acceptanceCriteria, notes: redone.notes }
        authored.dod = { definitionOfDone: redone.definitionOfDone, notes: redone.notes }
      }
    }
  }

  const finalArtifacts = {}
  for (const k of REVIEW_KEYS) {
    const r = lastReviews[k]
    finalArtifacts[k] = drafts[k]
    reviewFindings[k] = {
      resolved: !!(r && r.verdict === 'approve'),
      verdict: r ? r.verdict : 'reject',
      findings: r ? r.findings : [],
      feedback: r ? r.feedback : '',
    }
  }
  const reviewables = REVIEW_KEYS.map((key) => ({ key }))

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
    `Author the Story bead this Spec pairs with. A Spec and its Story are created together, and a Story is scoped to a SINGLE repository — the one named below. Write a title and a description stating what this Story contains in terms of the authored spec set. The Story is a CONTAINER: it is never worked, and it is never itself decomposed — its SPEC is what decomposes into tasks downstream — do NOT include a task breakdown, a WSJF score, or any priority. If the spec set implies work in any OTHER repository, do not fold that work into this Story and do not mint a second story: report each such case in outOfRepoFindings instead (the caller runs this mini once per repo). Author only — do not review your own work.\n\nThis Story's single repository: ${repoPath || '(none supplied)'}\n\nAuthored spec set to summarize and scope-check:\n${JSON.stringify(specSet, null, 2)}\n\n${ctx}`,
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
