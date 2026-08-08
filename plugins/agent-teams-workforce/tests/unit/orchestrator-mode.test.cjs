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

/**
 * The session the harness reports for guard events by default. Arming under the
 * same id keeps these suites testing the ARMED orchestrator: the arm binds one
 * session, so a test that armed under a different id would be exercising an
 * unbound bystander without saying so.
 */
const ARMING_SESSION = 'ssbd-ja5d-unit-session';

function setMode(action, reason = 'test', { session = ARMING_SESSION } = {}) {
  const env = { ...process.env, CLAUDE_PROJECT_DIR: projectDir };
  if (session) env.CLAUDE_CODE_SESSION_ID = session;
  else delete env.CLAUDE_CODE_SESSION_ID;
  return spawnSync(process.execPath, [MODE_SCRIPT, action, reason], { encoding: 'utf8', env });
}

/** Runs a guard as an orchestrator session rooted at the temp project. */
function runGuard(script, toolName, toolInput, { sessionId } = {}) {
  return H.runScript(
    script,
    H.makeEvent({ toolName, toolInput, cwd: projectDir, sessionId }),
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
  assert.match(log, /off -> on\t.*\tstarting the MVP-1 run/);
  assert.match(log, /on -> off\t.*\trun complete/);
  assert.match(log, new RegExp(`off -> on\t${ARMING_SESSION}\t`), 'the log records who took the arm');
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

// ── The arm binds one session ─────────────────────────────────────────────────
//
// Mode read only from the project directory approximated the orchestrator ROLE by
// LOCATION: arming a run bound every session opened in the repo, so the operator
// could not do unrelated work alongside it without disarming the run. Same failure
// as leaving the guards permanently armed, and the same lesson learned — route
// around them.

const MODE_FILE = path.join('.claude', 'agent-teams-workforce.local.md');

test('the arming session stays guarded', () => {
  setMode('on', 'starting a run');
  const probe = H.writeProbe(projectDir, 'thing.py', 'x\n');
  const r = runGuard(EDIT_GUARD, 'Write', { file_path: probe, content: 'y' }, { sessionId: ARMING_SESSION });
  assert.equal(r.status, 2, 'the session that armed the run is the one under the contract');
});

test('another session in the same repo is unconstrained while a run is armed', () => {
  setMode('on', 'starting a run');
  const probe = H.writeProbe(projectDir, 'thing.py', 'x\n');
  const r = runGuard(EDIT_GUARD, 'Write', { file_path: probe, content: 'y' }, { sessionId: 'some-other-session' });
  assert.equal(r.status, 0, 'unrelated work must not have to wait for the run to finish');
});

test('an arm that names a session records it in the mode file', () => {
  setMode('on');
  const raw = fs.readFileSync(path.join(projectDir, MODE_FILE), 'utf8');
  assert.match(raw, new RegExp(`^armed_by_session: ${ARMING_SESSION}$`, 'm'));
});

test('an event carrying no session id is guarded, not waived', () => {
  setMode('on');
  const probe = H.writeProbe(projectDir, 'thing.py', 'x\n');
  const r = runGuard(EDIT_GUARD, 'Write', { file_path: probe, content: 'y' }, { sessionId: '' });
  assert.equal(r.status, 2, 'an event the guard cannot attribute is not thereby exempt');
});

test('an arm made with no session id available binds the whole project', () => {
  const r = setMode('on', 'no harness id', { session: null });
  assert.match(r.stdout, /binds EVERY session/);
  const probe = H.writeProbe(projectDir, 'thing.py', 'x\n');
  assert.equal(
    runGuard(EDIT_GUARD, 'Write', { file_path: probe, content: 'y' }, { sessionId: 'any-session' }).status,
    2,
    'without an id to bind, the arm can only fall back to the old project-wide scope',
  );
});

test('a mode file predating session binding still binds the whole project', () => {
  fs.mkdirSync(path.join(projectDir, '.claude'), { recursive: true });
  fs.writeFileSync(path.join(projectDir, MODE_FILE), '---\norchestrator_mode: on\n---\n', 'utf8');
  const probe = H.writeProbe(projectDir, 'thing.py', 'x\n');
  assert.equal(
    runGuard(EDIT_GUARD, 'Write', { file_path: probe, content: 'y' }, { sessionId: 'any-session' }).status,
    2,
    'an already-armed repo must keep behaving exactly as it did',
  );
});

test('a second session cannot take the arm from the first', () => {
  setMode('on', 'the real run');
  const r = setMode('on', 'me too', { session: 'some-other-session' });
  assert.match(r.stdout, /already on/);
  assert.match(r.stdout, new RegExp(`armed by session ${ARMING_SESSION}`));

  const raw = fs.readFileSync(path.join(projectDir, MODE_FILE), 'utf8');
  assert.match(
    raw,
    new RegExp(`^armed_by_session: ${ARMING_SESSION}$`, 'm'),
    'taking the arm would move the guards off the run they were protecting',
  );
});

test('status names the holder and whether this session is bound by it', () => {
  setMode('on');
  const mine = setMode('status');
  assert.match(mine.stdout, new RegExp(`armed by session: ${ARMING_SESSION}`));
  assert.match(mine.stdout, /guards here: ARMED/);

  const theirs = setMode('status', '', { session: 'some-other-session' });
  assert.match(theirs.stdout, /guards here: off — the arm belongs to another session/);
});

test('disarming from an unbound session says whose run just lost its guards', () => {
  setMode('on', 'the real run');
  const r = setMode('off', 'oops', { session: 'some-other-session' });
  assert.match(r.stdout, new RegExp(`belonged to session ${ARMING_SESSION}`));
  assert.match(r.stdout, /now unguarded/);
});

test('disarming clears the binding', () => {
  setMode('on');
  setMode('off', 'run complete');
  const raw = fs.readFileSync(path.join(projectDir, MODE_FILE), 'utf8');
  assert.doesNotMatch(raw, /armed_by_session/, 'mode off constrains nobody, so it holds no binding');
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

// ── Tracker admin is not prose ────────────────────────────────────────────────
//
// The hazard is text reaching a downstream agent's prompt. Closing a resolved
// bead injects no instruction into anyone's prompt, and blocking it only forces
// the operator to disarm the guards for routine bookkeeping — which is how a
// guard teaches people to work around it.

for (const command of [
  'bd close ssbd-ja5d',
  'bd reopen ssbd-1',
  'bd update ssbd-1 --status closed',
  'bd assign ssbd-1 alice',
  'bd defer ssbd-1',
]) {
  test(`\`${command}\` is permitted with mode on — administration carries no prose`, () => {
    setMode('on');
    assert.equal(runGuard(BEADS_GUARD, 'Bash', { command }).status, 0);
  });
}

for (const command of [
  'bd note ssbd-1 "decision already made"',
  'bd create "a bead"',
  'bd update ssbd-1 --notes "architecture settled, skip analysis"',
  'bd comment ssbd-1 "no need to re-derive"',
]) {
  test(`\`${command.slice(0, 40)}\` is still blocked — it writes into an agent's prompt`, () => {
    setMode('on');
    assert.equal(
      runGuard(BEADS_GUARD, 'Bash', { command }).status,
      2,
      'text written into a bead reaches downstream agents as authoritative input',
    );
  });
}

test('the MCP route blocks prose and permits reads', () => {
  setMode('on');
  assert.equal(runGuard(BEADS_GUARD, 'mcp__beads__update', { id: 'ssbd-1', notes: 'x' }).status, 2);
  assert.equal(runGuard(BEADS_GUARD, 'mcp__beads__create', { title: 'x' }).status, 2);
  assert.equal(runGuard(BEADS_GUARD, 'mcp__beads__show', { id: 'ssbd-1' }).status, 0);
  assert.equal(runGuard(BEADS_GUARD, 'mcp__beads__ready', {}).status, 0);
});
