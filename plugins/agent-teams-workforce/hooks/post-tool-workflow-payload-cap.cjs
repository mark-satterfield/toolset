#!/usr/bin/env node
'use strict';

/**
 * PostToolUse hook — REQ-ORCH-08 (ssbd-ja5d, root cause H).
 *
 * A workflow's full completion payload is the workflow's internal record, not
 * the orchestrator's. Letting it flow back verbatim fills the one context
 * window that cannot be refreshed, and it is the mechanism by which an
 * orchestrator accumulates enough detail to start second-guessing the agents
 * that produced it.
 *
 * The cap was written down as prose and never enforced. This is the layer.
 * Payloads at or under the cap pass through untouched; oversized payloads are
 * rejected with exit 2 so the workflow returns a verdict instead of a dump.
 *
 * Decision order:
 *   1. unparseable input   -> exit 0  (the tool already ran; nothing to protect)
 *   2. subagent session    -> exit 0
 *   3. payload <= cap      -> exit 0, silent, unmodified   (AC-ORCH-08c)
 *   4. payload  > cap      -> exit 2                       (AC-ORCH-04a)
 */

const fs = require('node:fs');
const { guardsApplyHere } = require('./lib/plugin-scope.cjs');

/**
 * Caps on what a completion may return into orchestrator context.
 *
 * The original cap was 15 lines, set when a single workflow completion could eat
 * a large fraction of the window. On a 1M-token context that is far tighter than
 * the constraint warrants: fifteen lines cannot carry a gate verdict with
 * per-criterion evidence, so workflows were truncating things the orchestrator
 * needed in order to route correctly.
 *
 * Characters matter as much as lines — one 8,000-character line passed the old
 * cap while sixteen short ones failed — so both are measured and either trips it.
 */
const MAX_PAYLOAD_LINES = 200;
const MAX_PAYLOAD_CHARS = 24000;

/** Reads all of stdin synchronously; returns '' when unreadable. */
function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

/**
 * Renders a tool response as text for line counting. Objects are stringified
 * so a structured return is measured by the shape it will occupy in context.
 */
function asText(toolResponse) {
  if (toolResponse === undefined || toolResponse === null) return '';
  if (typeof toolResponse === 'string') return toolResponse;
  try {
    return JSON.stringify(toolResponse, null, 2);
  } catch {
    return String(toolResponse);
  }
}

function main() {
  const raw = readStdin();
  if (!raw.trim()) {
    process.exit(0);
  }

  let event;
  try {
    event = JSON.parse(raw);
  } catch {
    process.exit(0);
  }

  if (event.agent_id) {
    process.exit(0);
  }

  // Out of scope in the monorepo that builds this plugin.
  if (!guardsApplyHere(event)) {
    process.exit(0);
  }

  const text = asText(event.tool_response);
  if (!text) {
    process.exit(0);
  }

  const lines = text.split('\n');
  const overLines = lines.length > MAX_PAYLOAD_LINES;
  const overChars = text.length > MAX_PAYLOAD_CHARS;
  if (!overLines && !overChars) {
    // Under both caps: pass through unchanged and say nothing.
    process.exit(0);
  }

  const toolName = String(event.tool_name ?? 'Workflow');
  const workflowName = String((event.tool_input ?? {}).name ?? '(inline script)');

  process.stderr.write(
    `${[
      '--- Workflow Payload Over Cap ---',
      '',
      `Tool: ${toolName}`,
      `Workflow: ${workflowName}`,
      `Payload: ${lines.length} lines (cap ${MAX_PAYLOAD_LINES}), ${text.length} chars (cap ${MAX_PAYLOAD_CHARS})`,
      `Over on: ${[overLines && 'lines', overChars && 'characters'].filter(Boolean).join(' and ')}`,
      '',
      'A completion payload this size belongs in the run transcript, not in the',
      'orchestrator context window. The orchestrator needs the verdict, not the',
      'working record that produced it.',
      '',
      'Have the workflow return a short structured result:',
      '  { ok, phase, verdict, escalation, artifactPaths }',
      '',
      'The full detail stays readable in the run transcript and journal.jsonl,',
      'and any agent that needs it can read it in its own context.',
      '',
      'Rule source: REQ-ORCH-08 (ssbd-ja5d) — completion payload cap',
      '--- End ---',
    ].join('\n')}\n`,
  );
  process.exit(2);
}

main();
