"""Fail on an import cycle among first-party modules, or on a first-party module that does not import.

Each source root is a ``sys.path`` entry: its top-level ``.py`` files are modules, and its
folders holding an ``__init__.py`` are packages, recursively. Every import statement counts,
wherever it sits (module level, a function body, an ``if TYPE_CHECKING:`` block), so a cycle
cannot be hidden by moving one of its imports. Each module is then imported first, alone, in
a fresh interpreter with every root on ``sys.path``, the way an entry point would import it.

Usage:
    python check_import_graph.py [--mypy-config FILE] [ROOT ...]

``--mypy-config`` adds the roots listed in that file's ``mypy_path``. Exit status: 0 clean,
1 findings, 2 usage error. Findings go to stdout.
"""

from __future__ import annotations

import argparse
import ast
import configparser
import os
import subprocess  # ruff: ignore[suspicious-subprocess-import] - every command is a fixed argv list run without a shell
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Final

EXIT_CLEAN: Final = 0
EXIT_FINDINGS: Final = 1
EXIT_USAGE: Final = 2
IMPORT_TIMEOUT_SECONDS: Final = 120
SKIPPED_DIRS: Final = frozenset({"__pycache__", "tests", ".venv", "node_modules"})
MYPY_SECTION: Final = "mypy"
MYPY_PATH_KEY: Final = "mypy_path"
CONFIG_DIR_VARIABLE: Final = "$MYPY_CONFIG_FILE_DIR"
IMPORT_PROBE: Final = "import importlib, sys; sys.path[:0] = sys.argv[2:]; importlib.import_module(sys.argv[1])"


@dataclass(frozen=True)
class Module:
    """One first-party module: its dotted name, its file, and whether it is a package."""

    name: str
    path: Path
    is_package: bool


def _package_modules(package_dir: Path, prefix: str) -> list[Module]:
    """Return the modules of one package folder and of its sub-packages.

    Args:
        package_dir: A folder holding an ``__init__.py``.
        prefix: The package's dotted name.

    Returns:
        The package itself, its modules and the modules of every sub-package.

    """
    found: list[Module] = [Module(prefix, package_dir / "__init__.py", is_package=True)]
    found += [
        Module(f"{prefix}.{path.stem}", path, is_package=False)
        for path in sorted(package_dir.glob("*.py"))
        if path.name != "__init__.py"
    ]
    for child in sorted(package_dir.iterdir()):
        if child.name not in SKIPPED_DIRS and (child / "__init__.py").is_file():
            found += _package_modules(child, f"{prefix}.{child.name}")
    return found


def root_modules(root: Path) -> list[Module]:
    """Return every module importable with ``root`` on ``sys.path``.

    Args:
        root: A source root.

    Returns:
        Its top-level modules, and the modules of its top-level packages.

    """
    found: list[Module] = [Module(path.stem, path, is_package=False) for path in sorted(root.glob("*.py"))]
    for child in sorted(root.iterdir()):
        if child.name not in SKIPPED_DIRS and (child / "__init__.py").is_file():
            found += _package_modules(child, child.name)
    return found


def _ancestors(name: str) -> set[str]:
    """Return the dotted names of the packages that contain a module.

    Returns:
        Every proper prefix of ``name``.

    """
    parts: list[str] = name.split(".")
    return {".".join(parts[:end]) for end in range(1, len(parts))}


def _resolve_relative(module: Module, level: int, target: str | None) -> str:
    """Return the absolute name a relative ``from`` import names.

    Returns:
        The dotted name of the imported module or package.

    """
    package_parts: list[str] = module.name.split(".") if module.is_package else module.name.split(".")[:-1]
    base: list[str] = package_parts[: len(package_parts) - level + 1]
    return ".".join([*base, target] if target else base)


def _imported_names(module: Module, node: ast.Import | ast.ImportFrom) -> set[str]:
    """Return every dotted name one import statement loads.

    Returns:
        The imported modules, and for ``from X import Y`` also ``X.Y``, which is a module when Y is one.

    """
    if isinstance(node, ast.Import):
        return {alias.name for alias in node.names}
    source: str = _resolve_relative(module, node.level, node.module) if node.level else node.module or ""
    return {source} | {f"{source}.{alias.name}" for alias in node.names}


def import_edges(module: Module, first_party: set[str]) -> set[str]:
    """Return the first-party modules one module imports, anywhere in its source.

    An import of a package's own module from inside that package does not reach the package
    again, because Python has already started the package; those edges are left out.

    Args:
        module: The importing module.
        first_party: Every first-party module name.

    Returns:
        The first-party modules and packages it loads.

    """
    tree: ast.Module = ast.parse(module.path.read_text(encoding="utf-8"), filename=str(module.path))
    nodes: list[ast.Import | ast.ImportFrom] = [
        node for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom)
    ]
    loaded: set[str] = set()
    for node in nodes:
        loaded |= _imported_names(module, node)
    reached: set[str] = loaded | {ancestor for name in loaded for ancestor in _ancestors(name)}
    return (reached & first_party) - _ancestors(module.name) - {module.name}


@dataclass
class _Tarjan:
    """State of Tarjan's strongly connected components walk over the import graph."""

    graph: dict[str, set[str]]
    index: dict[str, int]
    low: dict[str, int]
    stack: list[str]
    on_stack: set[str]
    cycles: list[list[str]]

    def visit(self, start: str) -> None:
        """Walk from one module without recursion, recording every cycle found."""
        work: list[tuple[str, list[str]]] = [(start, sorted(self.graph[start]))]
        self._enter(start)
        while work:
            name, pending = work[-1]
            if pending:
                self._follow(name, pending.pop(), work)
                continue
            work.pop()
            if work:
                parent: str = work[-1][0]
                self.low[parent] = min(self.low[parent], self.low[name])
            self._close(name)

    def _enter(self, name: str) -> None:
        """Give a module its walk index and push it on the stack."""
        self.index[name] = self.low[name] = len(self.index)
        self.stack.append(name)
        self.on_stack.add(name)

    def _follow(self, name: str, target: str, work: list[tuple[str, list[str]]]) -> None:
        """Descend into an unvisited import, or lower the module's link to one on the stack."""
        if target not in self.index:
            self._enter(target)
            work.append((target, sorted(self.graph[target])))
            return
        if target in self.on_stack:
            self.low[name] = min(self.low[name], self.index[target])

    def _close(self, name: str) -> None:
        """Pop a finished component off the stack, recording it when it is a cycle."""
        if self.low[name] != self.index[name]:
            return
        component: list[str] = []
        while not component or component[-1] != name:
            member: str = self.stack.pop()
            self.on_stack.discard(member)
            component.append(member)
        if len(component) > 1:
            self.cycles.append(sorted(component))


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Return each group of modules that import one another, directly or through others.

    Returns:
        The strongly connected components of more than one module, each sorted.

    """
    walk: _Tarjan = _Tarjan(graph, {}, {}, [], set(), [])
    for name in sorted(graph):
        if name not in walk.index:
            walk.visit(name)
    return sorted(walk.cycles)


def import_failure(name: str, roots: list[Path]) -> str | None:
    """Import one module first, alone, in a fresh interpreter.

    Returns:
        The interpreter's error output when the import fails, else None.

    """
    command: list[str] = [sys.executable, "-c", IMPORT_PROBE, name, *(str(root) for root in roots)]
    environment: dict[str, str] = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        completed: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed argv, no shell
            command,
            capture_output=True,
            text=True,
            timeout=IMPORT_TIMEOUT_SECONDS,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        return f"import did not finish within {IMPORT_TIMEOUT_SECONDS} s"
    if completed.returncode == 0:
        return None
    return completed.stderr.strip() or f"exit status {completed.returncode}"


def mypy_path_roots(config_file: Path) -> list[Path]:
    """Return the source roots a mypy configuration lists in ``mypy_path``.

    Returns:
        Each listed folder, with ``$MYPY_CONFIG_FILE_DIR`` replaced by the file's folder.

    Raises:
        ValueError: The file has no ``[mypy] mypy_path``.

    """
    parser: configparser.ConfigParser = configparser.ConfigParser()
    parser.read(config_file, encoding="utf-8")
    if not parser.has_option(MYPY_SECTION, MYPY_PATH_KEY):
        message: str = f"{config_file} has no [{MYPY_SECTION}] {MYPY_PATH_KEY}"
        raise ValueError(message)
    config_dir: str = str(config_file.resolve().parent)
    entries: list[str] = parser.get(MYPY_SECTION, MYPY_PATH_KEY).replace(",", ":").split(":")
    return [Path(entry.strip().replace(CONFIG_DIR_VARIABLE, config_dir)) for entry in entries if entry.strip()]


def collect_modules(roots: list[Path]) -> tuple[dict[str, Module], list[str]]:
    """Return every first-party module by name, and each name more than one root defines.

    Returns:
        The modules, and a finding for each name that one root shadows in another.

    """
    modules: dict[str, Module] = {}
    shadowed: list[str] = []
    for module in (module for root in roots for module in root_modules(root)):
        prior: Module | None = modules.get(module.name)
        if prior is not None:
            shadowed.append(f"module {module.name} is defined twice: {prior.path} and {module.path}")
            continue
        modules[module.name] = module
    return modules, shadowed


def check(roots: list[Path]) -> list[str]:
    """Return every finding for the source roots.

    Returns:
        One line per shadowed module, per import cycle and per module that fails to import.

    """
    modules, findings = collect_modules(roots)
    names: set[str] = set(modules)
    graph: dict[str, set[str]] = {name: import_edges(module, names) for name, module in modules.items()}
    findings += [f"import cycle: {' -> '.join(cycle)}" for cycle in find_cycles(graph)]
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as pool:
        failures: list[str | None] = list(pool.map(lambda name: import_failure(name, roots), sorted(names)))
    findings += [
        f"module {name} fails to import first:\n{failure}"
        for name, failure in zip(sorted(names), failures, strict=True)
        if failure is not None
    ]
    return findings


def main(argv: list[str]) -> int:
    """Run the check and print its findings.

    Returns:
        The exit status: 0 clean, 1 findings, 2 usage error.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("roots", nargs="*", type=Path, help="a source root, as a sys.path entry")
    parser.add_argument("--mypy-config", type=Path, help="also check the roots in this file's mypy_path")
    arguments: argparse.Namespace = parser.parse_args(argv)
    roots: list[Path] = [Path(root) for root in arguments.roots]
    try:
        roots += mypy_path_roots(arguments.mypy_config) if arguments.mypy_config else []
    except ValueError as error:
        sys.stderr.write(f"{error}\n")
        return EXIT_USAGE
    missing: list[Path] = [root for root in roots if not root.is_dir()]
    if not roots or missing:
        sys.stderr.write(f"no source roots given, or not folders: {[str(root) for root in missing]}\n")
        return EXIT_USAGE
    findings: list[str] = check([root.resolve() for root in roots])
    sys.stdout.write("".join(f"{finding}\n" for finding in findings))
    return EXIT_FINDINGS if findings else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
