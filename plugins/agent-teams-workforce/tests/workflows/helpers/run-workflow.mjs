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
import { assertRunnerLoadable } from '../../../scripts/workflow-runner-constraints.mjs'

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

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
 * @returns {Promise<{result: any, calls: Array}>}
 */
export async function runWorkflowScript(absPath, { args = {}, agentImpl, workflowImpl } = {}) {
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
  const log = () => {}
  const parallel = async (thunks = []) => {
    const out = []
    for (const t of thunks) out.push(await t())
    return out
  }

  const fn = new AsyncFunction('args', 'agent', 'workflow', 'phase', 'log', 'parallel', transformed)
  const result = await fn(args, agent, workflow, phase, log, parallel)
  return { result, calls }
}

/** All agent() dispatches with the given label. */
export function agentCalls(calls, label) {
  return calls.filter((c) => c.kind === 'agent' && c.label === label)
}

/** All workflow() dispatches with the given workflow name. */
export function workflowCalls(calls, name) {
  return calls.filter((c) => c.kind === 'workflow' && c.name === name)
}

/** Index of the first agent() dispatch with the given label, or -1. */
export function agentCallIndex(calls, label) {
  return calls.findIndex((c) => c.kind === 'agent' && c.label === label)
}
