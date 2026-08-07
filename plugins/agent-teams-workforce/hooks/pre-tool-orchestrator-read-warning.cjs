#!/usr/bin/env node
/**
 * PreToolUse hook — records an orchestrator read of a source/config file.
 *
 * Fires on: Read and Grep against source, config, and test paths.
 * Action: records the read and states what it costs.
 *
 * This hook does not deny, and it grants no exemption. It used to ask the
 * orchestrator whether it intended to edit the file this turn and to proceed if
 * so — an exemption whose predicate is the actor's own unobservable future
 * intent (REQ-ORCH-02, root cause B). Editing source from the orchestrator is
 * now denied outright by pre-tool-orchestrator-edit-guard.cjs, so the question
 * no longer has anything to gate: there is no read that is a legitimate step
 * toward an orchestrator edit.
 *
 * What remains is a real cost with no rule attached — the shared context window
 * — so the emitted text states it and nothing more.
 */

const fs = require('node:fs');
const { guardsApplyHere } = require('./lib/plugin-scope.cjs');

const SOURCE_FILE_EXTENSIONS =
  /\.(py|toml|yaml|yml|js|cjs|mjs|ts|jsx|tsx|json|cfg|ini|env|sh|bash|go|rs|rb|java|c|cpp|h|hpp)$/i;
const TEST_PATH_PATTERN = /\/(tests?|spec|__tests?__)\/|test_[^/]+\.(py|js|ts)$/i;

/**
 * @param {string} filePath
 * @returns {boolean}
 */
function isSourceOrConfigFile(filePath) {
  if (!filePath) return false;
  return SOURCE_FILE_EXTENSIONS.test(filePath) || TEST_PATH_PATTERN.test(filePath);
}

/**
 * Returns true if the path resolves to a directory on disk.
 * Safe to call on non-existent paths — returns false on any error.
 * Note: .md files (e.g. backlog per-item files) are excluded by isSourceOrConfigFile already;
 * this function only fires for paths that already passed the directory check branch.
 *
 * @param {string} targetPath
 * @returns {boolean}
 */
function isDirectory(targetPath) {
  try {
    return fs.statSync(targetPath).isDirectory();
  } catch {
    return false;
  }
}

/**
 * Returns true if the path looks like a directory by convention:
 * - ends with '/' or '\'  (explicit directory separator)
 * - last path segment contains no '.' character (no file extension)
 *
 * @param {string} targetPath
 * @returns {boolean}
 */
function looksLikeDirectory(targetPath) {
  if (!targetPath) return false;
  if (targetPath.endsWith('/') || targetPath.endsWith('\\')) return true;
  const lastSegment = targetPath.split(/[\\/]/).filter(Boolean).pop() || '';
  return !lastSegment.includes('.');
}

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  input += chunk;
});
process.stdin.on('end', () => {
  let data = {};
  try {
    data = JSON.parse(input);
  } catch {
    process.stdout.write(JSON.stringify({}));
    process.exit(0);
  }

  // Skip warning for subagent sessions — subagents SHOULD read source files.
  // When running inside a subagent, the hook input includes agent_id and agent_type
  // fields that are absent in the orchestrator session. Verified 2026-03-23.
  if (data.agent_id) {
    process.stdout.write(JSON.stringify({}));
    process.exit(0);
  }

  // Out of scope in the monorepo that builds this plugin.
  if (!guardsApplyHere(data)) {
    process.stdout.write(JSON.stringify({}));
    process.exit(0);
  }

  const toolName = data.tool_name || '';
  const toolInput = data.tool_input || {};

  let targetPath = '';
  let shouldWarn = false;
  if (toolName === 'Read') {
    targetPath = toolInput.file_path || '';
    shouldWarn = isSourceOrConfigFile(targetPath);
  } else if (toolName === 'Grep') {
    targetPath = toolInput.path || '';
    shouldWarn =
      isSourceOrConfigFile(targetPath) || isDirectory(targetPath) || looksLikeDirectory(targetPath);
  } else {
    process.stdout.write(JSON.stringify({}));
    process.exit(0);
  }

  if (!shouldWarn) {
    process.stdout.write(JSON.stringify({}));
    process.exit(0);
  }

  const output = {
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      additionalContext: `<orchestrator-read-record>
ORCHESTRATOR SOURCE READ RECORDED.

File: ${targetPath}

This session is the orchestrator. Its context window is the one shared resource
in the run that cannot be refreshed; every subagent gets a fresh one per task.
Source content read here is spent for the remainder of the session.

Editing this file from the orchestrator is separately blocked by the edit guard
(REQ-ORCH-01), so reading it is not a step toward changing it.

What a delegated read costs instead: nothing from this window. Pass the path
into the agent's prompt and the agent reads it in its own context, verifies it
there, and returns a verdict.
</orchestrator-read-record>`,
    },
  };

  process.stdout.write(JSON.stringify(output));
  process.exit(0);
});
