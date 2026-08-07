'use strict';

/**
 * Which artifacts the current session has produced, read from its transcript.
 *
 * Shared by the guards that enforce "the producer may not be the verifier". Both
 * need the same answer to the same question — what did THIS session write? — and
 * they must not drift apart, because a disagreement between them would let one
 * gate pass work the other would deny.
 */

const fs = require('node:fs');
const path = require('node:path');

/** Tools whose successful use means this session produced an artifact. */
const PRODUCING_TOOLS = new Set(['Edit', 'Write', 'MultiEdit', 'NotebookEdit']);

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


module.exports = { PRODUCING_TOOLS, producedPaths, commandReferences };
