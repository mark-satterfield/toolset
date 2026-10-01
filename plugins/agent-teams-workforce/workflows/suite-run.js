export const meta = {
  name: 'suite-run',
  description:
    "Leaf mini — runs a repository's whole test suite once and reports what the run printed. One session runs exactly one command in the tree, followed by an echo of its exit status on a SUITE-EXIT line, and returns { exitCode, tail, failing, summary, command }; the exit code is read from that line in the verbatim tail, and a run whose output lacks it returns exitCode -1. Each failing entry is { kind: test | load, file, test, line }, whatever the test runner. The command is the caller's, or, when the caller names none, the one the repository itself declares: a test command stated in its AGENTS.md or CLAUDE.md, or the `test` task in its Taskfile. When the repository declares none it returns resolveError and runs nothing. Green means exitCode 0; the caller judges that, not the session.",
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

const tail = String(out.tail || '')
const marks = [...tail.matchAll(new RegExp(`${EXIT_MARK} (\\d+)`, 'g'))]
if (!marks.length) {
  const why = `the run's output carries no \`${EXIT_MARK}\` line, so its exit status is unknown`
  log(`suite-run: ${why}`)
  return { ok: false, exitCode: -1, command: command || ran, tail, failing: [], summary: String(out.summary || '').trim(), reason: why }
}
const exitCode = Number(marks[marks.length - 1][1])
if (out.exitCode !== exitCode) log(`suite-run: the runner reported exit ${out.exitCode}; the ${EXIT_MARK} line says ${exitCode}, which is used`)
const failing = (Array.isArray(out.failing) ? out.failing : [])
  .filter((f) => f && typeof f === 'object')
  .map((f) => ({ kind: f.kind === 'load' ? 'load' : 'test', file: String(f.file || '').trim(), test: String(f.test || '').trim(), line: String(f.line || '').trim() }))
  .filter((f) => f.file || f.test || f.line)
log(`suite-run: \`${command || ran}\` exited ${exitCode}${out.summary ? ` — ${String(out.summary).trim()}` : ''}`)
return {
  ok: exitCode === 0,
  command: command || ran,
  exitCode,
  tail,
  failing,
  summary: String(out.summary || '').trim(),
}
