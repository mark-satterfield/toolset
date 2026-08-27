// Test harness for agent-teams-workforce workflow SCRIPTS (ssbd-1xcs).
//
// The files under plugins/agent-teams-workforce/workflows/ are not importable ESM
// modules: they are script BODIES executed by the pipeline runner with injected
// globals (args, agent, workflow, phase, log, parallel) and they use top-level
// `return`. This harness reproduces that seam for unit tests: it wraps the source
// in an AsyncFunction, injects FAKE dispatchers that capture every (label, prompt,
// schema) / (workflow, payload) tuple, and returns both the script's result and
// the captured call list.
//
// This file is TEST INFRASTRUCTURE (a mock of the runner), not production code.
// Nothing here reaches a network, an AWS control plane, or a real agent.
//
// It is a mock, so it is only as good as the strictness it reproduces. Where it is
// laxer than the runner, a green suite means nothing — see assertRunnerLoadable below.

import { readFileSync } from 'node:fs'
import { assertRunnerLoadable, compileWorkflowBody } from '../../../scripts/workflow-runner-constraints.mjs'

/** Read the raw workflow source (for source-text assertions, e.g. D1-AC1's grep clause). */
export function readWorkflowSource(absPath) {
  return readFileSync(absPath, 'utf8')
}

/**
 * Execute a workflow script with fake `agent` / `workflow` dispatchers.
 *
 * @param {string} absPath   absolute path to the workflow script
 * @param {object} opts
 * @param {object} opts.args         the `args` global the script parses
 * @param {function} opts.agentImpl  (call, calls) => scripted result for agent() dispatches
 * @param {function} opts.workflowImpl (call, calls) => scripted result for workflow() dispatches
 * @param {object} [opts.budget]     the seventh injected global; undefined unless a test supplies one
 * @returns {Promise<{result: any, calls: Array}>}
 */
export async function runWorkflowScript(absPath, { args = {}, agentImpl, workflowImpl, budget } = {}) {
  const raw = readFileSync(absPath, 'utf8')
  // The runner accepts ONE top-level export — `meta` — and rejects the script on a
  // second one before any phase runs. Stripping every `export const` made this
  // harness more permissive than the runtime it models, which is how a workflow
  // carrying two exports passed the suite while being undispatchable in practice.
  // Neutralize `meta` only, and fail here on anything else, as the runtime does.
  const stray = raw.split('\n').filter((l) => /^export\s/.test(l) && !/^export const meta\b/.test(l))
  if (stray.length) {
    throw new Error(
      `${absPath}: the runtime accepts only \`export const meta\` at top level and rejects the ` +
        `script on any other top-level export. Found: ${stray.map((l) => l.trim().slice(0, 60)).join(' | ')}`,
    )
  }
  // An AsyncFunction body is strictly MORE PERMISSIVE than the real runner: constructs
  // the runner refuses STATICALLY are perfectly legal in here. That gap is not academic
  // — 6.0.6 shipped a workspace.js the runner could not load, and because this harness
  // happily executed it, 446 tests passed and an adversarial verifier's 28 probes all
  // missed that the first phase of all three composites was unloadable.
  //
  // So the harness now refuses what the runner refuses, from the SAME list the syntax
  // checker uses. A test that passes here is now at least a test of a loadable script.
  assertRunnerLoadable(raw, absPath)

  const transformed = raw.replace(/^export\s+const\s+meta\b/m, 'const meta')

  const calls = []
  const agent = async (prompt, opts = {}) => {
    const call = { kind: 'agent', label: (opts && opts.label) || null, prompt: String(prompt), opts }
    calls.push(call)
    const value = agentImpl ? await agentImpl(call, calls) : null
    call.returned = value
    return value
  }
  const workflow = async (name, payload = {}) => {
    const call = { kind: 'workflow', name, payload }
    calls.push(call)
    const value = workflowImpl ? await workflowImpl(call, calls) : null
    call.returned = value
    return value
  }
  const phase = () => {}
  // Logs were discarded, so nothing could assert on them — which is how a log line
  // containing the literal text `{PHASE}` instead of `${phaseName}` shipped in three
  // composites at once. They are captured and returned now; a line a script emits is
  // output, and output that nothing ever reads is output nobody has checked.
  const logs = []
  const log = (line) => {
    logs.push(String(line == null ? '' : line))
  }
  const parallel = async (thunks = []) => {
    const out = []
    for (const t of thunks) out.push(await t())
    return out
  }

  // The harness executes a workflow body, so it carries the SAME capability probe the
  // syntax checker's execution pass does — out-of-contract names are shadowed by
  // tripwires, and a reach is recorded before it throws. Two models, one control: a
  // harness laxer than the checker is precisely the gap that shipped 6.0.6, and a
  // capability escape that only the checker notices is the same defect one level up.
  const compiled = compileWorkflowBody(transformed)
  let result
  try {
    result = await compiled.invoke({ args, agent, workflow, phase, log, parallel, budget })
  } finally {
    // Checked in `finally` so a script that CATCHES its own escape is still reported,
    // and so an escape is reported even when the script then fails for another reason.
    if (compiled.escapes.length) {
      throw new Error(
        `${absPath}: CAPABILITY ESCAPE — this script reached past the globals the runner injects, ` +
          `so a passing test here would be meaningless.\n` +
          compiled.escapes.map((e) => `  ${e.message}`).join('\n'),
      )
    }
  }
  return { result, calls, logs }
}

/** All agent() dispatches with the given label. */
export function agentCalls(calls, label) {
  return calls.filter((c) => c.kind === 'agent' && c.label === label)
}

/** All workflow() dispatches with the given workflow name. */
export function workflowCalls(calls, name) {
  return calls.filter((c) => c.kind === 'workflow' && c.name === name)
}

/**
 * The payload a composite handed to the run journal.
 *
 * Composites no longer return their phase artifacts to the caller — a single run came back
 * with 22k characters truncated off the end, and a campaign of hundreds killed the
 * dispatching session. The detail goes to the run-ledger-writer instead and the caller
 * gets `detailPath`. Tests that used to assert against `result.detail` assert against this.
 *
 * @returns {{ detail: any, runLedger: any[], carriedFlags: string[] }|null}
 */
export function journalPayload(calls) {
  const call = calls.find((c) => c.kind === 'agent' && c.label === 'ledger:persist')
  if (!call) return null
  const marker = 'JSON payload:\n'
  const i = call.prompt.indexOf(marker)
  if (i < 0) return null
  return JSON.parse(call.prompt.slice(i + marker.length))
}

/** Just the `detail` a composite journalled — what `result.detail` used to hold. */
export function journalDetail(calls) {
  const payload = journalPayload(calls)
  return payload ? payload.detail : null
}

/** Index of the first agent() dispatch with the given label, or -1. */
export function agentCallIndex(calls, label) {
  return calls.findIndex((c) => c.kind === 'agent' && c.label === label)
}
