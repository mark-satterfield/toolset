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
