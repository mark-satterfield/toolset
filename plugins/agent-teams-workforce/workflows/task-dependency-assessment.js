export const meta = {
  name: 'task-dependency-assessment',
  description:
    "Assesses the build dependencies of ONE Task created outside elaboration and writes its `blocks` edges. One task-dependency-mapper session writes the Task's context, reads the related Tasks, proposes and validates the edges, and runs apply-edges. When the edges are applied it triggers wsjf-scoring. With `apply: false` apply-edges runs as a dry run and no scoring runs.",
  whenToUse: 'A Task was created or changed outside elaboration and needs its build dependencies assessed.',
  phases: [
    { title: 'Assess', detail: 'one task-dependency-mapper session writes the context, proposes and validates the edges, and runs apply-edges' },
    { title: 'Score', detail: 'wsjf-scoring over the new edges' },
  ],
}
const dispatchFailures = []
// Returns the recorded dispatch failures of the named phases, or all of them when none is named.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
const DETERMINISTIC_ERROR_TEXT =
  /completed without calling structuredoutput|structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i
const TRANSIENT_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504, 529])
// Returns 'transient' for an API overload, rate limit or network error, otherwise 'deterministic'.
function failureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = String((e && e.message) || err || '')
  if (DETERMINISTIC_ERROR_TEXT.test(text)) return 'deterministic'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((v) => Number(v))
    .find((v) => Number.isFinite(v) && v >= 100 && v < 600)
  if (Number.isFinite(status) && TRANSIENT_STATUS.has(status)) return 'transient'
  return TRANSIENT_ERROR_TEXT.test(text) ? 'transient' : 'deterministic'
}
const SETTLE_CAN_WAIT = typeof setTimeout === 'function'
const settleSleep = (ms) => (SETTLE_CAN_WAIT ? new Promise((resolve) => setTimeout(resolve, ms)) : Promise.resolve())
// Returns the wait before retry `attempt`: 5s tripled per attempt, capped at 300s, scaled into [50%, 100%) by a hash of the dispatch.
function transientWaitMs(name, attempt) {
  const key = `${name}#${attempt}`
  let h = 2166136261
  for (let i = 0; i < key.length; i++) h = Math.imul(h ^ key.charCodeAt(i), 16777619)
  const scheduled = Math.min(300000, 5000 * Math.pow(3, attempt - 1))
  return Math.round(scheduled * (0.5 + 0.5 * ((h >>> 0) / 4294967296)))
}
// Calls agent() and returns its result. A transient failure is retried with backoff until it clears
// (three attempts when no timer exists); any other failure returns null and is recorded in dispatchFailures.
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const who = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null }
  const name = who.label || who.agentType || 'agent'
  const mine = []
  let waitedMs = 0
  for (let attempt = 1; ; attempt++) {
    let out = null
    try {
      out = await agent(prompt, o)
    } catch (err) {
      const message = String((err && err.message) || err)
      const cause = failureCause(err)
      const entry = {
        ...who,
        outcome: 'threw',
        cause,
        attempt,
        message: message.slice(0, 300),
        note: `${name} ended without a structured result (${cause}): ${message.slice(0, 160)}`,
      }
      dispatchFailures.push(entry)
      mine.push(entry)
      log(entry.note)
      if (cause !== 'transient' || (!SETTLE_CAN_WAIT && attempt >= 3)) return null
      const wait = transientWaitMs(name, attempt)
      waitedMs += wait
      log(`${name}: transient failure on attempt ${attempt}; retrying in ${Math.round(wait / 1000)}s (${Math.round(waitedMs / 1000)}s waited)`)
      await settleSleep(wait)
      continue
    }
    if (out) {
      for (const entry of mine) {
        const at = dispatchFailures.indexOf(entry)
        if (at >= 0) dispatchFailures.splice(at, 1)
      }
      return out
    }
    dispatchFailures.push({ ...who, outcome: 'skipped', cause: 'deterministic', attempt, message: null, note: `${name} returned nothing` })
    log(`${name} returned nothing`)
    return null
  }
}

// args: {
//   repoPath:     string,   // absolute path of the repository whose `bd` tracker holds the Tasks
//   pluginRoot:   string,   // absolute path of this plugin's root
//   workDir:      string,   // absolute path of a directory for this run's files
//   task:         string,   // the one Task assessed
//   projectRoot?: string,
//   archPath?:    string,
//   score?:       boolean,  // false: do not trigger scoring. Default true.
//   apply?:       boolean,  // false: apply-edges runs as a dry run. Default true.
// }
// Returns: { ok, stage, beadId, headline, apply, settled, workDir, task, assessment, edges, scoring,
//            stop, error?, dispatchFailed, dispatchFailures }
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
const resolved = await resolveArgs(given, 'task-dependency-assessment', [...PATH_ARGS, 'task'])
if (resolved.missing.length) return refuseArgs(resolved, 'task-dependency-assessment')
const a = resolved.args
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const target = String(a.task || '')
const repo = String(a.repoPath || '').replace(/\/+$/, '')
const work = String(a.workDir || '').replace(/\/+$/, '')
const DS = `${String(a.pluginRoot || '').replace(/\/+$/, '')}/scripts/portfolio/depscore.py`
const file = (name) => `${work}/${name}`
const cmd = (sub, extra) => `python3 ${shq(DS)} ${sub} -C ${shq(repo)}${extra ? ` ${extra}` : ''}`
const scope = `--task ${shq(target)}`
const applies = a.apply !== false
const project = { repoPath: repo, pluginRoot: a.pluginRoot, archPath: a.archPath, projectRoot: a.projectRoot }

const planFile = file('assess-plan.json')
const contextDir = file('context')
const contextFile = file('context.json')
const corpusDir = `${contextDir}/task`
const indexFile = `${contextDir}/index.md`
const taskFile = `${corpusDir}/${target}.md`
const edgesFile = file('edges.json')
const reasoningFile = file('reasoning.md')
const validationFile = file('validation.json')
const applyFile = file(applies ? 'apply-edges.json' : 'apply-edges-dry-run.json')

phase('Assess')
const ASSESS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['edgesPath', 'edgeCount', 'valid', 'relatedRead', 'applyExitCode', 'applySummary'],
  properties: {
    edgesPath: { type: 'string' },
    reasoningPath: { type: 'string' },
    edgeCount: { type: 'integer' },
    valid: { type: 'boolean' },
    findings: { type: 'object' },
    relatedRead: { type: 'array', items: { type: 'string' } },
    unsure: { type: 'array', items: { type: 'string' } },
    applyExitCode: { type: 'integer' },
    applySummary: { type: 'object' },
    error: { type: 'string' },
  },
}
const THE_TEST = `THE TEST. An edge from A to B says B cannot be built until A is built, because B consumes something A provides — an API, an event contract, a table, an IAM grant, a deployed resource. Sharing a domain, a vocabulary, a repository or an Epic is not an edge. Both ends are Tasks: no end is a Story or an Epic. When in doubt an edge is left out, because a false edge serializes work that could run in parallel.`
const applyCmd = `set -o pipefail; ${cmd('apply-edges', `--edges ${shq(edgesFile)} --plan ${shq(planFile)} ${scope}${applies ? '' : ' --dry-run'}`)} | tee ${shq(applyFile)}`
const priorBlock = typeof a.priorFailure === 'string' && a.priorFailure.trim()
  ? `THE PREVIOUS ASSESSMENT OF THIS ITEM FAILED, on this same content: ${a.priorFailure.trim().slice(0, 2000)}\nWork out why before you start, and do not repeat it.\n\n`
  : ''
const assessPrompt = `${priorBlock}Assess the build dependencies of ONE Task, ${target}, which was created outside elaboration. ${target} is new or has changed.

${THE_TEST}

Work in this order:
1. Run these two commands, once each. Each prints one JSON object; if either exits non-zero, stop, set \`valid\` false, \`applyExitCode\` -1, \`applySummary\` {}, and put its output in \`error\`.
   ${cmd('assess-plan', `--level task ${scope} --out ${shq(planFile)}`)}
   ${cmd('assess-context', `${scope} --dir ${shq(contextDir)} --out ${shq(contextFile)}`)}
   They write: ${target} at ${taskFile}; the corpus at ${corpusDir}, one file per open Task named <id>.md; the index at ${indexFile}, one line per open Task with its title, Epic, repository, status and file; and ${contextFile}, whose \`standing\` lists every edge between ${target} and another open Task, in either direction, as {from, to, type, owned, reason, confidence, setBy, setAt} — \`from\` is the Task built first, \`reason\` the one recorded when the edge was set, or null. \`withdrawn\` lists every edge touching ${target} that an earlier assessment WITHDREW, as {from, to, reason, withdrawnBy, withdrawnAt}: that edge was judged not to exist, for the reason recorded. Setting it again is admitted only when you answer that reason.
2. Read ${target}.
3. Name what it consumes and what it provides.
4. Search the corpus with Grep, and the index, for the Tasks that provide what ${target} consumes or consume what it provides. Read no Task the search did not find related.
5. Read in full every related Task, and the Task at the other end of every standing edge.
6. Apply the test in both directions: an edge from another Task to ${target} where ${target} consumes what that Task provides, and an edge from ${target} to another Task where that Task consumes what ${target} provides.
7. Write ${edgesFile} as {"edges": [{"from", "to", "reason", "confidence", "answers"}], "withdrawn": [{"from", "to", "reason"}]}. \`answers\` is required only on an edge the context's \`withdrawn\` list covers: state why the recorded withdrawal reason is wrong. An edge you cannot answer that way is not set — the earlier judgment stands. \`edges\` holds EVERY edge to or from ${target} that passes the test — a standing one it keeps included — and no edge that does not touch ${target}. \`withdrawn\` holds every standing edge with \`owned: true\` that is not in \`edges\`, with a reason that answers the reason recorded for it. Every reason names the artifact and which Task provides it; \`confidence\` is \`high\`, \`medium\` or \`low\`. A standing edge with \`owned: false\` was made by hand: leave it out of both lists. No edge is a valid result. Write the reasoning, per edge and per withdrawal, to ${reasoningFile}.
8. Validate: \`set -o pipefail; ${cmd('validate', `--edges ${shq(edgesFile)} ${scope}`)} | tee ${shq(validationFile)}\` — revise the file until \`ok\` is true, keeping to THE TEST: an edge that fails the test is dropped, never kept to satisfy the validator; an owned standing edge you drop goes in \`withdrawn\` with a reason. It refuses an edge that does not touch ${target}, an edge whose ends are not both open Tasks, a missing reason, an edge an earlier assessment withdrew that carries no \`answers\`, an owned standing edge left unaccounted, a withdrawal of an edge that is not an owned standing edge, and a cycle against every other Task edge. A cycle you cannot remove by dropping one of your own edges that fails the test — one through an edge with \`owned: false\` — is reported, not forced: set \`valid\` false, put the validator's findings in \`findings\`, name the cycle in \`unsure\`, and do not run step 9 (\`applyExitCode\` -1, \`applySummary\` {}).
9. Only once validation passes, run exactly this, once: \`${applyCmd}\`. Return its exit code as \`applyExitCode\` and the \`summary\` object it printed, unaltered, as \`applySummary\`. Do not retry it or repair anything it refuses.

Return the edge file path, the reasoning file path, the edge count, whether the final validation passed, \`relatedRead\` — the id of every Task you read in full, other than ${target} — each edge you were unsure of with what would settle it, and the apply-edges result.`

const assessed = await settleAgent(assessPrompt, {
  label: `task-dependency-mapper:${target}`,
  phase: 'Assess',
  effort: 'medium',
  agentType: 'task-dependency-mapper',
  schema: ASSESS_SCHEMA,
})
const printed = (assessed && assessed.applySummary) || {}
const summary = printed.command === 'apply-edges' && printed.summary && typeof printed.summary === 'object' ? printed.summary : printed
const settled = !!assessed && assessed.applyExitCode === 0 && !summary.validation && summary.applied !== false
const stop = assessed && !settled && !assessed.error
  ? { task: target, findings: assessed.findings || summary.validation || {}, edgesFile, validationFile, reasoning: reasoningFile }
  : null
const edges = {
  ...summary,
  applied: applies && settled,
  proposed: !applies && settled,
  resultFile: applyFile,
  edgesFile,
  reasoning: reasoningFile,
  unsure: (assessed && assessed.unsure) || [],
  ...(settled
    ? {}
    : {
        reason: !assessed
          ? 'the task-dependency-mapper returned no result; the tracker keeps its current edges'
          : assessed.error
            ? `the context could not be written: ${assessed.error}`
            : `the edge proposal was not applied (exit ${assessed.applyExitCode}); the tracker keeps its current edges`,
      }),
}
if (settled) log(`Edges (${target})${applies ? '' : ', proposed'}: ${summary.added ?? '?'} added, ${summary.converted ?? '?'} converted, ${summary.removed ?? '?'} withdrawn, ${summary.unchanged ?? '?'} unchanged`)
else log(`${target}: ${edges.reason}`)

let scoring = null
const scores = applies && settled && a.score !== false
if (scores) {
  phase('Score')
  try {
    scoring = await workflow('agent-teams-workforce:wsjf-scoring', { ...project, workDir: file('scoring') })
  } catch (err) {
    scoring = { ok: false, error: String((err && err.message) || err).slice(0, 500) }
  }
}

const storyEdges = summary.storyEdges || null
const storyEdgeLine = !storyEdges
  ? ''
  : storyEdges.ok
    ? `; Story edges ${storyEdges.added || 0} added, ${storyEdges.removed || 0} removed`
    : `; Story edges ${storyEdges.error ? `NOT written — ${storyEdges.error}` : `${storyEdges.added || 0} added, ${storyEdges.removed || 0} removed; NOT written for ${(storyEdges.refusedStories || []).join(', ')}, whose order is contradictory`}${[...(storyEdges.conflicts || []), ...(storyEdges.cycles || [])]
        .map((x) => ` [${(x.stories || []).join(' / ')}${(x.tasks || []).length ? `, Tasks ${x.tasks.join(', ')}` : ''}]`)
        .join('')}`
if (storyEdgeLine) log(`${target}${storyEdgeLine}`)

const scoredOk = !scores || (!!scoring && scoring.ok === true)
const scoringDeaths = scoring && scoring.ok !== true && scoring.stage === 'agent-dispatch-failed' && Array.isArray(scoring.dispatchFailures) ? scoring.dispatchFailures : []
const failure = !settled
  ? `${target}: ${edges.reason}`
  : !scoredOk
    ? `${target}: the edges were applied, but scoring failed: ${(scoring && scoring.error) || 'wsjf-scoring returned no result'}`
    : null
return {
  ok: settled && scoredOk,
  stage: !assessed ? 'agent-dispatch-failed' : !settled ? 'Assess' : !scoredOk ? (scoring && scoring.stage === 'agent-dispatch-failed' ? scoring.stage : 'Score') : 'done',
  beadId: target,
  headline: failure || `${target}: edges ${applies ? 'applied' : 'proposed'} — ${summary.added ?? '?'} added, ${summary.converted ?? '?'} converted, ${summary.removed ?? '?'} withdrawn, ${summary.unchanged ?? '?'} unchanged${scores ? ', and rescored' : ''}${storyEdgeLine}`,
  apply: applies,
  settled,
  workDir: work,
  task: target,
  assessment: assessed || { failed: true },
  edges,
  scoring,
  stop,
  ...(failure ? { error: failure } : {}),
  dispatchFailed: dispatchDeaths().length + scoringDeaths.length > 0,
  dispatchFailures: [...dispatchDeaths(), ...scoringDeaths],
}
