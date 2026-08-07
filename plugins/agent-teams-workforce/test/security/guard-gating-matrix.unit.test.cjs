'use strict';

/**
 * ssbd-ja5d / REQ-ORCH-04 — for each of the four forbidden orchestrator
 * actions there must be a guard that (a) evaluates the call when agent_id is
 * absent and terminates with exit code 2 on a violation, and (b) preserves
 * the subagent exemption (non-empty agent_id => exit 0).
 *
 * The four forbidden actions (single-sentence root cause of ssbd-ja5d):
 *   1. editing code
 *   2. verifying its own output
 *   3. dispatching by name against a stale snapshot
 *   4. absorbing a full workflow payload
 *
 * Threat model entries: root cause (D) — hooks gate only via agent_id
 * inversion and warnings; root cause (B) — advisory additionalContext is not
 * enforcement; the single working primitive (PreToolUse exit 2) is applied to
 * none of the four actions.
 *
 * INTENDED RED STATE:
 *   AC-ORCH-04a/04c fail per category — editing-code and dispatch and payload
 *   guards do not exist (discovery failure), and the self-verification
 *   category's only firing guard (the diagnostic gate) responds with exit 0 +
 *   additionalContext advisory instead of exit 2.
 *   AC-ORCH-04b is a subagent-exemption pin that passes today.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const {
  PLUGIN_ROOT,
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
} = require('./helpers.cjs');

test('AC-ORCH-04a/04c category 1 (editing code): a guard exists for Write with no agent_id and terminates with exit 2 on a code write', () => {
  const dir = mkFixtureDir('ac04a-edit');
  try {
    const probe = writeProbe(dir, 'probe.py', 'SENTINEL_ORIGINAL');
    const guards = guardsMatchingTool('Write');
    assert.ok(
      guards.length > 0,
      'MISSING CONTROL [root cause A]: no PreToolUse guard covers the forbidden action ' +
        '"editing code" (no Edit|Write|MultiEdit|NotebookEdit matcher in hooks.json)',
    );
    const evt = hookEvent({ toolName: 'Write', toolInput: { file_path: probe, content: 'x' } });
    const outcomes = guards.map((g) => ({ g, r: runGuard(g.command, evt) }));
    assert.ok(
      outcomes.some((o) => o.r.status === 2),
      `AC-ORCH-04a: the editing-code guard must terminate with exit 2 on a violating Write; ` +
        `observed: [${outcomes.map((o) => o.r.status).join(', ')}]`,
    );
  } finally {
    rmFixtureDir(dir);
  }
});

test('AC-ORCH-04a/04c category 2 (self-verification): a Bash guard blocks with exit 2, and no guard answers the violation with an exit-0 advisory only', () => {
  const dir = mkFixtureDir('ac04a-verify');
  try {
    const produced = writeProbe(dir, 'handler.py', 'SENTINEL_ORIGINAL');
    const transcriptPath = writeTranscriptWithPriorEdit(dir, produced);
    const guards = guardsMatchingTool('Bash');
    assert.ok(guards.length > 0, 'harness precondition: Bash guards registered');

    // `pytest` is a self-verification command the diagnostic gate already
    // recognizes (DIAGNOSTIC_PATTERNS:27) — today it warns and exits 0.
    // `git show HEAD -- <produced>` is self-verification it does not even see.
    for (const command of ['pytest', `git show HEAD -- ${produced}`]) {
      const evt = hookEvent({ toolName: 'Bash', toolInput: { command }, transcriptPath });
      const outcomes = guards.map((g) => ({ g, r: runGuard(g.command, evt) }));

      assert.ok(
        outcomes.some((o) => o.r.status === 2),
        `AC-ORCH-04a [root cause C]: self-verification command "${command}" in an orchestrator ` +
          `session must be denied with exit 2; observed: ` +
          `[${outcomes.map((o) => `${o.g.matcher}:${o.r.status}`).join(', ')}]`,
      );

      for (const o of outcomes) {
        const advisoryOnly =
          o.r.status === 0 && /hookSpecificOutput/.test(o.r.stdout) && /additionalContext/.test(o.r.stdout);
        assert.ok(
          !advisoryOnly,
          `AC-ORCH-04c [root cause B]: guard "${path.basename(o.g.scriptPath || o.g.command)}" ` +
            `responded to the violating command "${command}" with exit 0 plus an ` +
            `additionalContext advisory as its only response. Advisory text the actor may ` +
            `disregard is not enforcement — the guard must exit 2.`,
        );
      }
    }
  } finally {
    rmFixtureDir(dir);
  }
});

test('AC-ORCH-04a/04c category 3 (dispatch-by-name against a stale snapshot): a guard is registered for workflow dispatch', () => {
  const dispatchGuards = [
    ...guardsMatchingTool('Workflow'),
    // A dispatch guard may alternatively hook the generic agent-dispatch tools
    // with staleness logic; count those only if their script mentions the
    // snapshot/digest concern at all.
    ...guardsMatchingTool('Task').filter((g) => scriptMentionsStaleness(g)),
  ];
  assert.ok(
    dispatchGuards.length > 0,
    'MISSING CONTROL [root cause F]: no PreToolUse guard covers the forbidden action ' +
      '"dispatching by name against a stale registry snapshot". ROUTING.md:88/:101 mandate ' +
      'name dispatch, name resolution uses the session-start snapshot, and nothing detects a ' +
      'mid-session script edit (the stale deploy.js symptom).',
  );
});

test('AC-ORCH-04a/04c category 4 (absorbing full payloads): a completion-payload guard is registered', () => {
  const config = loadHooksConfig();
  const candidateEvents = ['PostToolUse', 'SubagentStop', 'Stop'];
  const registered = candidateEvents.flatMap((evtName) =>
    entriesForEvent(config, evtName).flatMap((e) => e.hooks || []),
  );
  assert.ok(
    registered.length > 0,
    'MISSING CONTROL [root cause H]: no PostToolUse/SubagentStop/Stop hook exists to cap a ' +
      'workflow completion payload before it enters the orchestrator context. The 15-line rule ' +
      'exists only as mission prose (implement-all-prds.md:132), which no hook inspects.',
  );
});

test('AC-ORCH-04b (pin): with a non-empty agent_id, each existing guard exits 0 and emits nothing or an empty JSON object', () => {
  const dir = mkFixtureDir('ac04b');
  try {
    const probe = writeProbe(dir, 'probe.py', 'SENTINEL_ORIGINAL');
    // Violating inputs per existing guard category, per the AC's citations:
    // read-warning:79, diagnostic-gate:67, bash-misuse:128, block-explore:142.
    const cases = [
      { tool: 'Read', toolInput: { file_path: probe } },
      { tool: 'Bash', toolInput: { command: 'pytest' } },
      { tool: 'Bash', toolInput: { command: 'cat config.py' } },
      {
        tool: 'Task',
        toolInput: {
          subagent_type: 'Explore',
          description: 'analyze the architecture',
          prompt: 'analyze and review the design',
        },
      },
    ];
    for (const c of cases) {
      const guards = guardsMatchingTool(c.tool);
      assert.ok(guards.length > 0, `harness precondition: guards registered for ${c.tool}`);
      const evt = hookEvent({ toolName: c.tool, toolInput: c.toolInput, agentId: 'subagent-77' });
      for (const g of guards) {
        const r = runGuard(g.command, evt);
        assert.equal(
          r.status,
          0,
          `AC-ORCH-04b: guard (matcher "${g.matcher}") must preserve the subagent exemption ` +
            `for ${c.tool}; stderr: ${r.stderr}`,
        );
        const body = r.stdout.trim();
        const emptyObject = body === '' || JSON.stringify(JSON.parse(body)) === '{}';
        assert.ok(
          emptyObject,
          `AC-ORCH-04b: guard (matcher "${g.matcher}") must emit nothing or an empty JSON ` +
            `object for a subagent; emitted: ${body}`,
        );
      }
    }
  } finally {
    rmFixtureDir(dir);
  }
});

/**
 * True when a guard's script file exists and mentions snapshot/digest/staleness.
 * @param {{scriptPath: string|null}} guard
 * @returns {boolean}
 */
function scriptMentionsStaleness(guard) {
  const fs = require('node:fs');
  if (!guard.scriptPath) return false;
  try {
    const src = fs.readFileSync(guard.scriptPath.replaceAll('${CLAUDE_PLUGIN_ROOT}', PLUGIN_ROOT), 'utf8');
    return /stale|snapshot|sha-?256|digest/i.test(src);
  } catch {
    return false;
  }
}
