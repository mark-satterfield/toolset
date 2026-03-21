#!/usr/bin/env python3
"""gitignore_audit.py -- Audit, optimize, and protect .gitignore files.

Companion tool for the gitignore-guardian skill. Provides CLI subcommands for
auditing repository hygiene, finding tracked-but-ignored files, detecting dead
rules, suggesting missing patterns, and managing @protect annotations.

Usage:
    python3 tools/gitignore_audit.py audit
    python3 tools/gitignore_audit.py tracked-ignored
    python3 tools/gitignore_audit.py dead-rules
    python3 tools/gitignore_audit.py missing-rules
    python3 tools/gitignore_audit.py optimize
    python3 tools/gitignore_audit.py untrack <file>
    python3 tools/gitignore_audit.py purge <file>
    python3 tools/gitignore_audit.py protect <pattern> <reason>
    python3 tools/gitignore_audit.py index <pattern> <reason>
    python3 tools/gitignore_audit.py hook-validate  (called by PreToolUse hook, reads stdin)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SENSITIVE_PATTERNS = frozenset({
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.keystore",
    "*secret*", "credentials.json", "service-account*.json",
    ".aws/credentials", "*.jks", "id_rsa", "id_ed25519",
})

# Patterns that are dangerously broad -- would ignore source files
OVERLY_BROAD_PATTERNS = frozenset({
    "*", "**", "*.py", "*.ts", "*.tsx", "*.js", "*.jsx", "*.java",
    "*.go", "*.rs", "*.rb", "*.swift", "*.kt", "*.c", "*.cpp", "*.h",
    "*.css", "*.scss", "*.json", "*.yaml", "*.yml", "*.toml", "*.md",
})

# Stack-detection files -> suggested gitignore patterns
STACK_PATTERNS: dict[str, list[str]] = {
    "package.json": [
        "node_modules/", ".next/", ".nuxt/", "dist/", ".parcel-cache/",
        "npm-debug.log*", "yarn-error.log*", "pnpm-debug.log*",
        ".pnpm-store/", ".turbo/", "coverage/",
    ],
    "pyproject.toml": [
        "__pycache__/", "*.py[cod]", ".venv/", "*.egg-info/",
        ".mypy_cache/", ".ruff_cache/", ".pytest_cache/", ".coverage",
        "htmlcov/", "dist/", "build/",
    ],
    "requirements.txt": [
        "__pycache__/", "*.py[cod]", ".venv/", ".pytest_cache/",
    ],
    "Cargo.toml": ["target/", "Cargo.lock"],
    "go.mod": ["vendor/"],
    "cdk.json": ["cdk.out/", "cdk.context.json", ".cdk/"],
    "Podfile": ["Pods/", "*.xcworkspace"],
    "pubspec.yaml": [".dart_tool/", ".flutter-plugins", "build/"],
    "Gemfile": ["vendor/bundle/", ".bundle/"],
    "expo-module.config.json": [".expo/", "web-build/"],
}

# OS/editor patterns that should always be present
UNIVERSAL_PATTERNS = [".DS_Store", "Thumbs.db", "*.swp", "*~"]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class GitignoreEntry:
    """Parsed line from a .gitignore file."""
    pattern: str
    line_number: int
    raw_line: str
    is_negation: bool = False
    is_comment: bool = False
    is_blank: bool = False
    is_protected: bool = False
    protect_reason: str = ""
    in_protect_block: bool = False
    is_indexed: bool = False
    index_reason: str = ""
    in_index_block: bool = False


@dataclass
class AuditResult:
    """Aggregated audit findings."""
    tracked_ignored: list[str] = field(default_factory=list)
    dead_rules: list[GitignoreEntry] = field(default_factory=list)
    missing_rules: list[str] = field(default_factory=list)
    optimizations: list[str] = field(default_factory=list)
    protected_entries: list[GitignoreEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git_root() -> Path:
    """Get the git repository root."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        print("ERROR: Not inside a git repository.", file=sys.stderr)
        sys.exit(1)
    return Path(result.stdout.strip())


def git_tracked_files() -> set[str]:
    """Get all files tracked by git."""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print("ERROR: git ls-files failed.", file=sys.stderr)
        sys.exit(1)
    return set(result.stdout.strip().splitlines()) if result.stdout.strip() else set()


def git_check_ignore(paths: list[str]) -> set[str]:
    """Check which paths would be ignored by .gitignore rules.

    Uses --no-index so it checks against .gitignore rules regardless of
    whether files are currently tracked.
    """
    if not paths:
        return set()

    ignored = set()
    # Process in batches to avoid argument list too long
    batch_size = 500
    for i in range(0, len(paths), batch_size):
        batch = paths[i:i + batch_size]
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--"] + batch,
            capture_output=True, text=True, timeout=30,
        )
        # exit 0 = some ignored, exit 1 = none ignored, exit 128 = error
        if result.stdout.strip():
            ignored.update(result.stdout.strip().splitlines())

    return ignored


def git_worktree_list() -> list[str]:
    """List all git worktrees."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        return []
    worktrees = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            worktrees.append(line[len("worktree "):])
    return worktrees


# ---------------------------------------------------------------------------
# Gitignore parser
# ---------------------------------------------------------------------------

def parse_gitignore(gitignore_path: Path) -> list[GitignoreEntry]:
    """Parse a .gitignore file, recognizing @protect and @index annotations."""
    if not gitignore_path.exists():
        return []

    entries: list[GitignoreEntry] = []
    lines = gitignore_path.read_text().splitlines()

    pending_protect: str | None = None
    in_protect_block = False
    pending_index: str | None = None
    in_index_block = False

    for i, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()

        # Check for @protect-start
        if stripped.startswith("# @protect-start:"):
            in_protect_block = True
            entries.append(GitignoreEntry(
                pattern="", line_number=i, raw_line=raw_line,
                is_comment=True, is_protected=True,
                protect_reason=stripped[len("# @protect-start:"):].strip(),
                in_protect_block=True,
            ))
            continue

        # Check for @protect-end
        if stripped == "# @protect-end":
            in_protect_block = False
            entries.append(GitignoreEntry(
                pattern="", line_number=i, raw_line=raw_line,
                is_comment=True, is_protected=True,
                in_protect_block=False,
            ))
            continue

        # Check for single-line @protect
        if stripped.startswith("# @protect:"):
            pending_protect = stripped[len("# @protect:"):].strip()
            entries.append(GitignoreEntry(
                pattern="", line_number=i, raw_line=raw_line,
                is_comment=True, is_protected=True,
                protect_reason=pending_protect,
            ))
            continue

        # Check for @index-start
        if stripped.startswith("# @index-start:"):
            in_index_block = True
            entries.append(GitignoreEntry(
                pattern="", line_number=i, raw_line=raw_line,
                is_comment=True, is_indexed=True,
                index_reason=stripped[len("# @index-start:"):].strip(),
                in_index_block=True,
            ))
            continue

        # Check for @index-end
        if stripped == "# @index-end":
            in_index_block = False
            entries.append(GitignoreEntry(
                pattern="", line_number=i, raw_line=raw_line,
                is_comment=True, is_indexed=True,
                in_index_block=False,
            ))
            continue

        # Check for single-line @index
        if stripped.startswith("# @index:"):
            pending_index = stripped[len("# @index:"):].strip()
            entries.append(GitignoreEntry(
                pattern="", line_number=i, raw_line=raw_line,
                is_comment=True, is_indexed=True,
                index_reason=pending_index,
            ))
            continue

        # Blank line
        if not stripped:
            pending_protect = None  # Blank line breaks associations
            pending_index = None
            entries.append(GitignoreEntry(
                pattern="", line_number=i, raw_line=raw_line,
                is_blank=True,
            ))
            continue

        # Regular comment
        if stripped.startswith("#"):
            entries.append(GitignoreEntry(
                pattern="", line_number=i, raw_line=raw_line,
                is_comment=True,
            ))
            continue

        # Pattern line
        is_negation = stripped.startswith("!")
        pattern = stripped[1:] if is_negation else stripped

        entry = GitignoreEntry(
            pattern=pattern,
            line_number=i,
            raw_line=raw_line,
            is_negation=is_negation,
            is_protected=pending_protect is not None or in_protect_block,
            protect_reason=pending_protect or "",
            in_protect_block=in_protect_block,
            is_indexed=pending_index is not None or in_index_block,
            index_reason=pending_index or "",
            in_index_block=in_index_block,
        )
        entries.append(entry)
        pending_protect = None  # Consumed
        pending_index = None  # Consumed

    return entries


# ---------------------------------------------------------------------------
# Audit functions
# ---------------------------------------------------------------------------

def find_tracked_ignored(repo_root: Path) -> list[tuple[str, bool]]:
    """Find tracked files that match .gitignore patterns.

    Returns list of (filepath, is_protected) tuples.
    """
    tracked = git_tracked_files()
    if not tracked:
        return []

    ignored = git_check_ignore(list(tracked))
    if not ignored:
        return []

    # Check which are protected
    gitignore_path = repo_root / ".gitignore"
    entries = parse_gitignore(gitignore_path)
    protected_patterns = {
        e.pattern for e in entries if e.is_protected and e.pattern
    }

    results = []
    for filepath in sorted(ignored):
        # Check if any @protect pattern matches this file
        is_protected = False
        for pp in protected_patterns:
            # Simple check -- exact match or the pattern is a prefix
            if filepath == pp or filepath == pp.lstrip("./"):
                is_protected = True
                break
            # Check using git check-ignore with the specific pattern
            # (expensive, skip for now -- rely on exact match)

        results.append((filepath, is_protected))

    return results


def find_dead_rules(repo_root: Path) -> list[GitignoreEntry]:
    """Find .gitignore patterns that match no files in the repo."""
    gitignore_path = repo_root / ".gitignore"
    entries = parse_gitignore(gitignore_path)
    dead = []

    for entry in entries:
        if entry.is_comment or entry.is_blank or entry.is_negation or not entry.pattern:
            continue

        pattern = entry.pattern
        # Strip leading / for glob matching
        search_pattern = pattern.lstrip("/")

        # Try to find any matching file
        try:
            # Use git ls-files with the pattern
            result = subprocess.run(
                ["git", "ls-files", "--others", "--ignored",
                 "--exclude", pattern, "--"],
                capture_output=True, text=True, timeout=10,
                cwd=str(repo_root),
            )
            # Also check tracked files
            result2 = subprocess.run(
                ["git", "ls-files", "--"],
                capture_output=True, text=True, timeout=10,
                cwd=str(repo_root),
            )

            # Use pathlib glob as a simpler check
            matches = list(repo_root.glob(search_pattern))
            # Also check with ** prefix for non-anchored patterns
            if not pattern.startswith("/") and not matches:
                matches = list(repo_root.glob("**/" + search_pattern))

            if not matches:
                dead.append(entry)

        except (subprocess.TimeoutExpired, OSError):
            continue  # Skip on error, don't report as dead

    return dead


def find_missing_rules(repo_root: Path) -> list[str]:
    """Suggest gitignore patterns based on detected tech stack."""
    gitignore_path = repo_root / ".gitignore"
    existing_text = gitignore_path.read_text() if gitignore_path.exists() else ""

    missing = []

    # Check stack-specific patterns
    for indicator_file, patterns in STACK_PATTERNS.items():
        if (repo_root / indicator_file).exists():
            for pattern in patterns:
                # Check if pattern (or equivalent) already exists
                if pattern not in existing_text:
                    missing.append(pattern)

    # Check universal patterns
    for pattern in UNIVERSAL_PATTERNS:
        if pattern not in existing_text:
            missing.append(pattern)

    # Check sensitive file patterns
    for pattern in SENSITIVE_PATTERNS:
        if pattern not in existing_text:
            # Only suggest if the file type actually exists in the repo
            clean = pattern.replace("*", "").replace(".", "")
            if clean and any(
                f for f in (repo_root.glob(pattern) if "*" in pattern else [repo_root / pattern])
                if f.exists()
            ):
                missing.append(pattern)

    return sorted(set(missing))


def suggest_optimizations(repo_root: Path) -> list[str]:
    """Suggest pattern improvements and consolidation."""
    gitignore_path = repo_root / ".gitignore"
    entries = parse_gitignore(gitignore_path)
    suggestions = []

    patterns = [e for e in entries if not e.is_comment and not e.is_blank and e.pattern]

    # Check for duplicate patterns
    seen: dict[str, int] = {}
    for entry in patterns:
        key = ("!" if entry.is_negation else "") + entry.pattern
        if key in seen:
            suggestions.append(
                f"Line {entry.line_number}: Duplicate of line {seen[key]}: {key}"
            )
        else:
            seen[key] = entry.line_number

    # Check for patterns that could be consolidated
    # e.g., multiple *.ext patterns in same directory
    dir_patterns: dict[str, list[GitignoreEntry]] = {}
    for entry in patterns:
        if "/" in entry.pattern:
            dir_part = entry.pattern.rsplit("/", 1)[0]
            dir_patterns.setdefault(dir_part, []).append(entry)

    for dir_path, dir_entries in dir_patterns.items():
        if len(dir_entries) >= 3:
            suggestions.append(
                f"Consider consolidating {len(dir_entries)} patterns under "
                f"'{dir_path}/' (lines {', '.join(str(e.line_number) for e in dir_entries)})"
            )

    # Check for unanchored patterns that should be anchored
    for entry in patterns:
        if entry.pattern in (".env", "build/", "dist/", "lib/", "out/"):
            if not entry.pattern.startswith("/"):
                neg_count = sum(
                    1 for e in patterns
                    if e.is_negation and entry.pattern.rstrip("/") in e.pattern
                )
                if neg_count >= 2:
                    suggestions.append(
                        f"Line {entry.line_number}: '{entry.pattern}' is unanchored and "
                        f"requires {neg_count} negation patterns. Consider anchoring "
                        f"with '/{entry.pattern}' or using more specific paths."
                    )

    # Check for overly broad *.html-type patterns
    for entry in patterns:
        if entry.pattern.startswith("*.") and not entry.is_negation:
            ext = entry.pattern
            neg_count = sum(
                1 for e in patterns if e.is_negation and ext[1:] in e.pattern
            )
            if neg_count >= 2:
                suggestions.append(
                    f"Line {entry.line_number}: '{ext}' requires {neg_count} negation "
                    f"exceptions. Consider more specific paths instead of blanket extension ignore."
                )

    return suggestions


# ---------------------------------------------------------------------------
# Action commands
# ---------------------------------------------------------------------------

def cmd_audit(args: argparse.Namespace) -> int:
    """Run full audit."""
    root = git_root()
    print(f"Auditing .gitignore in {root}\n")

    # Tracked-ignored
    ti = find_tracked_ignored(root)
    unprotected = [(f, p) for f, p in ti if not p]
    protected = [(f, p) for f, p in ti if p]

    if unprotected:
        print(f"TRACKED-BUT-IGNORED ({len(unprotected)} files):")
        for filepath, _ in unprotected:
            print(f"  ! {filepath}")
        print()
    else:
        print("TRACKED-BUT-IGNORED: None found (clean)")
        print()

    if protected:
        print(f"PROTECTED TRACKED-IGNORED ({len(protected)} files, intentional):")
        for filepath, _ in protected:
            print(f"  @ {filepath}")
        print()

    # Dead rules
    dead = find_dead_rules(root)
    if dead:
        print(f"DEAD RULES ({len(dead)} patterns match nothing):")
        for entry in dead:
            print(f"  Line {entry.line_number}: {entry.pattern}")
        print()
    else:
        print("DEAD RULES: None found")
        print()

    # Missing rules
    missing = find_missing_rules(root)
    if missing:
        print(f"MISSING RULES ({len(missing)} suggested patterns):")
        for pattern in missing:
            print(f"  + {pattern}")
        print()
    else:
        print("MISSING RULES: None suggested")
        print()

    # Optimizations
    opts = suggest_optimizations(root)
    if opts:
        print(f"OPTIMIZATIONS ({len(opts)} suggestions):")
        for suggestion in opts:
            print(f"  ~ {suggestion}")
        print()
    else:
        print("OPTIMIZATIONS: None suggested")
        print()

    # IDE sync hint
    gitignore_path = root / ".gitignore"
    gi_entries = parse_gitignore(gitignore_path)
    indexed_count = sum(1 for e in gi_entries if e.is_indexed and e.pattern)
    if indexed_count > 0:
        print(f"IDE INDEX OVERRIDES: {indexed_count} pattern(s) marked @index")
        print()

    print("IDE SYNC: Run 'python3 tools/ide_exclusion_audit.py audit' to check "
          "IDE exclusion drift")
    print()

    # Summary
    issues = len(unprotected) + len(dead) + len(missing) + len(opts)
    if issues == 0:
        print("RESULT: .gitignore is healthy")
        return 0
    else:
        print(f"RESULT: {issues} issues found")
        return 1


def cmd_tracked_ignored(args: argparse.Namespace) -> int:
    """Find tracked files matching .gitignore patterns."""
    root = git_root()
    results = find_tracked_ignored(root)

    if not results:
        print("No tracked files match .gitignore patterns.")
        return 0

    for filepath, is_protected in results:
        marker = "@" if is_protected else "!"
        label = " (protected)" if is_protected else ""
        print(f"  {marker} {filepath}{label}")

    unprotected = [f for f, p in results if not p]
    if unprotected:
        print(f"\n{len(unprotected)} unprotected file(s) should be untracked:")
        print(f"  git rm --cached {' '.join(unprotected[:5])}")
        if len(unprotected) > 5:
            print(f"  ... and {len(unprotected) - 5} more")
    return 1 if unprotected else 0


def cmd_dead_rules(args: argparse.Namespace) -> int:
    """Find .gitignore patterns that match nothing."""
    root = git_root()
    dead = find_dead_rules(root)

    if not dead:
        print("No dead rules found. All patterns match at least one file.")
        return 0

    print(f"{len(dead)} dead rules found:")
    for entry in dead:
        protected = " (protected, keeping)" if entry.is_protected else ""
        print(f"  Line {entry.line_number}: {entry.pattern}{protected}")

    return 1


def cmd_missing_rules(args: argparse.Namespace) -> int:
    """Suggest patterns that should be in .gitignore."""
    root = git_root()
    missing = find_missing_rules(root)

    if not missing:
        print("No missing patterns detected for the current tech stack.")
        return 0

    print(f"{len(missing)} suggested patterns:")
    for pattern in missing:
        print(f"  + {pattern}")

    return 1


def cmd_optimize(args: argparse.Namespace) -> int:
    """Suggest pattern improvements."""
    root = git_root()
    opts = suggest_optimizations(root)

    if not opts:
        print("No optimizations suggested. Patterns look good.")
        return 0

    print(f"{len(opts)} suggestions:")
    for suggestion in opts:
        print(f"  ~ {suggestion}")

    return 1


def cmd_untrack(args: argparse.Namespace) -> int:
    """Untrack a file (git rm --cached)."""
    filepath = args.file
    root = git_root()

    # Verify file is tracked
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", filepath],
        capture_output=True, text=True, timeout=10,
        cwd=str(root),
    )
    if result.returncode != 0:
        print(f"ERROR: '{filepath}' is not tracked by git.", file=sys.stderr)
        return 1

    # Check if it's protected
    gitignore_path = root / ".gitignore"
    entries = parse_gitignore(gitignore_path)
    for entry in entries:
        if entry.is_protected and entry.pattern and filepath.endswith(entry.pattern.lstrip("./")):
            print(f"WARNING: '{filepath}' is @protected: {entry.protect_reason}")
            print("Use --force to override protection.")
            if not getattr(args, "force", False):
                return 1

    # Untrack
    result = subprocess.run(
        ["git", "rm", "--cached", filepath],
        capture_output=True, text=True, timeout=10,
        cwd=str(root),
    )
    if result.returncode != 0:
        print(f"ERROR: git rm --cached failed: {result.stderr}", file=sys.stderr)
        return 1

    print(f"Untracked: {filepath}")
    print(f"File still exists locally. Verify it's in .gitignore, then commit.")
    return 0


def cmd_purge(args: argparse.Namespace) -> int:
    """Guide through purging a file from git history."""
    filepath = args.file
    root = git_root()

    print(f"PURGE: {filepath}")
    print("=" * 60)
    print()
    print("This will REWRITE git history. This is destructive and irreversible.")
    print("All collaborators must re-clone after a purge.")
    print()

    # Check if file exists in history
    result = subprocess.run(
        ["git", "log", "--all", "--oneline", "--diff-filter=A", "--", filepath],
        capture_output=True, text=True, timeout=30,
        cwd=str(root),
    )

    if not result.stdout.strip():
        print(f"'{filepath}' was never committed to git history.")
        return 0

    commits = result.stdout.strip().splitlines()
    print(f"Found in {len(commits)} commit(s):")
    for commit in commits[:10]:
        print(f"  {commit}")
    if len(commits) > 10:
        print(f"  ... and {len(commits) - 10} more")

    print()
    print("Recommended purge method (choose one):")
    print()
    print("1. git-filter-repo (recommended, install with: pip install git-filter-repo)")
    print(f"   git filter-repo --invert-paths --path {filepath}")
    print()
    print("2. BFG Repo Cleaner (simpler for secrets)")
    print(f"   bfg --delete-files {Path(filepath).name} .git")
    print("   git reflog expire --expire=now --all")
    print("   git gc --prune=now --aggressive")
    print()
    print("After purging:")
    print("  1. git push --force --all")
    print("  2. git push --force --tags")
    print("  3. ROTATE any credentials that were in the file")
    print("  4. Notify all collaborators to re-clone")
    print("  5. Contact GitHub support if repo is public (to clear caches)")

    return 0


def cmd_protect(args: argparse.Namespace) -> int:
    """Add @protect annotation to a .gitignore entry."""
    pattern = args.pattern
    reason = args.reason
    root = git_root()
    gitignore_path = root / ".gitignore"

    if not gitignore_path.exists():
        print("ERROR: .gitignore not found.", file=sys.stderr)
        return 1

    lines = gitignore_path.read_text().splitlines()
    found = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == pattern:
            # Check if already protected
            if i > 0 and lines[i - 1].strip().startswith("# @protect:"):
                print(f"Pattern '{pattern}' is already protected.")
                return 0

            # Insert @protect comment before the pattern
            lines.insert(i, f"# @protect: {reason}")
            found = True
            break

    if not found:
        print(f"Pattern '{pattern}' not found in .gitignore.", file=sys.stderr)
        print(f"Add it first, then protect it.")
        return 1

    gitignore_path.write_text("\n".join(lines) + "\n")
    print(f"Protected: {pattern}")
    print(f"Reason: {reason}")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    """Add @index annotation to a .gitignore entry."""
    pattern = args.pattern
    reason = args.reason
    root = git_root()
    gitignore_path = root / ".gitignore"

    if not gitignore_path.exists():
        print("ERROR: .gitignore not found.", file=sys.stderr)
        return 1

    lines = gitignore_path.read_text().splitlines()
    found = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == pattern:
            # Check if already indexed
            if i > 0 and lines[i - 1].strip().startswith("# @index:"):
                print(f"Pattern '{pattern}' is already marked @index.")
                return 0

            # Insert @index comment before the pattern
            lines.insert(i, f"# @index: {reason}")
            found = True
            break

    if not found:
        print(f"Pattern '{pattern}' not found in .gitignore.", file=sys.stderr)
        print(f"Add it first, then mark it @index.")
        return 1

    gitignore_path.write_text("\n".join(lines) + "\n")
    print(f"Indexed: {pattern}")
    print(f"Reason: {reason}")
    print(f"This pattern will remain visible/searchable in IDE indexes.")
    return 0


def cmd_hook_validate(args: argparse.Namespace) -> int:
    """Validate a .gitignore change from a PreToolUse hook.

    Reads JSON from stdin with tool_name and tool_input.
    Exit 0 = allow, Exit 2 = block.
    """
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0  # Can't parse, allow

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("filePath", "")

    # Only check .gitignore files
    if not file_path.endswith(".gitignore"):
        return 0

    # Get the content being written/edited
    if tool_name == "Write":
        new_content = tool_input.get("content", "")
        old_content = ""
        # Read current .gitignore for comparison
        root = git_root()
        gitignore_path = root / ".gitignore"
        if gitignore_path.exists():
            old_content = gitignore_path.read_text()
    elif tool_name in ("Edit", "MultiEdit"):
        old_string = tool_input.get("old_string", "")
        new_string = tool_input.get("new_string", "")
        old_content = old_string
        new_content = new_string
    else:
        return 0

    violations = []

    # Check 1: Removing sensitive pattern protection
    for sensitive in SENSITIVE_PATTERNS:
        if sensitive in old_content and sensitive not in new_content:
            violations.append(
                f"Removing sensitive pattern '{sensitive}' -- this could expose secrets"
            )

    # Check 2: Removing @protect annotations
    if "# @protect:" in old_content and "# @protect:" not in new_content:
        violations.append(
            "Removing @protect annotation -- protected entries exist for a reason"
        )

    if "# @protect-start:" in old_content and "# @protect-start:" not in new_content:
        violations.append(
            "Removing @protect-start block -- protected entries exist for a reason"
        )

    # Check 3: Adding overly broad patterns
    new_lines = new_content.splitlines() if new_content else []
    for line in new_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("!"):
            if stripped in OVERLY_BROAD_PATTERNS:
                violations.append(
                    f"Adding overly broad pattern '{stripped}' -- "
                    f"this would ignore source files"
                )

    if violations:
        msg = "BLOCKED: Dangerous .gitignore modification\n\n"
        msg += "Violations:\n"
        for v in violations:
            msg += f"  - {v}\n"
        msg += "\nIf this is intentional, discuss with the user first."
        print(msg, file=sys.stderr)
        return 2

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit, optimize, and protect .gitignore files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("audit", help="Full health check")
    subparsers.add_parser("tracked-ignored",
                          help="Find tracked files matching .gitignore")
    subparsers.add_parser("dead-rules",
                          help="Find patterns that match nothing")
    subparsers.add_parser("missing-rules",
                          help="Suggest patterns for detected tech stack")
    subparsers.add_parser("optimize",
                          help="Suggest pattern improvements")

    untrack = subparsers.add_parser("untrack",
                                    help="Untrack a file (git rm --cached)")
    untrack.add_argument("file", help="File to untrack")
    untrack.add_argument("--force", action="store_true",
                         help="Override @protect")

    purge = subparsers.add_parser("purge",
                                  help="Guide through history purge")
    purge.add_argument("file", help="File to purge from history")

    protect = subparsers.add_parser("protect",
                                    help="Add @protect annotation")
    protect.add_argument("pattern", help="Gitignore pattern to protect")
    protect.add_argument("reason", help="Reason for protection")

    index = subparsers.add_parser("index",
                                   help="Add @index annotation (keep in IDE index)")
    index.add_argument("pattern", help="Gitignore pattern to keep indexed")
    index.add_argument("reason", help="Reason for keeping in IDE index")

    subparsers.add_parser("hook-validate",
                          help="PreToolUse hook validator (reads stdin)")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "audit": cmd_audit,
        "tracked-ignored": cmd_tracked_ignored,
        "dead-rules": cmd_dead_rules,
        "missing-rules": cmd_missing_rules,
        "optimize": cmd_optimize,
        "untrack": cmd_untrack,
        "purge": cmd_purge,
        "protect": cmd_protect,
        "index": cmd_index,
        "hook-validate": cmd_hook_validate,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
