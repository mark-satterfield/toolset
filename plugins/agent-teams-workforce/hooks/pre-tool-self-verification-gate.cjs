#!/usr/bin/env node
'use strict';

/**
 * PreToolUse hook — REQ-ORCH-03 (ssbd-ja5d, root cause C).
 *
 * "The producer may not be the verifier." The doctrine already says no agent
 * approves its own output; the orchestrator was the one actor exempt from it
 * in practice, because nothing stopped it from editing a file and then
 * inspecting that same file to satisfy itself the edit was good.
 *
 * Session production state is read from the transcript named by the hook
 * input's `transcript_path` — the only session-history channel present in the
 * PreToolUse contract, and machine-observable rather than self-attested.
 *
 * Decision order:
 *   1. unparseable input                    -> exit 0 (other Bash guards still run)
 *   2. subagent session                     -> exit 0
 *   3. non-Bash tool                        -> exit 0
 *   4. session produced nothing             -> exit 0 (AC-ORCH-03f part 1)
 *   5. network fetch after producing        -> exit 2
 *   6. git inspection naming a produced path-> exit 2 (AC-ORCH-03b)
 *   7. anything else                        -> exit 0
 */

const fs = require('node:fs');
const path = require('node:path');
const { guardsApplyHere } = require('./lib/plugin-scope.cjs');

/** Tools whose successful use means this session produced an artifact. */
const PRODUCING_TOOLS = new Set(['Edit', 'Write', 'MultiEdit', 'NotebookEdit']);

/** git subcommands that inspect content rather than change it. */
const GIT_INSPECTION = /\bgit\s+(?:diff|log|show|blame|status|cat-file)\b/;

/** Commands that fetch a deployed artifact over the network. */
const NETWORK_FETCH = /(?:^|[\s|;&(])(?:curl|wget|http|https|httpie|xh)\b/;

/** Reads all of stdin synchronously; returns '' when unreadable. */
function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

/**
 * Extracts the set of file paths this session successfully produced, by
 * scanning the session transcript for Edit/Write/MultiEdit/NotebookEdit
 * tool_use blocks. A tool_use whose matching tool_result reports an error is
 * not counted — a failed write produced nothing.
 *
 * @param {string} transcriptPath
 * @returns {string[]} absolute paths, deduplicated
 */
function producedPaths(transcriptPath) {
  if (!transcriptPath) return [];

  let raw;
  try {
    raw = fs.readFileSync(transcriptPath, 'utf8');
  } catch {
    return [];
  }

  /** @type {Map<string, string>} tool_use id -> produced path */
  const pending = new Map();
  /** @type {Set<string>} tool_use ids whose result was an error */
  const failed = new Set();

  for (const line of raw.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    let entry;
    try {
      entry = JSON.parse(trimmed);
    } catch {
      continue; // a partial or corrupt line tells us nothing
    }

    const content = entry?.message?.content;
    if (!Array.isArray(content)) continue;

    for (const block of content) {
      if (block?.type === 'tool_use' && PRODUCING_TOOLS.has(String(block.name ?? ''))) {
        const input = block.input ?? {};
        const target = input.file_path ?? input.notebook_path ?? '';
        if (target && block.id) pending.set(String(block.id), String(target));
      }
      if (block?.type === 'tool_result' && block.is_error === true && block.tool_use_id) {
        failed.add(String(block.tool_use_id));
      }
    }
  }

  const out = new Set();
  for (const [id, target] of pending) {
    if (!failed.has(id)) out.add(target);
  }
  return [...out];
}

/**
 * True when the command text references the given produced path — either by
 * its full path or by its basename as a whole token.
 */
function commandReferences(command, producedPath) {
  if (command.includes(producedPath)) return true;
  const base = path.basename(producedPath);
  if (!base) return false;
  const escaped = base.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(?:^|[\\s/'"=])${escaped}(?:$|[\\s'"),;])`).test(command);
}

/** Emits denial feedback on stderr and terminates with exit 2. */
function deny(lines) {
  process.stderr.write(
    `${['--- Self-Verification Blocked ---', '', ...lines, '--- End ---'].join('\n')}\n`,
  );
  process.exit(2);
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

  if (String(event.tool_name ?? '') !== 'Bash') {
    process.exit(0);
  }

  const command = String((event.tool_input ?? {}).command ?? '');
  if (!command.trim()) {
    process.exit(0);
  }

  const produced = producedPaths(String(event.transcript_path ?? ''));
  if (produced.length === 0) {
    // Nothing produced this session — normal inspection access.
    process.exit(0);
  }

  if (NETWORK_FETCH.test(command)) {
    deny([
      `Command: ${command.trim()}`,
      '',
      `This session has produced ${produced.length} artifact(s):`,
      ...produced.slice(0, 5).map((p) => `  ${p}`),
      produced.length > 5 ? `  ... and ${produced.length - 5} more` : '',
      '',
      'Fetching a deployed endpoint after producing the change that went into it',
      'is the producer verifying its own output.',
      '',
      'Route verification to an agent that did not write the change:',
      '  - smoke-test-author / the deploy workflow for post-deployment checks',
      '  - integration-testing-lead for endpoint behavior',
      '',
      'Rule source: REQ-ORCH-03 (ssbd-ja5d) — the producer may not be the verifier',
    ].filter(Boolean));
  }

  if (GIT_INSPECTION.test(command)) {
    const hit = produced.find((p) => commandReferences(command, p));
    if (hit) {
      deny([
        `Command: ${command.trim()}`,
        `Artifact: ${hit}`,
        '',
        'This session produced that file, and is now inspecting it to judge the',
        'result. That is the producer verifying its own output.',
        '',
        'Route verification to an agent that did not write the change:',
        '  - code-correctness-reviewer for behavior preservation',
        '  - test-coverage-gap-reviewer for coverage against acceptance criteria',
        '  - the tdd-refactor / integration workflows, which build the review in',
        '',
        'git access is unaffected for files this session did not produce.',
        '',
        'Rule source: REQ-ORCH-03 (ssbd-ja5d) — the producer may not be the verifier',
      ]);
    }
  }

  process.exit(0);
}

main();
