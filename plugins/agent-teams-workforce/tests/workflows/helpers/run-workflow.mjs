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

import { readFileSync } from 'node:fs'

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
  // The runner accepts `export const <name> = ...` at script top level; a plain
  // AsyncFunction body does not. Neutralize the export keyword only — everything
  // else runs verbatim.
  const transformed = raw.replace(/^export\s+const\s+/gm, 'const ')

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
