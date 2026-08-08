'use strict';

/**
 * Deploy requires a worktree that nothing creates.
 *
 * deploy.js tells its agent to "Confirm the work is committed on a feature branch
 * IN A WORKTREE ... Never branch in a main working tree". But no workflow phase
 * creates one, and no phase mentions branching at all — so every writing phase
 * edits whatever tree it was handed. Observed live on ssbd-sa5j: the Red phase
 * wrote its test files onto `main` in the main working tree, the one place the
 * rules forbid, and the one place two parallel runs would collide.
 *
 * The chain closes at the entry command, which is deterministic shell rather than
 * an agent's judgement: /work-bead establishes the worktree and passes it as
 * repoPath, and everything downstream inherits it.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..', '..');
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');

test('deploy still requires a feature branch in a worktree', () => {
  const src = read('workflows/deploy.js');
  assert.match(src, /IN A WORKTREE/i, 'if this requirement is dropped, the entry command should stop creating one');
});

test('/work-bead establishes the worktree before dispatching', () => {
  const cmd = read('commands/work-bead.md');
  assert.match(cmd, /git .*worktree add/, 'the entry point must create the worktree — no workflow phase does');
  assert.match(cmd, /repoPath: "\$WT"/, 'the composite must be pointed at the worktree, not the main tree');
});

test('/work-bead reuses an existing worktree for the same bead', () => {
  // A resumed or re-dispatched run must land in the same tree as the attempt
  // before it. In a fresh tree it cannot see the earlier run's tests, so Red's
  // survey finds nothing and re-authors everything it already paid for.
  const cmd = read('commands/work-bead.md');
  assert.match(cmd, /REUSE it/i, 'a second attempt in a fresh tree cannot see the first attempt\'s work');
});

test('/resume-run enumerates worktrees rather than trusting the main tree', () => {
  // `git status` in the main tree reports nothing from a linked worktree, so a
  // status check there can show a clean tree while the work sits elsewhere — or
  // show half the picture and lead someone to delete the wrong half.
  const cmd = read('commands/resume-run.md');
  assert.match(cmd, /git worktree list/, 'resume must look in every tree, not just the one it is standing in');
  assert.match(cmd, /does NOT see linked worktrees/i, 'and must say why, or the step reads as redundant');
});

// ── The guard that makes it structural ────────────────────────────────────────

const { execFileSync } = require('node:child_process');
const os = require('node:os');

const GUARD = path.join(ROOT, 'hooks', 'pre-tool-protect-main-worktree.cjs');

/** A real git repo on `main`, plus a linked worktree on a feature branch. */
function makeRepos() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'atw-wt-'));
  const repo = path.join(base, 'repo');
  fs.mkdirSync(repo);
  const g = (args, cwd = repo) => execFileSync('git', args, { cwd, stdio: 'ignore' });
  g(['init', '-b', 'main']);
  g(['config', 'user.email', 't@t']);
  g(['config', 'user.name', 't']);
  fs.writeFileSync(path.join(repo, 'seed.txt'), 'x');
  g(['add', '.']);
  g(['commit', '-m', 'seed']);
  const wt = path.join(base, '.worktrees', 'ssbd-1-repo');
  g(['worktree', 'add', '-b', 'fix/ssbd-1', wt]);

  const project = path.join(base, 'project');
  fs.mkdirSync(path.join(project, '.claude'), { recursive: true });
  fs.writeFileSync(
    path.join(project, '.claude', 'agent-teams-workforce.local.md'),
    '---\norchestrator_mode: on\n---\n',
  );
  return { base, repo, wt, project };
}

function runGuard(filePath, project, extra = {}) {
  const event = JSON.stringify({
    session_id: 's',
    cwd: project,
    hook_event_name: 'PreToolUse',
    tool_name: 'Write',
    tool_input: { file_path: filePath, content: 'x' },
    ...extra,
  });
  const r = require('node:child_process').spawnSync(process.execPath, [GUARD], {
    input: event,
    encoding: 'utf8',
    env: { ...process.env, CLAUDE_PROJECT_DIR: project },
  });
  return r.status;
}

test('writing to the default branch in the MAIN tree is blocked', () => {
  const { base, repo, project } = makeRepos();
  try {
    assert.equal(runGuard(path.join(repo, 'src', 'new.py'), project), 2);
  } finally {
    fs.rmSync(base, { recursive: true, force: true });
  }
});

test('writing in a LINKED worktree on a feature branch is allowed', () => {
  const { base, wt, project } = makeRepos();
  try {
    assert.equal(runGuard(path.join(wt, 'src', 'new.py'), project), 0, 'the worktree is where work belongs');
  } finally {
    fs.rmSync(base, { recursive: true, force: true });
  }
});

test('the guard binds SUBAGENTS too — an implementer writing to main is the failure', () => {
  // Every other guard here exempts subagents, because implementing is their job.
  // This one governs WHERE anyone may write, and the observed failure was a test
  // writer putting files on main. A rule binding only the orchestrator stops nothing.
  const { base, repo, project } = makeRepos();
  try {
    assert.equal(
      runGuard(path.join(repo, 'src', 'new.py'), project, { agent_id: 'sub-1', agent_type: 'worker' }),
      2,
      'exempting subagents here would exempt exactly the actor that caused the problem',
    );
  } finally {
    fs.rmSync(base, { recursive: true, force: true });
  }
});

test('a path outside any git repo is ignored', () => {
  const { base, project } = makeRepos();
  try {
    assert.equal(runGuard(path.join(os.tmpdir(), 'nowhere', 'x.txt'), project), 0);
  } finally {
    fs.rmSync(base, { recursive: true, force: true });
  }
});

test('nothing this plugin ships hides errors with 2>/dev/null', () => {
  // A fleet non-negotiable: errors stay visible in hooks, scripts, and commands.
  // A guard that fails silently is indistinguishable from one that passed, which
  // is the worst possible failure mode for a guard.
  const dirs = ['commands', 'hooks', 'scripts'];
  const offenders = [];
  for (const d of dirs) {
    const full = path.join(ROOT, d);
    if (!fs.existsSync(full)) continue;
    for (const f of fs.readdirSync(full)) {
      const p = path.join(full, f);
      if (!fs.statSync(p).isFile()) continue;
      const src = fs.readFileSync(p, 'utf8');
      // Allow the prohibition itself to name the pattern.
      const lines = src.split('\n').filter((l) => /2>\/dev\/null/.test(l) && !/prohibit|forbid|never/i.test(l));
      if (lines.length) offenders.push(`${d}/${f}: ${lines[0].trim().slice(0, 70)}`);
    }
  }
  assert.deepEqual(offenders, [], `these hide stderr:\n  ${offenders.join('\n  ')}`);
});

test('the main-tree guard is the ONLY guard that binds subagents', () => {
  // Scoping REQ-ORCH-04b's subagent exemption is a real weakening if it spreads.
  // Pin the exception to exactly one guard, so a second one cannot be added by
  // quietly widening the exclusion instead of arguing for it.
  const spec = read('tests/unit/forbidden-action-guards.test.cjs');
  const excluded = [...spec.matchAll(/ROLE_EXEMPT_ONLY = \/([^/]+)\//g)].map((m) => m[1]);
  assert.equal(excluded.length, 1, 'exactly one exclusion pattern should exist');
  assert.match(excluded[0], /protect-main-worktree/, 'and it must name the location guard specifically');
});
