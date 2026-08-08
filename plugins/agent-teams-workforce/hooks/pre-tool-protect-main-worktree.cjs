#!/usr/bin/env node
'use strict';

/**
 * PreToolUse hook — nobody writes to the default branch in the main working tree.
 *
 * "All branch work in worktrees; never branch in the main working tree" was a
 * non-negotiable that existed only as prose. Nothing created a worktree, nothing
 * created a branch, no gate checked which branch a phase was on, and no guard
 * blocked the write — so a Red phase handed a repoPath pointing at the main tree
 * wrote its test files straight onto `main`. It did exactly what it was told.
 *
 * Meanwhile deploy.js requires "the work is committed on a feature branch IN A
 * WORKTREE", a state nothing upstream produced. The chain only closes if the
 * constraint is checked where the write happens.
 *
 * THIS GUARD DOES NOT EXEMPT SUBAGENTS, and that is deliberate — it is the one
 * guard here that does not. The others govern the orchestrator's ROLE: subagents
 * are exempt because implementing is their job. This one governs WHERE anyone may
 * write, and an implementer writing to main is the exact failure observed. A rule
 * that binds only the orchestrator would have stopped nothing.
 *
 * Decision order:
 *   1. unparseable input                    -> exit 2  (FAIL CLOSED, REQ-ORCH-10a)
 *   2. out of scope (source repo / mode off)-> exit 0
 *   3. non-edit tool                        -> exit 0
 *   4. path not in a git repo               -> exit 0
 *   5. linked worktree, or feature branch   -> exit 0
 *   6. default branch in the MAIN worktree  -> exit 2
 */

const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { guardsApplyHere } = require('./lib/plugin-scope.cjs');

const EDIT_TOOLS = new Set(['Edit', 'Write', 'MultiEdit', 'NotebookEdit']);
const DEFAULT_BRANCHES = new Set(['main', 'master', 'trunk', 'develop']);

/** Reads all of stdin synchronously; returns '' when unreadable. */
function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

/** Runs git in a directory, returning trimmed stdout or null. */
function git(cwd, args) {
  try {
    return execFileSync('git', args, {
      cwd,
      encoding: 'utf8',
      // stderr is INHERITED, not discarded. Suppressing it hides why a repo
      // lookup failed, and this fleet's rules prohibit hiding errors — a guard
      // that fails silently is indistinguishable from one that passed.
      stdio: ['ignore', 'pipe', 'inherit'],
      timeout: 5000,
    }).trim();
  } catch {
    return null;
  }
}

/** The directory to ask git about — the file's own, since it may not exist yet. */
function containingDir(filePath) {
  let dir = path.dirname(path.resolve(filePath));
  for (let i = 0; i < 40; i += 1) {
    if (fs.existsSync(dir)) return dir;
    const up = path.dirname(dir);
    if (up === dir) return null;
    dir = up;
  }
  return null;
}

/** Denies with a reason and exits 2. */
function denyUnreadable(why) {
  process.stderr.write(
    `${[
      '--- Write to Main Working Tree Blocked ---',
      '',
      why,
      '',
      'This guard sits on the edit path, so it cannot fail open: a guard that cannot',
      'establish WHERE a write is going has no basis for permitting it (REQ-ORCH-10a).',
      '--- End ---',
    ].join('\n')}\n`,
  );
  process.exit(2);
}

function main() {
  const raw = readStdin();
  if (!raw.trim()) {
    denyUnreadable('The guard received no hook input and cannot establish the write target.');
  }

  let event;
  try {
    event = JSON.parse(raw);
  } catch {
    denyUnreadable('The guard could not parse its hook input as JSON.');
  }

  // NOTE: no agent_id check. See the header — this guard binds subagents too.
  if (!guardsApplyHere(event)) process.exit(0);

  if (!EDIT_TOOLS.has(String(event.tool_name ?? ''))) process.exit(0);

  const toolInput = event.tool_input ?? {};
  const target = toolInput.file_path ?? toolInput.notebook_path ?? '';
  if (!target) process.exit(0);

  const dir = containingDir(target);
  if (!dir) process.exit(0);

  // Not a git repo at all — nothing to protect.
  const inRepo = git(dir, ['rev-parse', '--is-inside-work-tree']);
  if (inRepo !== 'true') process.exit(0);

  // A LINKED worktree is exactly where work belongs. git reports the common dir
  // differently there, which is the cheapest reliable way to tell them apart.
  const gitDir = git(dir, ['rev-parse', '--git-dir']);
  const commonDir = git(dir, ['rev-parse', '--git-common-dir']);
  const isLinkedWorktree =
    gitDir && commonDir && path.resolve(dir, gitDir) !== path.resolve(dir, commonDir);
  if (isLinkedWorktree) process.exit(0);

  const branch = git(dir, ['rev-parse', '--abbrev-ref', 'HEAD']);
  if (!branch || branch === 'HEAD') process.exit(0); // detached: not a branch to protect
  if (!DEFAULT_BRANCHES.has(branch)) process.exit(0); // feature branch in the main tree

  const repoRoot = git(dir, ['rev-parse', '--show-toplevel']) || dir;
  const repoName = path.basename(repoRoot);
  const worktreeDir = path.join(path.dirname(repoRoot), '.worktrees');

  process.stderr.write(
    `${[
      '--- Write to Main Working Tree Blocked ---',
      '',
      `File:   ${target}`,
      `Repo:   ${repoRoot}`,
      `Branch: ${branch} (the MAIN working tree, not a linked worktree)`,
      '',
      'Branch work belongs in a worktree. Writing here puts uncommitted work on the',
      'default branch, where a second run would collide with it and where deploy —',
      'which requires the work on a feature branch in a worktree — cannot find it.',
      '',
      'Create one and work there instead:',
      '',
      `  git -C ${repoRoot} worktree list        # reuse one for this bead if it exists`,
      `  git -C ${repoRoot} worktree add -b <type>/<bead-id> \\`,
      `      ${worktreeDir}/<bead-id>-${repoName}`,
      '',
      'Then re-dispatch with repoPath pointing at the worktree. Everything downstream',
      'inherits it.',
      '',
      'This guard binds subagents as well as the orchestrator: an implementer writing',
      'to main is the failure it exists to stop.',
      '',
      'Rule source: agent-teams-workforce — never branch in a main working tree',
      '--- End ---',
    ].join('\n')}\n`,
  );
  process.exit(2);
}

main();
