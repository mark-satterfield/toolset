'use strict';

/**
 * Orchestrator mode: the guards constrain one role, and most sessions are not it.
 *
 * A repo where the guards are always armed is a repo where ordinary work —
 * troubleshooting, one-off scripts, anything unrelated to the pipelines — gets
 * blocked, and the operator learns to route around them. That is precisely the
 * behavior the guards exist to prevent, so leaving them permanently on is
 * self-defeating.
 *
 * Mode is OFF by default and switched on for a run. It is not a self-granted
 * exemption: it is set on disk before the work starts, is identical for every
 * call in the session, and every transition is logged.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const H = require('./support/hook-harness.cjs');

const MODE_SCRIPT = path.join(H.PLUGIN_ROOT, 'scripts', 'orchestrator-mode.cjs');

let projectDir;

test.beforeEach(() => {
  projectDir = H.makeTempDir('atw-mode-');
});
test.afterEach(() => {
  H.removeTempDir(projectDir);
});

function setMode(action, reason = 'test') {
  return spawnSync(process.execPath, [MODE_SCRIPT, action, reason], {
    encoding: 'utf8',
    env: { ...process.env, CLAUDE_PROJECT_DIR: projectDir },
  });
}

/** Runs a guard as an orchestrator session rooted at the temp project. */
function runGuard(script, toolName, toolInput) {
  return H.runScript(
    script,
    H.makeEvent({ toolName, toolInput, cwd: projectDir }),
    { cwd: projectDir },
  );
}

const EDIT_GUARD = path.join(H.PLUGIN_ROOT, 'hooks', 'pre-tool-orchestrator-edit-guard.cjs');
const BEADS_GUARD = path.join(H.PLUGIN_ROOT, 'hooks', 'pre-tool-beads-write-guard.cjs');

test('OFF is the default — a fresh project is unconstrained', () => {
  const probe = H.writeProbe(projectDir, 'thing.py', 'x\n');
  const r = runGuard(EDIT_GUARD, 'Write', { file_path: probe, content: 'y' });
  assert.equal(r.status, 0, 'a repo nobody has armed must not block ordinary work');
});

test('ON arms the guards', () => {
  setMode('on', 'starting a run');
  const probe = H.writeProbe(projectDir, 'thing.py', 'x\n');
  const r = runGuard(EDIT_GUARD, 'Write', { file_path: probe, content: 'y' });
  assert.equal(r.status, 2, 'with mode on, the orchestrator may not write code');
});

test('OFF disarms them again', () => {
  setMode('on');
  setMode('off', 'run finished');
  const probe = H.writeProbe(projectDir, 'thing.py', 'x\n');
  assert.equal(runGuard(EDIT_GUARD, 'Write', { file_path: probe, content: 'y' }).status, 0);
});

test('a shell script is writable when mode is off, blocked when on', () => {
  const probe = H.writeProbe(projectDir, 'file-bead.sh', '#!/bin/sh\n');
  assert.equal(
    runGuard(EDIT_GUARD, 'Write', { file_path: probe, content: 'x' }).status,
    0,
    'writing a helper script outside a run is ordinary work',
  );
  setMode('on');
  assert.equal(
    runGuard(EDIT_GUARD, 'Write', { file_path: probe, content: 'x' }).status,
    2,
    'inside a run, a .sh is implementation and belongs to an implementer',
  );
});

test('every transition is recorded with a reason', () => {
  setMode('on', 'starting the MVP-1 run');
  setMode('off', 'run complete');
  const log = fs.readFileSync(path.join(projectDir, '.claude', 'agent-teams-workforce.mode-log'), 'utf8');
  assert.match(log, /off -> on\tstarting the MVP-1 run/);
  assert.match(log, /on -> off\trun complete/);
});

test('status reports without changing anything', () => {
  setMode('on');
  const before = fs.readFileSync(path.join(projectDir, '.claude', 'agent-teams-workforce.local.md'), 'utf8');
  const r = setMode('status');
  assert.match(r.stdout, /orchestrator mode: on/);
  const after = fs.readFileSync(path.join(projectDir, '.claude', 'agent-teams-workforce.local.md'), 'utf8');
  assert.equal(after, before, 'status must not rewrite the mode file');
});

test('a run cannot silently disarm itself by editing the mode file', () => {
  setMode('on');
  const modeFile = path.join(projectDir, '.claude', 'agent-teams-workforce.local.md');
  const r = runGuard(EDIT_GUARD, 'Write', { file_path: modeFile, content: 'orchestrator_mode: off\n' });
  assert.equal(r.status, 2, 'disarming must go through the command, which logs it');
  assert.match(r.stderr, /orchestrator-mode/);
});

// ── The guard must judge what a command does, not what it is called ───────────

test('`bd create --help` is a read and is permitted even with mode on', () => {
  setMode('on');
  const r = runGuard(BEADS_GUARD, 'Bash', { command: 'bd create --help' });
  assert.equal(r.status, 0, 'printing usage writes nothing — matching the subcommand name is not judging the effect');
});

test('`bd create` still blocks with mode on', () => {
  setMode('on');
  assert.equal(runGuard(BEADS_GUARD, 'Bash', { command: 'bd create "a bead"' }).status, 2);
});

test('`bd create` is permitted with mode off', () => {
  assert.equal(runGuard(BEADS_GUARD, 'Bash', { command: 'bd create "a bead"' }).status, 0);
});
