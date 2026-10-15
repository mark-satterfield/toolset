#!/usr/bin/env node
'use strict';

/**
 * PreToolUse hook: no edit lands in the primary working tree of a product repository.
 *
 * Tier 1 repositories (the SkillSpoke product: services, libraries, infrastructure, web)
 * take all work in worktrees. Tier 2 repositories (the control repository, the toolset
 * repository, the documentation vault) commit in their primary working tree, so this
 * guard must never block them.
 *
 * Which repository is which comes from the tier record the polyrepo-steward exports:
 * $SKILLSPOKE_CC/.polyrepo/repository-tiers.json, a JSON object mapping each
 * repository's absolute path to "product" or "tooling". The guard blocks only a write
 * inside a repository the record lists as "product". When the record is absent or
 * unreadable, the guard allows the write and prints one warning line, so a missing
 * record never blocks tier 2 work.
 *
 * The guard binds subagents as well as the session the owner talks to: an implementer
 * writing to a product repository's primary tree is the failure it exists to stop.
 *
 * Decision order:
 *   1. unparseable hook input                           -> exit 2 (fail closed)
 *   2. non-edit tool, or no target path                 -> exit 0
 *   3. tier record absent or unreadable                 -> exit 0, one warning line
 *   4. target outside every "product" repository        -> exit 0
 *   5. target under the repository's .worktrees/        -> exit 0
 *   6. target in a linked worktree                      -> exit 0
 *   7. otherwise (primary tree of a product repository) -> exit 2
 */

const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const EDIT_TOOLS = new Set(['Edit', 'Write', 'MultiEdit', 'NotebookEdit']);
const CONTROL_REPO_ENV = 'SKILLSPOKE_CC';
const TIER_RECORD = path.join('.polyrepo', 'repository-tiers.json');
const PRODUCT_TIER = 'product';
const KNOWN_TIERS = new Set([PRODUCT_TIER, 'tooling']);
const WORKTREE_DIR = '.worktrees';
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

/**
 * The real paths of the repositories the tier record lists as "product".
 * Exits 0 with a warning when the record is absent, unreadable or malformed.
 */
function productRepositories() {
  const controlRepo = process.env[CONTROL_REPO_ENV];
  if (!controlRepo) allowWithWarning(`$${CONTROL_REPO_ENV} is not set, so the tier record cannot be found`);
  const recordPath = path.join(controlRepo, TIER_RECORD);
  let record;
  try {
    record = JSON.parse(fs.readFileSync(recordPath, 'utf8'));
  } catch (error) {
    allowWithWarning(`the tier record ${recordPath} is absent or unreadable (${error.message})`);
  }
  if (record === null || typeof record !== 'object' || Array.isArray(record)) {
    allowWithWarning(`the tier record ${recordPath} is not a JSON object`);
  }
  const bad = Object.entries(record).filter(([repo, tier]) => !path.isAbsolute(repo) || !KNOWN_TIERS.has(tier));
  if (bad.length > 0) {
    allowWithWarning(`the tier record ${recordPath} has ${bad.length} entr(ies) that are not an absolute path mapped to product or tooling`);
  }
  return Object.entries(record)
    .filter(([, tier]) => tier === PRODUCT_TIER)
    .map(([repo]) => realOrResolved(repo));
}

/** True when the directory is inside a linked worktree, not a primary working tree. */
function inLinkedWorktree(dir) {
  const gitDir = git(dir, ['rev-parse', '--git-dir']);
  const commonDir = git(dir, ['rev-parse', '--git-common-dir']);
  return Boolean(gitDir && commonDir && path.resolve(dir, gitDir) !== path.resolve(dir, commonDir));
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

  const products = productRepositories();
  const dir = containingDir(target);
  if (!dir) process.exit(0);
  const realDir = realOrResolved(dir);
  const repoRoot = products.find((repo) => isWithin(repo, realDir));
  if (!repoRoot) process.exit(0);
  if (isWithin(path.join(repoRoot, WORKTREE_DIR), realDir)) process.exit(0);
  if (inLinkedWorktree(realDir)) process.exit(0);

  const repoName = path.basename(repoRoot);
  deny([
    `File: ${target}`,
    `Repo: ${repoRoot} (a product repository, primary working tree)`,
    '',
    'Product repositories take all work in worktrees. Create or reuse one and work there:',
    '',
    `  git -C ${repoRoot} worktree list`,
    `  git -C ${repoRoot} worktree add -b <type>/<bead-id> ${path.join(repoRoot, WORKTREE_DIR)}/<bead-id>-${repoName}`,
    '',
    `Tier record: $${CONTROL_REPO_ENV}/${TIER_RECORD}`,
  ]);
}

main();
