'use strict';

/**
 * Test-only harness for the agent-teams-workforce hook guards.
 *
 * Bug: ssbd-ja5d — "Orchestrator role is not enforceable".
 * This module is TEST SUPPORT CODE ONLY. It spawns the guard scripts exactly as
 * Claude Code would (stdin = the PreToolUse/PostToolUse hook input JSON) and
 * resolves guards from the plugin's registered hooks/hooks.json matchers, so
 * that tests exercise the real enforcement surface rather than a hand-picked
 * script path.
 *
 * Guard resolution contract (mirrors Claude Code hook semantics):
 *   - a hooks.json PreToolUse/PostToolUse entry applies to a tool call when its
 *     `matcher` value, evaluated as a regular expression, matches the tool name
 *     (full match, as with "Read|Grep").
 *   - the entry's `command` has ${CLAUDE_PLUGIN_ROOT} substituted with the
 *     plugin root, then runs with the hook input JSON on stdin.
 *   - exit 0 = allow (optionally with JSON on stdout), exit 2 = deny with
 *     feedback on stderr.
 */

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

/** Absolute root of the agent-teams-workforce plugin inside this repo. */
const PLUGIN_ROOT = path.resolve(__dirname, '..', '..', '..');

/** The registered hook configuration under test (the repo copy — the SUT). */
const HOOKS_JSON_PATH = path.join(PLUGIN_ROOT, 'hooks', 'hooks.json');

/** Direct paths to the existing hook scripts (for regression anchors). */
const HOOK_SCRIPTS = {
  readWarning: path.join(PLUGIN_ROOT, 'hooks', 'pre-tool-orchestrator-read-warning.cjs'),
  diagnosticGate: path.join(PLUGIN_ROOT, 'hooks', 'pre-tool-diagnostic-command-gate.cjs'),
  bashMisuse: path.join(PLUGIN_ROOT, 'hooks', 'prevent-bash-tool-misuse.cjs'),
  blockExplore: path.join(PLUGIN_ROOT, 'hooks', 'pre-tool-block-explore-for-analysis.cjs'),
  gitignoreEditGuard: path.resolve(
    PLUGIN_ROOT,
    '..',
    'gitignore-guardian',
    'hooks',
    'gitignore-edit-guard.sh',
  ),
};

/**
 * Phrases whose presence in a guard's emitted text means the guard is granting
 * an exemption conditioned on the actor's own (unobservable, self-declared)
 * intent — forbidden by REQ-ORCH-02 / root cause (B).
 */
const INTENT_EXEMPTION_MARKERS = [
  'Will you Edit or Write this file in this same turn',
  'If YES: proceed',
  'proceed if',
  'you can make the call',
  'EXCEPTION:',
];

/** Loads and parses the plugin hooks.json. */
function loadHooksConfig() {
  const raw = fs.readFileSync(HOOKS_JSON_PATH, 'utf8');
  return JSON.parse(raw);
}

/** Tokenizes a hook command string, honoring single/double quotes. */
function tokenizeCommand(command) {
  const tokens = [];
  const re = /"([^"]*)"|'([^']*)'|(\S+)/g;
  let m;
  while ((m = re.exec(command)) !== null) {
    tokens.push(m[1] ?? m[2] ?? m[3]);
  }
  return tokens;
}

/**
 * Resolves every registered guard for the given hook event + tool name.
 * Returns [] when no registered matcher matches the tool name — which is
 * itself the defect several tests assert against.
 *
 * @param {string} eventName  e.g. 'PreToolUse', 'PostToolUse'
 * @param {string} toolName   e.g. 'Write', 'Bash', 'Workflow'
 * @returns {{matcher: string, command: string, runner: string, args: string[], scriptPath: string}[]}
 */
function resolveGuardsForTool(eventName, toolName) {
  const config = loadHooksConfig();
  const entries = (config.hooks && config.hooks[eventName]) || [];
  const resolved = [];
  for (const entry of entries) {
    const matcher = entry.matcher;
    if (typeof matcher === 'string') {
      let re;
      try {
        re = new RegExp(`^(?:${matcher})$`);
      } catch {
        continue; // an unparseable matcher matches nothing
      }
      if (!re.test(toolName)) continue;
    }
    for (const h of entry.hooks || []) {
      const substituted = String(h.command || '').replaceAll('${CLAUDE_PLUGIN_ROOT}', PLUGIN_ROOT);
      const tokens = tokenizeCommand(substituted);
      const runner = tokens[0] || '';
      const args = tokens.slice(1);
      const scriptPath = args.find((t) => t.includes(path.sep)) || args[0] || '';
      resolved.push({ matcher: matcher ?? '(none)', command: substituted, runner, args, scriptPath });
    }
  }
  return resolved;
}

/**
 * Runs a resolved guard with the given stdin text, exactly as the hook runner
 * would. Returns { status, stdout, stderr }.
 */
function runGuard(guard, stdinText, opts = {}) {
  const executable = guard.runner === 'node' ? process.execPath : guard.runner;
  const result = spawnSync(executable, guard.args, {
    input: stdinText,
    encoding: 'utf8',
    timeout: 15000,
    cwd: opts.cwd,
  });
  return {
    status: result.status,
    stdout: result.stdout ?? '',
    stderr: result.stderr ?? '',
    error: result.error,
  };
}

/** Runs a hook script directly by path (regression anchors). */
function runScript(scriptPath, stdinText, opts = {}) {
  const runner = opts.runner === 'bash' ? 'bash' : process.execPath;
  return runGuard({ runner: runner === 'bash' ? 'bash' : 'node', args: [scriptPath] }, stdinText, opts);
}

/**
 * Builds a hook-input JSON document. Omit agentId for an orchestrator
 * (top-level) session; provide it for a subagent session.
 */
function makeEvent({
  eventName = 'PreToolUse',
  toolName,
  toolInput = {},
  toolResponse,
  agentId,
  transcriptPath,
  cwd,
  sessionId,
} = {}) {
  const event = {
    session_id: sessionId ?? 'ssbd-ja5d-unit-session',
    transcript_path: transcriptPath ?? path.join(os.tmpdir(), 'ssbd-ja5d-no-transcript.jsonl'),
    cwd: cwd ?? PLUGIN_ROOT,
    hook_event_name: eventName,
    tool_name: toolName,
    tool_input: toolInput,
  };
  if (toolResponse !== undefined) event.tool_response = toolResponse;
  if (agentId) {
    event.agent_id = agentId;
    event.agent_type = 'worker';
  }
  return JSON.stringify(event);
}

/** Creates a disposable temp directory for probe files and transcripts. */
function makeTempDir(prefix = 'ssbd-ja5d-') {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

/** Removes a temp directory tree. */
function removeTempDir(dir) {
  fs.rmSync(dir, { recursive: true, force: true });
}

/** Writes a probe file and returns its absolute path. */
function writeProbe(dir, name, content) {
  const p = path.join(dir, name);
  fs.writeFileSync(p, content, 'utf8');
  return p;
}

/**
 * Writes a session transcript fixture (JSONL, Claude Code transcript shape)
 * and returns its absolute path.
 *
 * `producedPath` (optional): when given, the transcript records a successful
 * Edit tool_use against that path — i.e. "this session produced this
 * artifact". When omitted, the transcript records no Write/Edit at all.
 */
function writeTranscript(dir, name, producedPath) {
  const lines = [
    JSON.stringify({
      type: 'user',
      message: { role: 'user', content: 'orchestrate the pipeline' },
    }),
  ];
  if (producedPath) {
    lines.push(
      JSON.stringify({
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'toolu_ssbd_ja5d_01',
              name: 'Edit',
              input: {
                file_path: producedPath,
                old_string: 'SENTINEL_ORIGINAL',
                new_string: 'SENTINEL_EDITED',
              },
            },
          ],
        },
      }),
      JSON.stringify({
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'toolu_ssbd_ja5d_01',
              content: 'The file has been updated.',
            },
          ],
        },
      }),
    );
  }
  const p = path.join(dir, name);
  fs.writeFileSync(p, `${lines.join('\n')}\n`, 'utf8');
  return p;
}

/** True when a guard's stdout is an empty decision ('' or {}). */
function isEmptyDecision(stdout) {
  const trimmed = String(stdout).trim();
  if (trimmed === '') return true;
  try {
    const parsed = JSON.parse(trimmed);
    return (
      parsed !== null && typeof parsed === 'object' && Object.keys(parsed).length === 0
    );
  } catch {
    return false;
  }
}

module.exports = {
  PLUGIN_ROOT,
  HOOKS_JSON_PATH,
  HOOK_SCRIPTS,
  INTENT_EXEMPTION_MARKERS,
  loadHooksConfig,
  resolveGuardsForTool,
  runGuard,
  runScript,
  makeEvent,
  makeTempDir,
  removeTempDir,
  writeProbe,
  writeTranscript,
  isEmptyDecision,
};
