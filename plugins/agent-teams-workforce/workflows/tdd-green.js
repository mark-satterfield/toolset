export const meta = {
  name: 'tdd-green',
  description:
    'Shared-tail mini — TDD Green. A read-only implementation-lead selects the implementer(s) matching the affected subsystem (unless the caller pre-specifies one); the selected implementers write the minimum production code in sequence to make the failing test pass, run the suite, and confirm Green without regressing other tests. Every implementer receives the contract as pointers to the documents that hold it — the work item and its description, the spec documents and sections, the requirement ids, the SAD decision ids the work was designed against, the Definition of Done and the acceptance criteria — so it builds the design the spec rules rather than inferring one from the failing test.',
  phases: [{ title: 'Green', detail: 'minimum code to pass; confirm Green' }],
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
    // A caller that owns its own failure reporting asks for the throw back, so the real
    // reason reaches its catch instead of being flattened to "returned no result".
    if (o.rethrow) throw err
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

// The implementer roster this mini may dispatch. Every name the lead returns is
// filtered against this list before it becomes an agentType — an unfiltered name
// would dispatch a nonexistent agent type in the phase that writes production
// code. Mirrors OPTIMIZER_ROSTER in tdd-refactor.js.
const IMPLEMENTER_ROSTER = [
  'chassis-extension-implementer',
  'power-tools-configuration-implementer',
  'api-gateway-cdk-implementer',
  'event-api-client-implementer',
  'event-driven-consumer-implementer',
  'dynamodb-access-layer-implementer',
  'cognito-lambda-trigger-implementer',
  'webauthn-implementer',
  'payments-integration-implementer',
  'email-notification-implementer',
  'mcp-server-implementer',
  'bedrock-integration-implementer',
  'matching-algorithm-implementer',
  'recommendation-engine-implementer',
  'vector-search-embeddings-implementer',
  'behavioral-signals-implementer',
  'llm-observability-implementer',
  'nextjs-component-implementer',
  'appsync-client-subscription-implementer',
  'ios-swiftui-implementer',
  'android-compose-implementer',
  'react-native-implementer',
  'appsync-cdk-implementer',
  'glue-etl-implementer',
  'kinesis-stream-implementer',
  'dynamodb-streams-cdc-implementer',
  's3-data-lake-implementer',
  'athena-redshift-analytics-implementer',
  // Selected by the infra path, which pre-specifies args.implementer.
  'cdk-stack-author',
]

// args: { contract, red, implementer?, feedback? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const red = a.red || {}
// ── PATH SAFETY AT THIS MINI'S OWN BOUNDARY ─────────────────────────────────
//
// The contract repo path is interpolated below into `git -C "<path>"` command text inside
// prompts that agents are told to run exactly as written, and into the prompt PROSE those
// same agents read. Inside a composite the value arrives already validated by the
// workspace step — but this mini is separately dispatchable, and a contract handed
// straight to it has been through no workspace step at all. Then the unvalidated value is
// back, in the phases that WRITE CODE and DEPLOY.
//
// This is the argument 6.0.8 used to justify re-validating inside settle rather than
// trusting the composite, applied where it was left out. A guard that only exists on the
// composite path is a guard on one of the two ways in.
//
// The rule matches the workspace step's: an ALLOWLIST, not a blocklist of shell
// metacharacters. The target is a model reading a prompt as well as a shell parsing a
// line, and a path made only of permitted characters can still be a sentence addressed to
// the reader. No spaces and no colons — a worktree path this pipeline creates needs
// neither, and prose needs both. REFUSE, never sanitize: a rewritten path names a
// different tree and nobody would learn of the substitution.
//
// An ABSENT path is not a fault. It has always meant "no tree was established", the
// placeholder below is not attacker-controlled, and turning that into a refusal would
// change what this mini does rather than what it accepts.
const CONTRACT_PATH_SHAPE = /^\/[A-Za-z0-9._/-]+$/
const suppliedRepoPath = String(c.repoPath || (c.bead && c.bead.repoPath) || '').trim()
const contractPathFault = (() => {
  if (!suppliedRepoPath) return null
  if (!CONTRACT_PATH_SHAPE.test(suppliedRepoPath)) {
    const offending = Array.from(suppliedRepoPath).find((ch) => !/[A-Za-z0-9._/-]/.test(ch))
    return (
      `the contract repoPath ${JSON.stringify(suppliedRepoPath)} ` +
      (suppliedRepoPath.startsWith('/')
        ? `contains ${JSON.stringify(offending)}, which either reshapes the commands an agent is told to run verbatim or lets the path be read as a sentence addressed to that agent`
        : 'is not absolute, and every command in this phase runs as `git -C "<path>"`, which resolves a relative path against whatever tree the agent is standing in')
    )
  }
  if (suppliedRepoPath.includes('//') || suppliedRepoPath.endsWith('/')) {
    return `the contract repoPath ${JSON.stringify(suppliedRepoPath)} has an empty or trailing path segment; it is refused rather than normalized`
  }
  if (suppliedRepoPath.split('/').includes('..')) {
    return `the contract repoPath ${JSON.stringify(suppliedRepoPath)} contains a ".." segment, so the directory it names is not the directory it reads as`
  }
  return null
})()
if (contractPathFault) {
  return {
    ok: false,
    greenConfirmed: false,
    changedFiles: [],
    blocked: [
      `${contractPathFault}. This phase refuses the contract rather than dispatching it: the path would ` +
        'already be inside the prompt by the time anyone could object.',
    ],
    ledger: { phase: 'green', beadId: (c.bead && c.bead.id) || null, chosen: [], mode: 'refused', ok: false },
  }
}

const repo = suppliedRepoPath || '(repo path not provided)'

// ── THE CONTRACT EVERY IMPLEMENTER RECEIVES ──────────────────────────────────────
//
// The failing test says what must pass; the contract says what must be BUILT. The design —
// the spec documents, the sections defining this work, the Definition of Done, and the SAD
// decisions the work was designed against — is ruled upstream and travels on the contract.
// It is rendered here as pointers to the documents that hold it, the same way tdd-red hands
// it to the test writers, so the implementer reads the design rather than inferring it from
// the shape of a test.
//
// Acceptance criteria arrive in two shapes: `{ given, when, then }` objects from bug triage,
// and prose strings from a Task's spec. Each renders as itself.
const str = (v) => (typeof v === 'string' && v.trim() ? v.trim() : '')
const strList = (v) => (Array.isArray(v) ? v.map((x) => str(x)).filter(Boolean) : [])
const isBugContract = !!(c.reproduction || c.rootCause)
const beadDescription = c.bead ? str(c.bead.description) : ''
const ac = Array.isArray(c.acceptanceCriteria) ? c.acceptanceCriteria : []
const acLine = (x, i) => {
  if (typeof x === 'string') return `${i + 1}. ${x.trim()}`
  if (x && typeof x === 'object' && (x.given || x.when || x.then)) {
    return `${i + 1}. GIVEN ${x.given || 'n/a'} WHEN ${x.when || 'n/a'} THEN ${x.then || 'n/a'}`
  }
  return `${i + 1}. ${JSON.stringify(x)}`
}
const decisionIds = [...new Set([...strList(c.decisionIds), ...strList(c.spec && c.spec.decisionIds)])]
const specBlock = (() => {
  const s = c.spec && typeof c.spec === 'object' ? c.spec : null
  const docs = s ? [...new Set([str(s.specPath), ...strList(s.specPaths)].filter(Boolean))] : []
  const lines = [
    docs.length
      ? `Spec documents — THE CONTRACT. Read the sections named below in these files before writing code; this prompt is a pointer to them, not a substitute for them:\n${docs.map((d) => `  - ${d}`).join('\n')}`
      : '',
    s && strList(s.specSections).length ? `Spec sections defining this work: ${strList(s.specSections).join(', ')}` : '',
    s && strList(s.requirementIds).length ? `Requirements satisfied: ${strList(s.requirementIds).join(', ')}` : '',
    decisionIds.length
      ? `Architecture decisions this work is designed against (SAD entry ids, cited by the spec documents): ${decisionIds.join(', ')}. The design they rule binds this change; where the spec cites one, build to it.`
      : '',
    s && strList(s.definitionOfDone).length ? `Definition of Done:\n${strList(s.definitionOfDone).map((d) => `  - ${d}`).join('\n')}` : '',
  ].filter(Boolean)
  return lines.length ? `\n\n${lines.join('\n')}` : ''
})()

const taskBlock = `${c.bead ? `${isBugContract ? 'Bug' : 'Task'} ${c.bead.id || ''}: ${c.bead.title || ''}` : 'Feature implementation'}${
  beadDescription ? `\n\n${beadDescription}` : ''
}${isBugContract ? `\n\nReproduction: ${c.reproduction || 'n/a'}\nRoot cause: ${c.rootCause || 'n/a'}` : ''}${specBlock}

Affected files: ${(c.affectedFiles || []).join(', ') || 'n/a'}
${ac.length ? `\nAcceptance criteria this change satisfies:\n${ac.map(acLine).join('\n')}\n` : ''}
Failing test(s) to satisfy: ${(red.testFiles || []).join(', ') || 'n/a'}
Red evidence: ${red.evidence || 'n/a'}`

phase('Green')

// implementation-lead SELECTS the implementer(s) whose specialty matches the affected
// subsystem — a READ-ONLY router that writes no code. A caller may pre-specify
// args.implementer to skip selection (e.g. the infra path fixes 'cdk-stack-author').
let implementers
let selectionMode
if (a.implementer) {
  if (!IMPLEMENTER_ROSTER.includes(a.implementer)) {
    throw new Error(
      `tdd-green: caller pre-specified implementer '${a.implementer}', which is not on the implementer roster. ` +
        `Dispatching it would resolve to a nonexistent agent type. Roster: ${IMPLEMENTER_ROSTER.join(', ')}`
    )
  }
  implementers = [a.implementer]
  selectionMode = 'selected'
} else {
  const selection = await settleAgent(
    `You are the implementation-lead — a READ-ONLY router. Do NOT write code. Select the FEWEST implementer agent(s) whose specialty covers this change, drawn ONLY from the implementer roster: ${IMPLEMENTER_ROSTER.join(', ')}. Any name outside this list is discarded. A standard Python-Lambda service change is chassis-extension-implementer alone. Order them so earlier ones lay groundwork for later ones.

Work within the repository at: ${repo}

PIN YOURSELF TO THE RIGHT TREE FIRST. You may be running in an isolation worktree, so a bare \`git status\`, a relative path, or an editor's idea of the project root can inspect — or WRITE TO — the wrong copy of the repository. Every file you create or modify is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}

${taskBlock}`,
    {
      label: 'green:select-implementers',
      effort: 'low',
      phase: 'Green',
      agentType: 'agent-teams-workforce:implementation-lead',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['implementers', 'rationale'],
        properties: {
          implementers: { type: 'array', items: { type: 'string' } },
          rationale: { type: 'string' },
        },
      },
    }
  )
  const picked =
    selection && Array.isArray(selection.implementers)
      ? selection.implementers.filter((i) => IMPLEMENTER_ROSTER.includes(i))
      : []
  implementers = picked.length ? picked : ['chassis-extension-implementer']
  selectionMode = picked.length ? 'selected' : 'default'
}

const GREEN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['changedFiles', 'greenConfirmed', 'evidence'],
  properties: {
    changedFiles: { type: 'array', items: { type: 'string' } },
    greenConfirmed: { type: 'boolean' },
    evidence: { type: 'string' },
    // ── THE CONTRADICTION CHANNEL ────────────────────────────────────────────
    // An implementer can be blocked by something no amount of implementation fixes:
    // the failing test asserts one outcome for an input, and ANOTHER test — already
    // passing — asserts the opposite outcome for the identical input. Nobody in the
    // pipeline could act on that. This implementer may not modify a test, the gate is
    // right to fail a test that does not pass, and re-authoring only regenerates one
    // side of the disagreement. Without somewhere to SAY it, the observation was lost
    // and the run deadlocked until a human read the logs.
    //
    // It is deliberately a structured field rather than prose in `notes`: the caller
    // routes it to the test-strategy-decider, which needs both tests and the GIVEN
    // they share to rule which contract binds.
    contradiction: {
      type: 'object',
      additionalProperties: false,
      required: ['testA', 'testB', 'sharedGiven', 'evidence'],
      properties: {
        testA: { type: 'string' },
        testB: { type: 'string' },
        sharedGiven: { type: 'string' },
        expectedA: { type: 'string' },
        expectedB: { type: 'string' },
        evidence: { type: 'string' },
      },
    },
    notes: { type: 'string' },
  },
}

// Run the selected implementer(s) in sequence — each builds on the prior's changes so
// they never edit the same files concurrently. The final pass confirms the suite is Green.
let green = null
const changedFiles = []
// The FIRST contradiction any implementer reports, kept separately. Only the LAST
// implementer's result is spread into the return below, so a contradiction observed by an
// earlier one in the sequence would otherwise be dropped — and it is the one finding in
// this phase that nothing downstream can rediscover.
let contradiction = null
for (const impl of implementers) {
  green = await settleAgent(
    `Make the failing test pass with the MINIMUM production change. Then run the test suite and confirm the target test passes (Green) and nothing else regressed. Work within the repository at: ${repo}

PIN YOURSELF TO THE RIGHT TREE FIRST. You may be running in an isolation worktree, so a bare \`git status\`, a relative path, or an editor's idea of the project root can inspect — or WRITE TO — the wrong copy of the repository. Every file you create or modify is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}

${taskBlock}${implementers.length > 1 ? `\n\nYou are '${impl}', one of ${implementers.length} implementers on this task — make only the part matching your specialty; prior implementers' changes are already applied.` : ''}
${a.feedback ? `\nGate feedback from the previous attempt — address it:\n${a.feedback}` : ''}

IF TWO TESTS CONTRADICT EACH OTHER, REPORT IT — do not pick a side and do not keep trying. There is one blocker you cannot fix and must not attempt to: the failing test requires one outcome for an input, and another test that ALREADY PASSES requires the opposite outcome for that identical input. No implementation satisfies both, so every further attempt re-proves the same impossibility. You may not modify a test, and neither may the gate, so the only correct move is to say so: fill in \`contradiction\` with both test identifiers, the precondition they share, what each one expects, and the executed output showing they cannot both hold. Which contract is right is not yours to decide — it is ruled by an agent with that authority, and your report is what reaches it. Report a contradiction ONLY for genuinely opposite expectations over the same input; a test that is merely wrong on its own terms is a defective test, which you report in your evidence as usual.

Constraints: minimum change to pass; build to the contract above; do not modify the test to make it pass. Deliver the changed files, whether Green is confirmed, and the captured passing output.`,
    {
      label: `green:${impl}`,
      phase: 'Green',
      agentType: `agent-teams-workforce:${impl}`,
      schema: GREEN_SCHEMA,
    }
  )
  if (green && Array.isArray(green.changedFiles)) changedFiles.push(...green.changedFiles)
  if (!contradiction && green && green.contradiction && green.contradiction.testA && green.contradiction.testB) {
    contradiction = green.contradiction
    log(`Green: '${impl}' reports a test contradiction — ${contradiction.testA} and ${contradiction.testB} assert opposite outcomes for the same input`)
  }
}

// Decision ledger — what this phase actually did, for over-time mining.
// mode 'selected' = implementation-lead (or the caller) chose the implementer(s);
// mode 'default'  = selection produced nothing and the mini fell back to the chassis default.
const ledger = {
  phase: 'green',
  beadId: (c.bead && c.bead.id) || null,
  chosen: implementers,
  mode: selectionMode,
  ok: !!(green && green.greenConfirmed),
  contradiction: !!contradiction,
}

return { ...(green || {}), changedFiles, contradiction, ledger }
