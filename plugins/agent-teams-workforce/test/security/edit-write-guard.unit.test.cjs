'use strict';

/**
 * ssbd-ja5d / REQ-ORCH-01 — the orchestrator must be mechanically blocked
 * from editing code, by a PreToolUse guard that exits 2.
 *
 * Threat model entry: root cause (A) "NO EDIT/WRITE GUARD EXISTS" — the
 * plugin's hooks.json registers matchers Read|Grep, Bash, Bash, Agent|Task
 * only; an orchestrator Write/Edit of source code is entirely unobserved.
 * Also root cause (D): agent_id-keyed exemption must be preserved for
 * subagents, and (B): the denial message must not be self-exemptable.
 *
 * INTENDED RED STATE: every denial test below fails on the discovery
 * assertion "a PreToolUse guard is registered for <tool>" because the
 * control does not exist. That is the missing-control failure, not a
 * harness error.
 *
 * ACs encoded here (unit slice of the decision table):
 *   AC-ORCH-01b, AC-ORCH-01d, AC-ORCH-01e, AC-ORCH-01f (unit slice),
 *   AC-ORCH-01h, AC-ORCH-10a.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const {
  guardsMatchingTool,
  runGuard,
  hookEvent,
  mkFixtureDir,
  rmFixtureDir,
  writeProbe,
  loadAuthorizationMatrix,
} = require('./helpers.cjs');

const SENTINEL = 'SENTINEL_ORIGINAL';
const EDIT_TOOLS = ['Edit', 'Write', 'MultiEdit', 'NotebookEdit'];
const CODE_EXTENSIONS = ['js', 'cjs', 'mjs', 'ts', 'sh', 'py', 'toml', 'yaml'];

/** Self-exemption clauses forbidden in any blocking message (AC-ORCH-01h). */
const SELF_EXEMPTION_SUBSTRINGS = [
  'If YES: proceed',
  'you can make the call',
  'proceed if',
  'EXCEPTION:',
];

/**
 * Discovery: the Edit/Write guard registered in the plugin's hooks.json for
 * the given tool. Fails the calling test with a missing-control message when
 * absent — the intended Red state under root cause (A).
 * @param {string} toolName
 * @returns {Array<{matcher: string, command: string, scriptPath: string|null}>}
 */
function requireEditGuards(toolName) {
  const guards = guardsMatchingTool(toolName);
  assert.ok(
    guards.length > 0,
    `MISSING CONTROL [root cause A, ssbd-ja5d]: no PreToolUse guard is registered ` +
      `for tool "${toolName}" in agent-teams-workforce/hooks/hooks.json. ` +
      `Registered matchers today are Read|Grep, Bash, Bash, Agent|Task — an ` +
      `orchestrator ${toolName} of source code is entirely unobserved (REQ-ORCH-01).`,
  );
  return guards;
}

/**
 * Runs every guard registered for the tool against the event; returns results.
 * @param {string} toolName
 * @param {object} evt
 */
function runAllGuards(toolName, evt) {
  return requireEditGuards(toolName).map((g) => ({ guard: g, result: runGuard(g.command, evt) }));
}

test('AC-ORCH-01b: orchestrator Edit/Write/MultiEdit/NotebookEdit of a .py probe are each blocked with exit 2 and the probe is unchanged', () => {
  const dir = mkFixtureDir('ac01b');
  try {
    const probe = writeProbe(dir, 'probe.py', SENTINEL);
    for (const tool of EDIT_TOOLS) {
      const toolInput =
        tool === 'NotebookEdit'
          ? { notebook_path: probe, new_source: 'tampered' }
          : tool === 'MultiEdit'
            ? { file_path: probe, edits: [{ old_string: SENTINEL, new_string: 'tampered' }] }
            : tool === 'Edit'
              ? { file_path: probe, old_string: SENTINEL, new_string: 'tampered' }
              : { file_path: probe, content: 'tampered' };
      const outcomes = runAllGuards(tool, hookEvent({ toolName: tool, toolInput }));
      assert.ok(
        outcomes.some((o) => o.result.status === 2),
        `AC-ORCH-01b: orchestrator ${tool} targeting ${probe} must be denied by a ` +
          `PreToolUse guard exiting 2; observed exit codes: ` +
          `[${outcomes.map((o) => o.result.status).join(', ')}]`,
      );
    }
    assert.equal(
      fs.readFileSync(probe, 'utf8'),
      SENTINEL,
      'AC-ORCH-01b: probe file content must remain exactly SENTINEL_ORIGINAL after all four blocked attempts',
    );
  } finally {
    rmFixtureDir(dir);
  }
});

test('AC-ORCH-01d: orchestrator Write is blocked with exit 2 for every code extension in the authorization matrix', () => {
  const matrix = loadAuthorizationMatrix();
  const dir = mkFixtureDir('ac01d');
  try {
    for (const ext of CODE_EXTENSIONS) {
      const cell = matrix.cells.find(
        (c) =>
          c.role === 'orchestrator' &&
          c.action === 'Write' &&
          c.resource === `code file (.${ext})`,
      );
      assert.ok(cell, `authorization matrix must define the orchestrator/Write/.${ext} cell`);
      assert.equal(cell.expected, 'deny', `matrix cell ${cell.id} must be an explicit deny`);

      const probe = writeProbe(dir, `probe.${ext}`, SENTINEL);
      const evt = hookEvent({ toolName: 'Write', toolInput: { file_path: probe, content: 'tampered' } });
      const outcomes = runAllGuards('Write', evt);
      assert.ok(
        outcomes.some((o) => o.result.status === 2),
        `AC-ORCH-01d [matrix ${cell.id}]: orchestrator Write of ${probe} must be denied ` +
          `with exit 2; observed: [${outcomes.map((o) => o.result.status).join(', ')}]`,
      );
      assert.equal(fs.readFileSync(probe, 'utf8'), SENTINEL, `probe .${ext} must be unchanged`);
    }
  } finally {
    rmFixtureDir(dir);
  }
});

test('AC-ORCH-01e: orchestrator Write of a .md report inside the artifact output directory is allowed (guard exit 0)', () => {
  // Binding constraint from the test strategy: the guard must key on target
  // path (extension + directory), not tool name — this allow cell and the
  // deny cells above are jointly satisfiable only by a path predicate.
  const dir = mkFixtureDir('ac01e-artifacts');
  try {
    const reportPath = path.join(dir, 'report.md');
    const evt = hookEvent({
      toolName: 'Write',
      toolInput: { file_path: reportPath, content: '# report' },
      extra: { artifact_output_dir: dir },
    });
    const outcomes = runAllGuards('Write', evt);
    for (const o of outcomes) {
      assert.equal(
        o.result.status,
        0,
        `AC-ORCH-01e [matrix M-13]: guard (matcher "${o.guard.matcher}") must exit 0 for a ` +
          `.md artifact write in the designated artifact directory; stderr: ${o.result.stderr}`,
      );
    }
  } finally {
    rmFixtureDir(dir);
  }
});

test('AC-ORCH-01f (unit slice): subagent Write of a .py file passes the guard with exit 0', () => {
  const dir = mkFixtureDir('ac01f');
  try {
    const probe = writeProbe(dir, 'probe.py', SENTINEL);
    const evt = hookEvent({
      toolName: 'Write',
      toolInput: { file_path: probe, content: 'SENTINEL_EDITED' },
      agentId: 'python-implementer-01',
    });
    const outcomes = runAllGuards('Write', evt);
    for (const o of outcomes) {
      assert.equal(
        o.result.status,
        0,
        `AC-ORCH-01f [matrix M-14, root cause D]: guard (matcher "${o.guard.matcher}") must ` +
          `preserve the subagent exemption (non-empty agent_id => exit 0); stderr: ${o.result.stderr}`,
      );
    }
  } finally {
    rmFixtureDir(dir);
  }
});

test('AC-ORCH-01h: the blocking message names the rejected path, names a delegate agent, and contains no self-granted exemption clause', () => {
  const dir = mkFixtureDir('ac01h');
  try {
    const probe = writeProbe(dir, 'probe.py', SENTINEL);
    const evt = hookEvent({ toolName: 'Write', toolInput: { file_path: probe, content: 'x' } });
    const outcomes = runAllGuards('Write', evt);
    const blocking = outcomes.filter((o) => o.result.status === 2);
    assert.ok(
      blocking.length > 0,
      'AC-ORCH-01h: at least one guard must block (exit 2) before its message can be inspected ' +
        '[missing control, root cause A]',
    );
    for (const o of blocking) {
      const msg = o.result.stderr;
      assert.ok(
        msg.includes(probe),
        `AC-ORCH-01h: blocking stderr must name the rejected absolute path ${probe}; got: ${msg}`,
      );
      assert.match(
        msg,
        /agent/i,
        'AC-ORCH-01h: blocking stderr must name at least one specific agent to delegate the edit to',
      );
      for (const clause of SELF_EXEMPTION_SUBSTRINGS) {
        assert.ok(
          !msg.includes(clause),
          `AC-ORCH-01h [root cause B]: blocking message must contain no self-exemption clause; ` +
            `found forbidden substring "${clause}"`,
        );
      }
    }
  } finally {
    rmFixtureDir(dir);
  }
});

test('AC-ORCH-10a: the Edit/Write guard fails closed — empty stdin and unparseable stdin both exit 2', () => {
  // Contrast with the current hooks, which exit 0 on parse failure
  // (pre-tool-orchestrator-read-warning.cjs:71-74, diagnostic gate :59-62).
  const guards = requireEditGuards('Write');
  for (const g of guards) {
    for (const [label, rawStdin] of [
      ['empty stdin', ''],
      ['unparseable stdin', '{not json%%%'],
    ]) {
      const result = runGuard(g.command, rawStdin);
      assert.equal(
        result.status,
        2,
        `AC-ORCH-10a: Edit/Write guard (matcher "${g.matcher}") must deny (exit 2) on ${label} ` +
          `instead of permitting the call; observed exit ${result.status}`,
      );
    }
  }
});
