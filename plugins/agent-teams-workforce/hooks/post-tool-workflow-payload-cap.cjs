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

/** Maximum lines a workflow completion may return into orchestrator context. */
const MAX_PAYLOAD_LINES = 15;

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

  const text = asText(event.tool_response);
  if (!text) {
    process.exit(0);
  }

  const lines = text.split('\n');
  if (lines.length <= MAX_PAYLOAD_LINES) {
    // Under the cap: pass through unchanged and say nothing.
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
      `Payload: ${lines.length} lines (cap ${MAX_PAYLOAD_LINES})`,
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
