#!/usr/bin/env node
'use strict';

/**
 * PreToolUse hook: no product file is edited in the primary working tree of a product repository.
 *
 * The folder layout decides which repositories are product repositories. Every git repository
 * under $SKILLSPOKE_APPS is product work: it takes a worktree and a pull request. The one
 * exception is the command-and-control repository at $SKILLSPOKE_CC, which sits under
 * $SKILLSPOKE_APPS but holds the tooling that builds the product, committed on main. AGENTS.md,
 * CLAUDE.md and .claude/ are tooling wherever they sit, so they are never blocked.
 *
 * When $SKILLSPOKE_APPS or $SKILLSPOKE_CC is unset, the guard allows the write and prints one
 * warning line, so a missing variable never blocks tooling work.
 *
 * The guard binds subagents as well as the session the owner talks to: an implementer
 * writing to a product repository's primary tree is the failure it exists to stop.
 *
 * Decision order:
 *   1. unparseable hook input                                  -> exit 2 (fail closed)
 *   2. non-edit tool, or no target path                        -> exit 0
 *   3. $SKILLSPOKE_APPS or $SKILLSPOKE_CC unset                -> exit 0, one warning line
 *   4. target in no git repository below $SKILLSPOKE_APPS       -> exit 0
 *   5. target in the command-and-control repository           -> exit 0
 *   6. target under the repository's .worktrees/               -> exit 0
 *   7. target in a linked worktree                             -> exit 0
 *   8. target is AGENTS.md, CLAUDE.md or under .claude/        -> exit 0
 *   9. otherwise (a product file in the primary tree)          -> exit 2
 */

const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const EDIT_TOOLS = new Set(['Edit', 'Write', 'MultiEdit', 'NotebookEdit']);
const APPS_ENV = 'SKILLSPOKE_APPS';
const CONTROL_REPO_ENV = 'SKILLSPOKE_CC';
const WORKTREE_DIR = '.worktrees';
const TIER2_FILES = new Set(['AGENTS.md', 'CLAUDE.md']);
const TIER2_DIR = '.claude';
const MAX_ASCENT = 40;

/** Reads all of stdin synchronously; returns '' when unreadable. */
function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

/** Runs git in a directory, returning trimmed stdout or null. stderr is inherited, not hidden. */
function git(cwd, args) {
  try {
    return execFileSync('git', args, {
      cwd,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'inherit'],
      timeout: 5000,
    }).trim();
  } catch {
    return null;
  }
}

/** Resolves symlinks when the path exists; returns the resolved path otherwise. */
function realOrResolved(p) {
  try {
    return fs.realpathSync(p);
  } catch {
    return path.resolve(p);
  }
}

/** The nearest existing directory holding the target, since the file may not exist yet. */
function containingDir(filePath) {
  let dir = path.dirname(path.resolve(filePath));
  for (let i = 0; i < MAX_ASCENT; i += 1) {
    if (fs.existsSync(dir)) return dir;
    const up = path.dirname(dir);
    if (up === dir) return null;
    dir = up;
  }
  return null;
}

/** True when child is root itself or lies below it. */
function isWithin(root, child) {
  const rel = path.relative(root, child);
  return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel));
}

/** Writes one warning line and allows the write. */
function allowWithWarning(why) {
  process.stderr.write(`main-worktree guard: ${why}; the write is allowed.\n`);
  process.exit(0);
}

/** Denies with a reason and exits 2. */
function deny(lines) {
  process.stderr.write(`${['--- Write to Main Working Tree Blocked ---', '', ...lines, '--- End ---'].join('\n')}\n`);
  process.exit(2);
}

/** The real path a layout variable names; exits 0 with a warning when it is unset. */
function layoutRoot(name) {
  const value = process.env[name];
  if (!value) allowWithWarning(`$${name} is not set, so the repository layout cannot be read`);
  return realOrResolved(value);
}

/** True when the directory is inside a linked worktree, not a primary working tree. */
function inLinkedWorktree(dir) {
  const gitDir = git(dir, ['rev-parse', '--git-dir']);
  const commonDir = git(dir, ['rev-parse', '--git-common-dir']);
  return Boolean(gitDir && commonDir && path.resolve(dir, gitDir) !== path.resolve(dir, commonDir));
}

/** True when the target is tooling wherever it sits: AGENTS.md or CLAUDE.md at any depth, or under .claude/. */
function isTier2File(repoRoot, realDir, target) {
  const relative = path.relative(repoRoot, path.join(realDir, path.basename(target)));
  if (TIER2_FILES.has(path.basename(relative))) return true;
  return relative.split(path.sep)[0] === TIER2_DIR;
}

function main() {
  const raw = readStdin();
  if (!raw.trim()) deny(['The guard received no hook input and cannot establish the write target.']);
  let event;
  try {
    event = JSON.parse(raw);
  } catch {
    deny(['The guard could not parse its hook input as JSON.']);
  }

  if (!EDIT_TOOLS.has(String(event.tool_name ?? ''))) process.exit(0);
  const toolInput = event.tool_input ?? {};
  const target = toolInput.file_path ?? toolInput.notebook_path ?? '';
  if (!target) process.exit(0);

  const apps = layoutRoot(APPS_ENV);
  const controlRepo = layoutRoot(CONTROL_REPO_ENV);
  const dir = containingDir(target);
  if (!dir) process.exit(0);
  const realDir = realOrResolved(dir);
  if (!isWithin(apps, realDir)) process.exit(0);
  const top = git(realDir, ['rev-parse', '--show-toplevel']);
  if (!top) process.exit(0);
  const repoRoot = realOrResolved(top);
  if (repoRoot === apps || !isWithin(apps, repoRoot)) process.exit(0);
  if (isWithin(controlRepo, realDir)) process.exit(0);
  if (isWithin(path.join(repoRoot, WORKTREE_DIR), realDir)) process.exit(0);
  if (inLinkedWorktree(realDir)) process.exit(0);
  if (isTier2File(repoRoot, realDir, target)) process.exit(0);

  const repoName = path.basename(repoRoot);
  deny([
    `File: ${target}`,
    `Repo: ${repoRoot} (under $${APPS_ENV}, primary working tree)`,
    '',
    `Every repository under $${APPS_ENV} except the command-and-control repository ($${CONTROL_REPO_ENV}) takes its product work in a worktree and a pull request opened with skillspoke-pr (AGENTS.md, CLAUDE.md and .claude/ are tooling and are not blocked). Create or reuse a worktree and work there:`,
    '',
    `  python3 ${path.join(__dirname, '..', 'scripts', 'portfolio', 'gitutils.py')} provision --repo ${repoRoot} --branch <type>/<bead-id> --name <bead-id>-${repoName}`,
    '',
    `It reuses the worktree registered for the branch, or creates one at ${path.join(repoRoot, WORKTREE_DIR)}/<bead-id>-${repoName}; never run git worktree add with a path of your own.`,
  ]);
}

main();
