'use strict';

/**
 * Shared harness for the ssbd-ja5d security test suite.
 *
 * Invokes PreToolUse guard hooks exactly as Claude Code does: the registered
 * command line is executed through `bash -c` with CLAUDE_PLUGIN_ROOT in the
 * environment and the hook event JSON piped to stdin. Assertions are made on
 * the terminal exit code, stdout payload, and stderr text — the only three
 * channels a hook has.
 *
 * Threat source: bug ssbd-ja5d (orchestrator role is not enforceable).
 * This file is test infrastructure only. It contains no production logic.
 */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

/** Absolute root of the agent-teams-workforce plugin under test (repo source copy). */
const PLUGIN_ROOT = path.resolve(__dirname, '..', '..');

/** Absolute root of the gitignore-guardian plugin (regression pins, AC-ORCH-10c). */
const GITIGNORE_GUARDIAN_ROOT = path.resolve(PLUGIN_ROOT, '..', 'gitignore-guardian');

/** SkillSpoke repo root for the cross-repo policy contract (AC-ORCH-09*). */
const SKILLSPOKE_REPO =
  process.env.SKILLSPOKE_REPO ||
  '/Users/msat1971/projects/SkillSpoke/apps/personal-agent/SkillSpoke';

/**
 * Loads and parses a plugin hooks.json.
 * @param {string} [pluginRoot]
 * @returns {object}
 */
function loadHooksConfig(pluginRoot = PLUGIN_ROOT) {
  const p = path.join(pluginRoot, 'hooks', 'hooks.json');
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

/**
 * Returns hook entries registered for a lifecycle event ('PreToolUse', 'SessionStart', ...).
 * @param {object} config
 * @param {string} eventName
 * @returns {Array<object>}
 */
function entriesForEvent(config, eventName) {
  return (config.hooks && config.hooks[eventName]) || [];
}

/**
 * Returns every registered PreToolUse guard whose matcher regex matches the
 * given tool name, per AC-ORCH-01c: "each PreToolUse entry's matcher value is
 * evaluated as a regular expression against the four literal strings".
 * Evaluation is standard unanchored regex `.test()` — the same permissive
 * reading Claude Code applies.
 *
 * @param {string} toolName e.g. 'Write'
 * @param {string} [pluginRoot]
 * @returns {Array<{matcher: string, command: string, scriptPath: string|null}>}
 */
function guardsMatchingTool(toolName, pluginRoot = PLUGIN_ROOT) {
  const config = loadHooksConfig(pluginRoot);
  const out = [];
  for (const entry of entriesForEvent(config, 'PreToolUse')) {
    const matcher = String(entry.matcher || '');
    let re;
    try {
      re = new RegExp(matcher);
    } catch {
      continue; // an unparseable matcher matches nothing
    }
    if (!re.test(toolName)) continue;
    for (const h of entry.hooks || []) {
      out.push({
        matcher,
        command: h.command,
        scriptPath: extractScriptPath(h.command, pluginRoot),
      });
    }
  }
  return out;
}

/**
 * Extracts the script file path from a registered hook command line and
 * resolves ${CLAUDE_PLUGIN_ROOT}. Returns null when no path can be extracted.
 * @param {string} command
 * @param {string} pluginRoot
 * @returns {string|null}
 */
function extractScriptPath(command, pluginRoot) {
  const m = String(command).match(/(?:node|bash|sh|python3?)\s+"?([^\s"]+)"?/);
  if (!m) return null;
  return m[1].replaceAll('${CLAUDE_PLUGIN_ROOT}', pluginRoot);
}

/**
 * Runs one registered hook command exactly as Claude Code would: via
 * `bash -c`, with CLAUDE_PLUGIN_ROOT exported and the event piped to stdin.
 *
 * @param {string} command registered command line (may contain ${CLAUDE_PLUGIN_ROOT})
 * @param {object|string} hookInput event object, or a raw string for malformed-stdin cases
 * @param {{pluginRoot?: string}} [opts]
 * @returns {{status: number|null, stdout: string, stderr: string}}
 */
function runGuard(command, hookInput, opts = {}) {
  const input = typeof hookInput === 'string' ? hookInput : JSON.stringify(hookInput);
  const res = spawnSync('bash', ['-c', command], {
    input,
    encoding: 'utf8',
    env: { ...process.env, CLAUDE_PLUGIN_ROOT: opts.pluginRoot || PLUGIN_ROOT },
    timeout: 15000,
  });
  return { status: res.status, stdout: res.stdout ?? '', stderr: res.stderr ?? '' };
}

/**
 * Builds a PreToolUse hook event as Claude Code delivers it.
 * Omit agentId to model the top-level orchestrator session (the bug's actor);
 * pass a non-empty agentId to model a dispatched subagent.
 *
 * @param {{toolName: string, toolInput: object, agentId?: string, sessionId?: string,
 *          cwd?: string, transcriptPath?: string, extra?: object}} spec
 * @returns {object}
 */
function hookEvent(spec) {
  const evt = {
    session_id: spec.sessionId || 'ssbd-ja5d-security-test',
    transcript_path: spec.transcriptPath || path.join(os.tmpdir(), 'ssbd-ja5d-missing.jsonl'),
    cwd: spec.cwd || PLUGIN_ROOT,
    hook_event_name: 'PreToolUse',
    tool_name: spec.toolName,
    tool_input: spec.toolInput,
    ...(spec.extra || {}),
  };
  if (spec.agentId) {
    evt.agent_id = spec.agentId;
    evt.agent_type = 'specialist-subagent';
  }
  return evt;
}

/**
 * Creates a disposable fixture directory. Caller removes it with rmFixtureDir.
 * @param {string} label
 * @returns {string}
 */
function mkFixtureDir(label) {
  return fs.mkdtempSync(path.join(os.tmpdir(), `ssbd-ja5d-${label}-`));
}

/**
 * @param {string} dir
 * @returns {void}
 */
function rmFixtureDir(dir) {
  try {
    fs.rmSync(dir, { recursive: true, force: true });
  } catch {
    /* best-effort cleanup; fixture dirs live in tmpdir */
  }
}

/**
 * Writes a probe file containing exactly the given content and returns its path.
 * @param {string} dir
 * @param {string} name
 * @param {string} content
 * @returns {string}
 */
function writeProbe(dir, name, content) {
  const p = path.join(dir, name);
  fs.writeFileSync(p, content);
  return p;
}

/**
 * Writes a minimal session transcript (JSONL, Claude Code shape) recording a
 * prior successful Edit of `editedPath` in this session. Used to model the
 * AC-ORCH-03 GIVEN "has already issued a successful Edit against P in this
 * same session" — transcript_path is a real field of every hook input, so a
 * session-aware guard can observe it. If the implementation chooses a
 * different session-state mechanism, extend this fixture (do not weaken the
 * assertions that consume it).
 *
 * @param {string} dir
 * @param {string} editedPath
 * @returns {string} transcript path
 */
function writeTranscriptWithPriorEdit(dir, editedPath) {
  const lines = [
    JSON.stringify({
      type: 'assistant',
      message: {
        content: [
          {
            type: 'tool_use',
            id: 'toolu_sec_01',
            name: 'Edit',
            input: { file_path: editedPath, old_string: 'a', new_string: 'b' },
          },
        ],
      },
    }),
    JSON.stringify({
      type: 'user',
      message: {
        content: [
          { type: 'tool_result', tool_use_id: 'toolu_sec_01', content: 'The file has been updated.' },
        ],
      },
    }),
  ];
  const p = path.join(dir, 'transcript.jsonl');
  fs.writeFileSync(p, `${lines.join('\n')}\n`);
  return p;
}

/**
 * Writes an empty-session transcript (no prior Write/Edit) for AC-ORCH-03f.
 * @param {string} dir
 * @returns {string}
 */
function writeTranscriptWithoutEdits(dir) {
  const p = path.join(dir, 'transcript-clean.jsonl');
  fs.writeFileSync(
    p,
    `${JSON.stringify({ type: 'user', message: { content: [{ type: 'text', text: 'begin' }] } })}\n`,
  );
  return p;
}

/** Loads the authorization matrix artifact backing the matrix-driven tests. */
function loadAuthorizationMatrix() {
  const p = path.join(__dirname, 'authorization-matrix.json');
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

module.exports = {
  PLUGIN_ROOT,
  GITIGNORE_GUARDIAN_ROOT,
  SKILLSPOKE_REPO,
  loadHooksConfig,
  entriesForEvent,
  guardsMatchingTool,
  extractScriptPath,
  runGuard,
  hookEvent,
  mkFixtureDir,
  rmFixtureDir,
  writeProbe,
  writeTranscriptWithPriorEdit,
  writeTranscriptWithoutEdits,
  loadAuthorizationMatrix,
};
