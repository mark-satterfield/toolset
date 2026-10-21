"""The tooling the control repo copies into every repository, so each repository is self-contained.

The config's `tooling_sync.files` lists each file or folder the control repo holds the master copy of,
the repository-relative path it is copied to, and optionally the repository types (the type token the
naming command reads in a repository name) that receive it and the repositories that do not
(`exclude`). A folder is mirrored: a file in the copy
that the master does not hold is removed. Each copy keeps its master's executable bit.

The control repo reaches out to the repositories; nothing in a repository points back to the control
repo. This module only plans and writes files; `polyrepo.py` commits and pushes them.
"""

from __future__ import annotations

import dataclasses
import stat
from pathlib import Path
from typing import Final

SKIPPED_NAMES: Final = frozenset({".DS_Store", "__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache"})
EXECUTABLE_MODE: Final = 0o755
PLAIN_MODE: Final = 0o644


class ToolingSyncError(ValueError):
    """The config's `tooling_sync` section is malformed or names a master that does not exist."""


@dataclasses.dataclass(frozen=True)
class ToolingFile:
    """One master file or folder and where every receiving repository holds its copy."""

    source: Path
    target: str
    types: frozenset[str]
    exclude: frozenset[str]

    def applies_to(self, name: str, repo_type: str | None) -> bool:
        """Say whether a repository receives the copy.

        Returns:
            False for an excluded repository; else True when the entry names no types, or names the
            repository's type.

        """
        if name in self.exclude:
            return False
        return not self.types or (repo_type is not None and repo_type in self.types)


@dataclasses.dataclass(frozen=True)
class ToolingSpec:
    """The tooling every repository receives, and the repositories and spaces that receive none."""

    files: tuple[ToolingFile, ...]
    exclude: frozenset[str]
    exclude_spaces: frozenset[str]

    def applies_to(self, name: str, space: str) -> bool:
        """Say whether a repository receives tooling at all.

        Returns:
            True unless the repository or its app space is excluded.

        """
        return name not in self.exclude and space not in self.exclude_spaces

    @property
    def typed(self) -> bool:
        """Say whether any entry depends on the repository's type.

        Returns:
            True when an entry names types.

        """
        return any(f.types for f in self.files)


@dataclasses.dataclass(frozen=True)
class Copy:
    """The content and mode a repository-relative file should have; None content means remove it."""

    content: bytes | None
    mode: int


def _strings(value: object, what: str) -> frozenset[str]:
    """Validate a list of strings.

    Returns:
        The strings.

    Raises:
        ToolingSyncError: when the value is not a list of strings.

    """
    if value is None:
        return frozenset()
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        msg = f"config tooling_sync {what}: expected a list of names"
        raise ToolingSyncError(msg)
    return frozenset(value)


def _entry(raw: object, base: Path, index: int) -> ToolingFile:
    """Validate one `tooling_sync.files` entry.

    Returns:
        The entry, its source resolved against the config file's folder.

    Raises:
        ToolingSyncError: when a key is missing or malformed, the target escapes the repository, or the
            source does not exist.

    """
    if not isinstance(raw, dict):
        msg = f"config tooling_sync.files[{index}]: expected a mapping with source and target"
        raise ToolingSyncError(msg)
    source, target = raw.get("source"), raw.get("target")
    if not isinstance(source, str) or not source or not isinstance(target, str) or not target:
        msg = f"config tooling_sync.files[{index}]: source and target are required strings"
        raise ToolingSyncError(msg)
    if Path(target).is_absolute() or ".." in Path(target).parts:
        msg = f"config tooling_sync.files[{index}]: target {target!r} must be a path inside the repository"
        raise ToolingSyncError(msg)
    resolved = (base / source).resolve()
    if not resolved.exists():
        msg = f"config tooling_sync.files[{index}]: source {resolved} not found"
        raise ToolingSyncError(msg)
    return ToolingFile(
        resolved,
        Path(target).as_posix(),
        _strings(raw.get("types"), f"files[{index}].types"),
        _strings(raw.get("exclude"), f"files[{index}].exclude"),
    )


def load_spec(raw: object, base: Path) -> ToolingSpec | None:
    """Read the config's `tooling_sync` section.

    Args:
        raw: The section's value; None when the config has none.
        base: The config file's folder, which relative sources are resolved against.

    Returns:
        The spec, or None when the config has no section.

    Raises:
        ToolingSyncError: when the section is malformed.

    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        msg = "config tooling_sync: expected a mapping"
        raise ToolingSyncError(msg)
    files = raw.get("files")
    if not isinstance(files, list) or not files:
        msg = "config tooling_sync.files: expected a non-empty list"
        raise ToolingSyncError(msg)
    return ToolingSpec(
        tuple(_entry(item, base, i) for i, item in enumerate(files)),
        _strings(raw.get("exclude"), "exclude"),
        _strings(raw.get("exclude_spaces"), "exclude_spaces"),
    )


def _mode(path: Path) -> int:
    """Return the mode a copy of a master file gets: executable when the master is.

    Returns:
        0o755 or 0o644.

    """
    return EXECUTABLE_MODE if path.stat().st_mode & stat.S_IXUSR else PLAIN_MODE


def _master_files(entry: ToolingFile) -> dict[str, Path]:
    """List the files of one master, keyed by the repository-relative path of their copy.

    Returns:
        Copy path to master file.

    """
    if entry.source.is_file():
        return {entry.target: entry.source}
    return {
        f"{entry.target}/{f.relative_to(entry.source).as_posix()}": f
        for f in sorted(entry.source.rglob("*"))
        if f.is_file() and not SKIPPED_NAMES.intersection(f.relative_to(entry.source).parts)
    }


def _copy_files(repo: Path, entry: ToolingFile) -> dict[str, Path]:
    """List the files a repository's copy of a master folder holds.

    Returns:
        Repository-relative path to file; empty for a master file or a missing copy.

    """
    folder = repo / entry.target
    if entry.source.is_file() or not folder.is_dir():
        return {}
    return {
        f"{entry.target}/{f.relative_to(folder).as_posix()}": f
        for f in sorted(folder.rglob("*"))
        if f.is_file() and not SKIPPED_NAMES.intersection(f.relative_to(folder).parts)
    }


def _differs(dest: Path, master: Path) -> bool:
    """Say whether a copy is missing, or differs from its master in content or executable bit.

    Returns:
        True when the copy must be written.

    """
    if not dest.is_file():
        return True
    return dest.read_bytes() != master.read_bytes() or _mode(dest) != _mode(master)


def copy_of(master: Path, dest: Path) -> Copy | None:
    """Return the copy a destination file should hold of its master, or None when it holds it already.

    A destination that is the master itself needs nothing.

    Returns:
        The master's content and mode, or None.

    """
    if dest.resolve() == master.resolve() or not _differs(dest, master):
        return None
    return Copy(master.read_bytes(), _mode(master))


def plan(spec: ToolingSpec, repo: Path, name: str, repo_type: str | None) -> dict[str, Copy]:
    """Return what a repository needs written or removed so its tooling copies equal their masters.

    A repository that is the master's own repository plans nothing for it.

    Returns:
        Repository-relative path to the copy it should hold; empty when the repository is current.

    """
    out: dict[str, Copy] = {}
    for entry in spec.files:
        if not entry.applies_to(name, repo_type):
            continue
        masters = _master_files(entry)
        out.update({rel: c for rel, master in masters.items() if (c := copy_of(master, repo / rel)) is not None})
        for rel in _copy_files(repo, entry).keys() - masters.keys():
            out[rel] = Copy(None, PLAIN_MODE)
    return out


def apply(repo: Path, copies: dict[str, Copy]) -> list[str]:
    """Write and remove the planned copies in a repository's working tree, committing nothing.

    Returns:
        The repository-relative paths changed, sorted.

    """
    for rel, copy in copies.items():
        dest = repo / rel
        if copy.content is None:
            dest.unlink(missing_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(copy.content)
        dest.chmod(copy.mode)
    return sorted(copies)
