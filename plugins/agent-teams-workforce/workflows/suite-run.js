export const meta = {
  name: 'suite-run',
  description:
    "Leaf mini — runs a repository's whole test suite once and reports what the run printed. One session runs exactly one command in the tree and returns { exitCode, tail, failing, summary, command }. The command is the caller's, or, when the caller names none, the one the repository itself declares: a test command stated in its AGENTS.md or CLAUDE.md, or the `test` task in its Taskfile. When the repository declares none it returns resolveError and runs nothing. Green means exitCode 0; the caller judges that, not the session.",
  phases: [{ title: 'Run', detail: 'runs the suite command once and reports its exit code and failures' }],
}

// Retries a dispatch that failed transiently (overload, rate limit, network) with capped backoff;
// returns null on any other failure.
const DETERMINISTIC_ERROR_TEXT =
  /structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i
const TRANSIENT_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504, 529])
const isTransient = (err) => {
  const e = err && typeof err === 'object' ? err : {}
  const text = String(e.message || err || '')
  if (DETERMINISTIC_ERROR_TEXT.test(text)) return false
  const status = Number(e.status || e.statusCode || (e.response && e.response.status))
  return TRANSIENT_STATUS.has(status) || TRANSIENT_ERROR_TEXT.test(text)
}
async function settleAgent(prompt, opts) {
  const call = opts || {}
  const name = call.label || call.agentType || 'agent'
  for (let attempt = 1; ; attempt++) {
    try {
      const out = await agent(prompt, call)
      if (!out) log(`${name}: returned nothing`)
      return out || null
    } catch (err) {
      const message = String((err && err.message) || err)
      if (isTransient(err) && typeof setTimeout === 'function') {
        const wait = Math.min(300000, 5000 * Math.pow(3, attempt - 1))
        log(`${name}: transient failure on attempt ${attempt}; retrying in ${Math.round(wait / 1000)}s — ${message.slice(0, 160)}`)
        await new Promise((resolve) => setTimeout(resolve, wait))
        continue
      }
      log(`${name}: ended without a structured result — ${message.slice(0, 160)}`)
      return null
    }
  }
}

// args: { repoPath: string, command?: string, label?: string }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const repoPath = String(a.repoPath || '').trim().replace(/\/+$/, '')
const command = String(a.command || '').trim()
const label = String(a.label || '').trim()

if (!repoPath) {
  return { ok: false, exitCode: -1, command, tail: '', failing: [], summary: '', resolveError: 'no repoPath supplied' }
}

const RUN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['command', 'exitCode', 'tail', 'failing', 'summary'],
  properties: {
    command: { type: 'string' },
    exitCode: { type: 'integer' },
    tail: { type: 'string' },
    failing: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    resolveError: { type: 'string' },
  },
}

const REPORT = `Report:
- command: the command you ran, exactly.
- exitCode: the command's exit status (\`echo $?\` straight after it).
- tail: the last 200 lines of its output.
- failing: one entry per failing test and per error the output names, each written as \`FAILED <test id>\` or \`ERROR <test id or file>\` (for pytest, the lines it prints starting \`FAILED \` or \`ERROR \`, copied up to the " - " that starts the message). An error that stops a file from being collected is \`ERROR <file>\`. Empty when nothing failed.
- summary: the runner's final summary line (for pytest, the "N passed, M failed" line), or "" when it printed none.`

const runBlock = (cmd) => `Run exactly this, once, and report what it printed:

cd "${repoPath}" && ${cmd}

Read and change nothing else: no other command, no file edits, no installs, no retries with other flags.`

const resolveBlock = `Find the command this repository declares for running its whole test suite, then run it once.

Repository tree: ${repoPath}

1. Read \`${repoPath}/AGENTS.md\` and \`${repoPath}/CLAUDE.md\` (either may be absent). When one states the command that runs the tests, that is the command.
2. Otherwise, when \`${repoPath}/Taskfile.yml\` or \`${repoPath}/Taskfile.yaml\` defines a \`test\` task, the command is \`task test\`.
3. Otherwise the repository declares none: run nothing and return exitCode -1, command "", tail "", failing [], summary "", and resolveError naming the files you read. A command inferred from the tooling you see (pyproject.toml, package.json, a tests directory) is not declared by the repository, so it is not used.

Then run the command, exactly as declared, once:

cd "${repoPath}" && <the command>

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
  return { ok: false, dispatchFailed: true, exitCode: -1, command, tail: '', failing: [], summary: '', reason: 'the suite runner returned nothing' }
}

const ran = String(out.command || '').trim()
const resolveError = String(out.resolveError || '').trim()
if (!command && (!ran || resolveError)) {
  log(`suite-run: no test command declared in ${repoPath}: ${resolveError || 'the runner named no command'}`)
  return {
    ok: false,
    exitCode: -1,
    command: '',
    tail: '',
    failing: [],
    summary: '',
    resolveError: resolveError || 'the repository declares no test command',
  }
}

const exitCode = Number.isInteger(out.exitCode) ? out.exitCode : -1
const failing = (Array.isArray(out.failing) ? out.failing : []).map((x) => String(x || '').trim()).filter(Boolean)
log(`suite-run: \`${command || ran}\` exited ${exitCode}${out.summary ? ` — ${String(out.summary).trim()}` : ''}`)
return {
  ok: exitCode === 0,
  command: command || ran,
  exitCode,
  tail: String(out.tail || ''),
  failing,
  summary: String(out.summary || '').trim(),
}
