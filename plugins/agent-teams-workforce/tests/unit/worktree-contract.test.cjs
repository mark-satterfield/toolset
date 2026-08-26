'use strict';

/**
 * Deploy requires a worktree, and the COMPOSITE is what creates it.
 *
 * deploy.js tells its agent to "Confirm the work is committed on a feature branch
 * IN A WORKTREE ... Never branch in a main working tree". That chain used to close
 * only at the entry command — shell in a markdown file, executed by a model — and
 * the two runs that stranded production work in a main working tree are the two
 * that skipped it. A step the pipeline depends on cannot be a step the pipeline
 * cannot see.
 *
 * It is now `workflows/workspace.js`, dispatched as the FIRST phase of every
 * code-writing composite, and its return value is the sole source of
 * contract.repoPath. These tests pin the mechanism, not the prose; the behavioural
 * assertions (dispatch order, refusal on an unverified tree) live in
 * tests/workflows/workspace-contract.test.mjs.
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

test('a workflow phase — not a command — creates the worktree', () => {
  const ws = read('workflows/workspace.js');
  assert.match(ws, /git -C "\$REPO" worktree add/, 'the workspace phase must actually cut the tree');
  assert.match(ws, /git -C "\$REPO" fetch origin/, 'branching without fetching can use a stale ref');
  assert.match(ws, /--git-common-dir/, 'it must VERIFY the result is a linked worktree, not assume it');
});

test('the worktree is verified by a SECOND agent, not by the one that created it', () => {
  // 6.0.6 tried to cross-examine the tree by shelling out to git from the script. The
  // runner refuses a module loader statically, so that script could not load AT ALL —
  // and it is the first phase of all three composites. A workflow script gets only
  // args, agent, workflow, phase, log, parallel and budget, so a script-side git check
  // is impossible by construction. Segregation of duties replaces it: a separate,
  // read-only agent reports the raw git facts and the SCRIPT rules on the two accounts.
  const ws = read('workflows/workspace.js');
  assert.match(ws, /workspace:independent-verify/, 'the second, independent dispatch must exist');
  assert.match(
    ws,
    /agentType: 'agent-teams-workforce:worktree-independent-verifier'/,
    'the verifier must be a DIFFERENT agent from the provisioner, or it grades its own homework',
  );
  assert.ok(
    fs.existsSync(path.join(ROOT, 'agents', 'worktree-independent-verifier.md')),
    'a workflow may not dispatch an agent this plugin does not ship',
  );
});

test('the workspace step refuses a tree belonging to a DIFFERENT repository', () => {
  // Residual: caller asks for repo A, provisioner returns a genuine linked worktree of
  // unrelated repo B on a feature branch. Both pure guards pass — it really is a linked
  // worktree on a non-default branch — and every writing phase then edits repo B.
  const ws = read('workflows/workspace.js');
  assert.match(ws, /DIFFERENT repository/, 'the returned tree must be checked against the repository the CALLER named');
  assert.match(ws, /callerCommonDir/, 'linked worktrees of one repo share its git-common-dir — that is the comparison');
});

test('the default branch is READ per repository, not hardcoded to main and master', () => {
  // A repo defaulting to `develop` or `trunk` was completely unprotected while the
  // hardcoded pair was the whole test. It stays as a FLOOR; the repo's real default is
  // read from origin/HEAD and refused as well.
  const ws = read('workflows/workspace.js');
  assert.match(ws, /refs\/remotes\/origin\/HEAD/, 'the real default branch must be obtained, not assumed');
  for (const f of ['workflows/bug-fix.js', 'workflows/task-to-deploy.js', 'workflows/infra-change.js']) {
    const src = read(f);
    assert.match(src, /settleDefaultBranch/, `${f}: settle must test against THIS repo's default, not a hardcoded pair`);
    assert.match(src, /SETTLE_DEFAULT_BRANCHES/, `${f}: and must keep main/master as a floor`);
  }
});

test('the composites require an AFFIRMATIVE verification before any writing phase', () => {
  // `ok === true && repoPath` also matches a 6.0.5-shaped result — version skew, a
  // bypassed or stale plugin cache — and the writing phases used to receive whatever
  // path it carried while only settle refused.
  for (const f of ['workflows/bug-fix.js', 'workflows/task-to-deploy.js', 'workflows/infra-change.js']) {
    const src = read(f);
    assert.match(src, /workspaceShapeFault/, `${f} must validate the shape the composite requires`);
    assert.match(src, /independentlyVerified !== true/, `${f} must refuse a result carrying no independent verification`);
  }
});

test('no workflow script reaches for a construct the runner refuses', async () => {
  // The P0 itself: an unloadable first phase in all three composites.
  const { findForbiddenConstructs } = await import('../../scripts/workflow-runner-constraints.mjs');
  const dir = path.join(ROOT, 'workflows');
  const offenders = [];
  for (const f of fs.readdirSync(dir).filter((n) => n.endsWith('.js'))) {
    for (const hit of findForbiddenConstructs(fs.readFileSync(path.join(dir, f), 'utf8'))) {
      offenders.push(`${f}:${hit.line} ${hit.name}`);
    }
  }
  assert.deepEqual(offenders, [], `these scripts CANNOT LOAD in production: ${offenders.join(', ')}`);
});

test('the workspace phase reuses an existing worktree for the same bead', () => {
  // A resumed or re-dispatched run must land in the same tree as the attempt
  // before it. In a fresh tree it cannot see the earlier run's tests, so Red's
  // survey finds nothing and re-authors everything it already paid for.
  const ws = read('workflows/workspace.js');
  assert.match(ws, /REUSE IT/i, 'a second attempt in a fresh tree cannot see the first attempt\'s work');
});

test('every code-writing composite dispatches the workspace phase', () => {
  for (const f of ['workflows/bug-fix.js', 'workflows/task-to-deploy.js', 'workflows/infra-change.js']) {
    const src = read(f);
    assert.match(src, /workflow\('agent-teams-workforce:workspace'/, `${f} must establish its own worktree`);
    assert.match(src, /no bead\.repoPath supplied/, `${f} must refuse to write code with no repository`);
  }
});

test('the entry commands no longer carry worktree shell of their own', () => {
  // Two sources for one convention is how `.worktrees/<bead>-<repo>`, `wt-<bead>`
  // and `wt-<name>` all ended up in the fleet at once.
  for (const f of ['commands/work-bead.md', 'commands/next-task.md']) {
    assert.doesNotMatch(read(f), /worktree add/, `${f} must not create a tree the composite also creates`);
  }
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

test('the main-tree guard is declared universal; the role guards are not', () => {
  // Replaces an earlier hack that excluded this guard from the spec by filename.
  // Scope is now a declared property each guard carries, so the spec checks the
  // right behaviour for each rather than one rule with an exception carved out.
  const { scopeOf } = require(path.join(ROOT, 'hooks', 'lib', 'guard-registry.cjs'));
  assert.equal(scopeOf('pre-tool-protect-main-worktree.cjs'), 'universal',
    'a rule about WHERE work lands binds everyone, including the subagent that caused the failure');
  assert.equal(scopeOf('pre-tool-orchestrator-edit-guard.cjs'), 'orchestrator-role',
    'a rule about WHO may act must still exempt subagents, or it blocks the work itself');
});


test('the workspace phase branches from the current tip, not a possibly-stale ref', () => {
  // Observed on ssbd-sa5j: the worktree was cut at 97f6e58 while main had already
  // moved to 048bd9c, which carried the committed unit suite. Red's survey looked
  // for those tests in a tree that genuinely did not have them, found nothing, and
  // re-authored the phase that had just been paid for. The survey was correct; it
  // was handed the wrong tree.
  const ws = read('workflows/workspace.js');
  assert.match(ws, /BRANCH FROM THE CURRENT TIP/i, 'branching from a stale ref silently omits landed work');
  assert.match(ws, /VERIFY, DO NOT ASSUME/i,
    'a worktree at the wrong commit is invisible until a phase behaves oddly — check it explicitly');
});
