export const meta = {
  name: 'seed-portfolio',
  description:
    "Seeds the Epic portfolio: runs dependency-assessment (with `score: false`) for every Epic in `epics`, one after another in the order given, then runs wsjf-scoring once. An Epic whose assessment fails is reported in `stoppedAt` and `remaining` and the seeding continues. With `apply: false` every assessment proposes only and nothing is scored. A path arg left out is read from the environment: `repoPath` from $ATW_CONTROL_REPO, `archPath` from $ATW_ARCH_PATH, `projectRoot` from $ATW_PROJECT_ROOT, `pluginRoot` from the install $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json records, and `workDir` from mkdtemp; when a required one has no value the run refuses before dispatching any agent, naming the arg and the variable that supplies it.",
  whenToUse: 'The Epic portfolio is seeded once: every open Epic gets its architecture dependencies assessed before every Epic and Task is scored by wsjf-scoring.',
  phases: [
    { title: 'Assess', detail: 'dependency-assessment for each Epic, one after another, with score: false' },
    { title: 'Score', detail: 'wsjf-scoring once, over the edge set' },
  ],
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

const dispatchFailures = []
// Returns the recorded dispatch failures of the named phases, or all of them when none is named.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
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
        for (const entry of mine) { const at = dispatchFailures.indexOf(entry); if (at >= 0) dispatchFailures.splice(at, 1) }
        return out
      }
      dispatchFailures.push({ agentType: o.agentType || null, label: o.label || null, phase: o.phase || null, outcome: 'skipped', cause: 'deterministic', attempt, message: null, note: name + ': returned nothing' })
      log(name + ': returned nothing')
      return null
    } catch (err) {
      const plan = dispatchRetry(err, name, attempt, waitedMs, policy, typeof setTimeout === 'function')
      const message = String((err && err.message) || err)
      const entry = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null, outcome: 'threw', cause: plan.cause, attempt, message: message.slice(0, 300), note: name + ': ' + message.slice(0, 160) }
      dispatchFailures.push(entry)
      mine.push(entry)
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

// args: {
//   repoPath:     string,    // absolute path of the repository whose `bd` tracker holds the Epics
//   pluginRoot:   string,    // absolute path of this plugin's root
//   workDir:      string,    // absolute path of a directory for this run's files
//   since:        string,    // ISO 8601 instant the seeding began, reported back
//   epics:        string[],  // the open Epics to assess, in order
//   archPath?:    string,
//   projectRoot?: string,
//   apply?:       boolean,   // false: every assessment proposes only; nothing is written. Default true.
// }
// Returns: { ok, stage, headline, since, apply, assessed, stoppedAt, remaining, failed, scoring,
//            dispatchFailed, dispatchFailures }
//   assessed:   [{ id, added, converted, removed, unchanged, withdrawn, edgesFile, reasoning, resultFile }]
//   failed:     [{ id, error, findings, edgesFile, validationFile, dispatchFailures }], one per failed Epic
//   stoppedAt:  the first entry of `failed`, or null
//   remaining:  the ids of the failed Epics
const given = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const PATH_ARGS = ['repoPath', 'pluginRoot', 'workDir']
// The environment variable that supplies each path arg the caller leaves out. pluginRoot has none of
// its own: it is the agent-teams-workforce install that $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json
// records. workDir has none either: a run without one gets a new directory from mkdtemp.
const ENV_OF = { repoPath: 'ATW_CONTROL_REPO', archPath: 'ATW_ARCH_PATH', projectRoot: 'ATW_PROJECT_ROOT' }
const OPTIONAL_PATH_ARGS = ['archPath', 'projectRoot']
const isAbsolute = (v) => typeof v === 'string' && v.trim().startsWith('/')
const RESOLVE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['exitCode', 'output'],
  properties: { exitCode: { type: 'integer' }, output: { type: 'object' } },
}
const RESOLVE_PY = `import json, os, sys, tempfile, time
from pathlib import Path
name, wanted = sys.argv[1], json.loads(sys.argv[2])
env_of = {"repoPath": "ATW_CONTROL_REPO", "archPath": "ATW_ARCH_PATH", "projectRoot": "ATW_PROJECT_ROOT"}
out, problems = {}, {}
def from_env(key):
    var = env_of[key]
    value = os.environ.get(var, "").strip()
    if not value:
        return f"\${var} is not set"
    if not Path(value).is_absolute() or not Path(value).exists():
        return f"\${var} is {value!r}, which is not an existing absolute path"
    out[key] = os.path.normpath(value)
    return ""
for key in ("repoPath", "archPath", "projectRoot"):
    if key in wanted:
        why = from_env(key)
        if why:
            problems[key] = why
if "pluginRoot" in wanted:
    marker = ("scripts", "portfolio", "depscore.py")
    config = os.environ.get("CLAUDE_CONFIG_DIR", "").strip() or str(Path.home() / ".claude")
    reg = Path(config) / "plugins" / "installed_plugins.json"
    control = os.environ.get("ATW_CONTROL_REPO", "").strip()
    control = os.path.normpath(control) if control else ""
    try:
        plugins = json.loads(reg.read_text(encoding="utf-8")).get("plugins", {})
    except (OSError, ValueError) as exc:
        plugins = None
        problems["pluginRoot"] = f"{reg} is unreadable: {exc}"
    if plugins is not None:
        ranked = []
        for key, entries in plugins.items():
            if not key.startswith("agent-teams-workforce@") or not isinstance(entries, list):
                continue
            for e in entries:
                path = e.get("installPath") if isinstance(e, dict) else None
                if not isinstance(path, str) or not Path(path, *marker).is_file():
                    continue
                if control and e.get("scope") in ("local", "project") and e.get("projectPath") == control:
                    ranked.append((0, path))
                elif e.get("scope") == "user":
                    ranked.append((1, path))
        if ranked:
            out["pluginRoot"] = os.path.normpath(sorted(ranked)[0][1])
        else:
            problems["pluginRoot"] = f"{reg} lists no agent-teams-workforce install shipping scripts/portfolio/depscore.py at user scope" + (f" or for $ATW_CONTROL_REPO ({control})" if control else "")
if "workDir" in wanted:
    out["workDir"] = os.path.realpath(tempfile.mkdtemp(prefix=f"{name}-"))
out["since"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
out["problems"] = problems
print(json.dumps(out))`
// Fills each path arg the caller left out, and only from the environment: repoPath from
// $ATW_CONTROL_REPO, archPath from $ATW_ARCH_PATH, projectRoot from $ATW_PROJECT_ROOT, pluginRoot from the
// agent-teams-workforce install that $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json records (the
// install for $ATW_CONTROL_REPO first, else the user-scope one), and workDir from mkdtemp. One runner
// session reads them, dispatched only when an arg is missing. Returns { args, missing, problems }:
// `missing` names every required arg still without a value, and the caller refuses before dispatching
// any other agent. An optional path arg the environment does not supply stays absent.
async function resolveArgs(given, name, required) {
  const out = { ...given }
  const lacking = [...PATH_ARGS, ...OPTIONAL_PATH_ARGS].filter((k) => !isAbsolute(out[k]))
  const problems = {}
  if (lacking.length) {
    const q = (s) => `'${String(s).replace(/'/g, "'\\''")}'`
    const got = await settleAgent(
      `Run this shell command exactly once and change nothing else:

python3 -c ${q(RESOLVE_PY)} ${q(name)} ${q(JSON.stringify(lacking))}

It prints one JSON object on stdout. Return its process exit code as \`exitCode\` and that JSON object, parsed and unaltered, as \`output\`. If stdout is not JSON, return {"error": "<stdout and stderr, verbatim>"} as \`output\`. Do not retry, do not repair, do not set any variable, do not run any other command.`,
      { label: 'resolve-paths', model: 'haiku', effort: 'low', schema: RESOLVE_SCHEMA }
    )
    const found = (got && got.output) || {}
    if (!got) problems.resolver = 'the path resolver returned no result'
    else if (found.error) problems.resolver = String(found.error).slice(0, 500)
    Object.assign(problems, found.problems && typeof found.problems === 'object' ? found.problems : {})
    for (const k of lacking) {
      if (isAbsolute(found[k])) {
        out[k] = found[k].trim()
        log(`${k} was not passed; ${ENV_OF[k] ? `$${ENV_OF[k]} gives` : k === 'workDir' ? 'mkdtemp made' : 'the plugin registry gives'} ${out[k]}`)
      }
    }
    if (!(typeof out.since === 'string' && out.since.trim()) && typeof found.since === 'string') out.since = found.since
  }
  const missing = required.filter((k) => (PATH_ARGS.includes(k) ? !isAbsolute(out[k]) : !(typeof out[k] === 'string' && out[k].trim())))
  return { args: out, missing, problems }
}
// Names what satisfies `k`: the Workflow arg, or the environment that supplies it.
function remedy(k) {
  if (ENV_OF[k]) return `pass ${k} in the Workflow args or set $${ENV_OF[k]}`
  if (k === 'pluginRoot') return 'pass pluginRoot in the Workflow args or install agent-teams-workforce so $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json (default ~/.claude) records it'
  return `pass ${k} in the Workflow args`
}
// Returns the refusal a workflow gives when a required arg has no value; no other agent has been dispatched.
function refuseArgs(resolved, name) {
  const why = resolved.missing
    .map((k) => `${k} has no value${resolved.problems[k] ? ` (${resolved.problems[k]})` : ''}: ${remedy(k)}`)
    .join('; ')
  const extra = resolved.problems.resolver ? `; resolver: ${resolved.problems.resolver}` : ''
  const error = `${name} refused before dispatching any agent: ${why}${extra}.`
  log(error)
  return {
    ok: false,
    stage: 'args',
    headline: error,
    error,
    missing: resolved.missing,
    dispatchFailed: dispatchDeaths().length > 0,
    dispatchFailures: dispatchDeaths(),
  }
}
const resolved = await resolveArgs(given, 'seed-portfolio', [...PATH_ARGS])
if (resolved.missing.length) return dispatchOutcome(refuseArgs(resolved, 'seed-portfolio'))
const a = resolved.args
const work = String(a.workDir || '').replace(/\/+$/, '')
const file = (name) => `${work}/${name}`
const contextDir = file('context')
const applies = a.apply !== false
const project = { repoPath: a.repoPath, pluginRoot: a.pluginRoot, archPath: a.archPath, projectRoot: a.projectRoot }
const count = (v) => (Array.isArray(v) ? v.length : typeof v === 'number' ? v : 0)
const queue = Array.isArray(a.epics) ? a.epics.filter((e) => typeof e === 'string' && e) : []
const assessed = []
const failed = []
let scoring = null
let nestedDeaths = []
log(`${queue.length} Epic(s) to assess since ${a.since}`)

phase('Assess')
let corpusReady = false
for (const id of queue) {
  let r = null
  let thrown = null
  try {
    r = await settleWorkflow('agent-teams-workforce:dependency-assessment', {
      ...project,
      workDir: file(`assess/${id}`),
      contextDir,
      corpusReady,
      epic: id,
      score: false,
      apply: applies,
    })
  } catch (err) {
    thrown = String((err && err.message) || err).slice(0, 500)
  }
  const edges = (r && r.edges) || {}
  if (r && r.ok === true) {
    corpusReady = true
    assessed.push({
      id,
      added: count(edges.added),
      converted: count(edges.converted),
      removed: count(edges.removed),
      unchanged: edges.unchanged ?? null,
      withdrawn: edges.withdrawn ?? null,
      edgesFile: edges.edgesFile || null,
      reasoning: edges.reasoning || null,
      resultFile: edges.resultFile || null,
    })
    log(`${id}: ${count(edges.added)} added, ${count(edges.converted)} converted, ${count(edges.removed)} withdrawn${applies ? '' : ' (proposed)'}`)
    continue
  }
  const stop = (r && r.stop) || null
  const entry = {
    id,
    error: thrown || (r && r.error) || 'the dependency assessment returned no result',
    findings: stop ? stop.findings || null : null,
    edgesFile: stop ? stop.edgesFile || null : edges.edgesFile || null,
    validationFile: stop ? stop.validationFile || null : null,
    dispatchFailures: (r && r.dispatchFailures) || [],
  }
  failed.push(entry)
  if (r && r.stage === 'agent-dispatch-failed') nestedDeaths.push(...entry.dispatchFailures)
  log(`${id}: assessment failed — ${entry.error}`)
}

let scoringError = null
if (applies) {
  phase('Score')
  try {
    scoring = await settleWorkflow('agent-teams-workforce:wsjf-scoring', { ...project, workDir: file('scoring') })
  } catch (err) {
    scoringError = String((err && err.message) || err).slice(0, 500)
  }
  if (!(scoring && scoring.ok === true)) {
    if (scoring && scoring.stage === 'agent-dispatch-failed') nestedDeaths.push(...(scoring.dispatchFailures || []))
    scoringError = scoringError || (scoring && scoring.error) || 'wsjf-scoring returned no result'
    log(`Scoring failed: ${scoringError}`)
  }
}

const errors = [
  failed.length ? `${failed.length} Epic(s) failed assessment: ${failed.map((f) => f.id).join(', ')}; resume with the same since, ${a.since}` : '',
  scoringError ? `scoring failed: ${scoringError}` : '',
].filter(Boolean)
const ok = errors.length === 0
return dispatchOutcome({
  ok,
  stage: ok ? 'done' : nestedDeaths.length ? 'agent-dispatch-failed' : failed.length ? 'Assess' : 'Score',
  headline: ok ? `${assessed.length} Epic(s) assessed${applies ? ' and the portfolio rescored' : ' (proposed only)'}` : errors.join('; '),
  since: a.since,
  apply: applies,
  assessed,
  stoppedAt: failed[0] || null,
  remaining: failed.map((f) => f.id),
  failed,
  scoring,
  ...(ok ? {} : { error: errors.join('; ') }),
  dispatchFailed: dispatchDeaths().length + nestedDeaths.length > 0,
  dispatchFailures: [...dispatchDeaths(), ...nestedDeaths],
})
