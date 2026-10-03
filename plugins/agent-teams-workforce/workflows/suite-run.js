export const meta = {
  name: 'suite-run',
  description:
    "Leaf mini — runs a repository's whole test suite once and reports what the run printed. One session runs exactly one command in the tree, followed by an echo of its exit status on a SUITE-EXIT line, and returns { exitCode, tail, failing, summary, command }; the exit code is read from that line in the verbatim tail, and a run whose output lacks it returns exitCode -1. Each failing entry is { kind: test | load, file, test, line }, whatever the test runner. The command is the caller's, or, when the caller names none, the one the repository itself declares: a test command stated in its AGENTS.md or CLAUDE.md, or the `test` task in its Taskfile. When the repository declares none it returns resolveError and runs nothing. Green means exitCode 0; the caller judges that, not the session.",
  phases: [{ title: 'Run', detail: 'runs the suite command once and reports its exit code and failures' }],
}
// BEGIN bounded dispatch policy — identical in workflow consumers (no runtime imports).
let dispatchInterruption = null
function dispatchOutcome(result) {
  if (!dispatchInterruption) return result
  const out = result && typeof result === 'object' ? result : {}
  return { ...out, ok: false, dispatchFailed: true, paused: true, resumable: true,
    stage: dispatchInterruption.stage, reason: dispatchInterruption.message, headline: dispatchInterruption.message,
    ...(typeof out.passed === 'boolean' ? { passed: false } : {}),
    ...(out.ledger ? { ledger: { ...out.ledger, ok: false } } : {}), dispatchInterruption }
}
function dispatchPolicy(options) {
  const input = (typeof args === 'string' ? JSON.parse(args) : args) || {}
  const policy = (options && options.retryPolicy) || input.retryPolicy || {}
  return { maxAttempts: Number.isInteger(policy.maxAttempts) && policy.maxAttempts > 0 ? policy.maxAttempts : 3,
    maxWaitMs: Number.isFinite(policy.maxWaitMs) && policy.maxWaitMs >= 0 ? policy.maxWaitMs : 300000 }
}
function dispatchFailureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = [e.message || err || '', e.type, e.code, e.error && e.error.type].join(' ')
  if (/structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i.test(text)) return 'deterministic'
  if (/insufficient_quota|quota|usage[ _-]?limit|spend[ _-]?limit|session[ _-]?limit|credit balance|out of credits|hit your limit|token limit|account.quota.exhausted/i.test(text)) return 'exhausted'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((value) => Number(value)).find((value) => Number.isFinite(value) && value >= 100 && value < 600)
  return [408, 425, 429, 500, 502, 503, 504, 529].includes(status) || /overload|rate[ _-]?limit|too many requests|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i.test(text) ? 'transient' : 'deterministic'
}
function dispatchRetry(err, name, attempt, waitedMs, policy, canWait) {
  const cause = dispatchFailureCause(err)
  if (cause === 'deterministic') return { retry: false, cause }
  const e = err && typeof err === 'object' ? err : {}
  const headers = e.headers || (e.response && e.response.headers) || {}
  const rawRetryAfter = e.retryAfter !== undefined ? e.retryAfter : headers['retry-after']
  const retryAfter = e.retryAfterMs !== undefined ? Number(e.retryAfterMs) : Number(rawRetryAfter) * 1000
  // An HTTP-date without a supplied clock cannot be safely shortened to our backoff.
  const unknownRetryDate = rawRetryAfter !== undefined && !Number.isFinite(retryAfter)
  let hash = 2166136261
  for (const ch of `${name}#${attempt}`) hash = Math.imul(hash ^ ch.charCodeAt(0), 16777619)
  const scheduled = Math.round(Math.min(300000, 5000 * Math.pow(3, attempt - 1)) * (0.5 + 0.5 * ((hash >>> 0) / 4294967296)))
  const wait = Math.max(scheduled, Number.isFinite(retryAfter) && retryAfter >= 0 ? retryAfter : 0)
  if (cause === 'transient' && !unknownRetryDate && canWait && attempt < policy.maxAttempts && waitedMs + wait <= policy.maxWaitMs) return { retry: true, cause, wait }
  const stage = cause === 'exhausted' ? 'account-quota-exhausted' : 'api-unavailable'
  return { retry: false, cause, interruption: { stage, message: `${stage}: ${name}: ${String(e.message || err || cause)}`, attempt,
    retryAfterMs: Number.isFinite(retryAfter) && retryAfter >= 0 ? retryAfter : null, retryAfter: rawRetryAfter || null } }
}
async function settleWorkflow(name, input) {
  if (dispatchInterruption) return dispatchOutcome({})
  const source = (typeof args === 'string' ? JSON.parse(args) : args) || {}
  try {
    const out = await workflow(name, { ...input, ...(source.retryPolicy && !(input && input.retryPolicy) ? { retryPolicy: source.retryPolicy } : {}) })
    if (out && out.paused && out.resumable && out.dispatchInterruption) dispatchInterruption = out.dispatchInterruption
    return out
  } catch (err) {
    const plan = dispatchRetry(err, name, 1, 0, dispatchPolicy(null), false)
    if (!plan.interruption) throw err
    dispatchInterruption = plan.interruption
    return dispatchOutcome({})
  }
}
// END bounded dispatch policy


function failureCause(err) { return dispatchFailureCause(err) }
async function settleAgent(prompt, opts) {
  if (dispatchInterruption) return null
  const o = opts && typeof opts === 'object' ? opts : {}
  const call = { ...o }
  delete call.retryPolicy
  delete call.schemaName
  delete call.rethrow
  const name = o.label || o.agentType || 'agent'
  const policy = dispatchPolicy(o)
  const mine = []
  let waitedMs = 0
  for (let attempt = 1; ; attempt++) {
    if (dispatchInterruption) return null
    try {
      const out = await agent(prompt, call)
      if (out) {

        return out
      }

      log(name + ': returned nothing')
      return null
    } catch (err) {
      const plan = dispatchRetry(err, name, attempt, waitedMs, policy, typeof setTimeout === 'function')
      const message = String((err && err.message) || err)

      if (!plan.retry) {
        if (plan.interruption) dispatchInterruption = plan.interruption
        log(name + ': stopped (' + plan.cause + ') — ' + message)
        if (o.rethrow && !plan.interruption) throw err
        return null
      }
      waitedMs += plan.wait
      log(name + ': transient failure; retry ' + (attempt + 1) + '/' + policy.maxAttempts + ' in ' + Math.round(plan.wait / 1000) + 's — ' + message.slice(0, 160))
      await new Promise((resolve) => setTimeout(resolve, plan.wait))
    }
  }
}

// args: { repoPath: string, command?: string, label?: string }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const repoPath = String(a.repoPath || '').trim().replace(/\/+$/, '')
const command = String(a.command || '').trim()
const label = String(a.label || '').trim()

if (!repoPath) {
  return dispatchOutcome({ ok: false, exitCode: -1, command, tail: '', failing: [], summary: '', resolveError: 'no repoPath supplied' })
}

const RUN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['command', 'exitCode', 'tail', 'failing', 'summary'],
  properties: {
    command: { type: 'string' },
    exitCode: { type: 'integer' },
    tail: { type: 'string' },
    failing: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['kind', 'file', 'test', 'line'],
        properties: {
          kind: { type: 'string', enum: ['test', 'load'] },
          file: { type: 'string' },
          test: { type: 'string' },
          line: { type: 'string' },
        },
      },
    },
    summary: { type: 'string' },
    resolveError: { type: 'string' },
  },
}

const EXIT_MARK = 'SUITE-EXIT'
const REPORT = `Report:
- command: the test command you ran, exactly (without the \`; echo "${EXIT_MARK} $?"\` that follows it).
- exitCode: the number the \`${EXIT_MARK}\` line printed.
- tail: the last 200 lines of the output, copied verbatim, ending with the \`${EXIT_MARK}\` line.
- failing: one entry per failure the output names, whatever the test runner. \`kind\` is \`test\` for a test that ran and failed or errored, and \`load\` for a test file the runner could not load, import, compile or collect, so none of its tests ran. \`file\` is the test file's path as the output prints it; \`test\` is the test's name without the file (empty for \`load\`); \`line\` is the output line that names the failure, verbatim. Empty when nothing failed.
- summary: the runner's final summary line, or "" when it printed none.`

const runBlock = (cmd) => `Run exactly this, once, and report what it printed:

cd "${repoPath}" && ${cmd}; echo "${EXIT_MARK} $?"

Read and change nothing else: no other command, no file edits, no installs, no retries with other flags.`

const resolveBlock = `Find the command this repository declares for running its whole test suite, then run it once.

Repository tree: ${repoPath}

1. Read \`${repoPath}/AGENTS.md\` and \`${repoPath}/CLAUDE.md\` (either may be absent). When one states the command that runs the tests, that is the command.
2. Otherwise, when \`${repoPath}/Taskfile.yml\` or \`${repoPath}/Taskfile.yaml\` defines a \`test\` task, the command is \`task test\`.
3. Otherwise the repository declares none: run nothing and return exitCode -1, command "", tail "", failing [], summary "", and resolveError naming the files you read. A command inferred from the tooling you see (pyproject.toml, package.json, a tests directory) is not declared by the repository, so it is not used.

Then run the command, exactly as declared, once:

cd "${repoPath}" && <the command>; echo "${EXIT_MARK} $?"

Read and change nothing else: no file edits, no installs, no retries with other flags.`

phase('Run')

const out = await settleAgent(`${command ? runBlock(command) : resolveBlock}

${REPORT}`, {
  label: `suite-run${label ? `:${label}` : ''}`,
  phase: 'Run',
  model: 'haiku',
  effort: 'low',
  schema: RUN_SCHEMA,
})

if (!out) {
  return dispatchOutcome({ ok: false, dispatchFailed: true, exitCode: -1, command, tail: '', failing: [], summary: '', reason: 'the suite runner returned nothing' })
}

const ran = String(out.command || '').trim()
const resolveError = String(out.resolveError || '').trim()
if (!command && (!ran || resolveError)) {
  log(`suite-run: no test command declared in ${repoPath}: ${resolveError || 'the runner named no command'}`)
  return dispatchOutcome({
    ok: false,
    exitCode: -1,
    command: '',
    tail: '',
    failing: [],
    summary: '',
    resolveError: resolveError || 'the repository declares no test command',
  })
}

const tail = String(out.tail || '')
const marks = [...tail.matchAll(new RegExp(`${EXIT_MARK} (\\d+)`, 'g'))]
if (!marks.length) {
  const why = `the run's output carries no \`${EXIT_MARK}\` line, so its exit status is unknown`
  log(`suite-run: ${why}`)
  return dispatchOutcome({ ok: false, exitCode: -1, command: command || ran, tail, failing: [], summary: String(out.summary || '').trim(), reason: why })
}
const exitCode = Number(marks[marks.length - 1][1])
if (out.exitCode !== exitCode) log(`suite-run: the runner reported exit ${out.exitCode}; the ${EXIT_MARK} line says ${exitCode}, which is used`)
const failing = (Array.isArray(out.failing) ? out.failing : [])
  .filter((f) => f && typeof f === 'object')
  .map((f) => ({ kind: f.kind === 'load' ? 'load' : 'test', file: String(f.file || '').trim(), test: String(f.test || '').trim(), line: String(f.line || '').trim() }))
  .filter((f) => f.file || f.test || f.line)
log(`suite-run: \`${command || ran}\` exited ${exitCode}${out.summary ? ` — ${String(out.summary).trim()}` : ''}`)
return dispatchOutcome({
  ok: exitCode === 0,
  command: command || ran,
  exitCode,
  tail,
  failing,
  summary: String(out.summary || '').trim(),
})
