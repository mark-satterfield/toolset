#!/usr/bin/env python3
"""
CDS plugin structural test runner.

Discovers every ``check_*.py`` module under ``checks/`` (siblings of this file),
imports each via importlib, and calls its ``run(repo_root)`` entry point. Each
module returns a list of failure strings (an empty list means it passed).

``repo_root`` is the monorepo root. This file lives at
``<root>/plugins/cds/test/check-plugin.py``, so the root is three levels up
from the test directory.

For each module a status line is printed:

    <name> ........ PASS         (no failures)
    <name> ........ FAIL (<n>)   (n failures)

After the status lines, every failure string from every module is printed.
Exit code 0 = all modules clean, 1 = one or more modules returned failures.

Usage:
    python3 check-plugin.py
"""
import importlib.util
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS_DIR = os.path.join(HERE, "checks")
# <root>/plugins/cds/test -> up three levels == <root>
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

# Width to pad the module name out to before the PASS/FAIL verdict, matching
# the dotted-leader style of lint-elements.py.
PAD = 28


def discover():
    """Return sorted absolute paths of every check_*.py under checks/."""
    if not os.path.isdir(CHECKS_DIR):
        return []
    names = [
        n for n in os.listdir(CHECKS_DIR)
        if n.startswith("check_") and n.endswith(".py")
    ]
    return [os.path.join(CHECKS_DIR, n) for n in sorted(names)]


def load_module(path):
    """Import a check module from its file path under a unique module name."""
    mod_name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def line(name, verdict):
    dots = "." * max(4, PAD - len(name))
    return f"{name} {dots} {verdict}"


def main():
    modules = discover()
    if not modules:
        print(f"No check_*.py modules found in {CHECKS_DIR}")
        sys.exit(1)

    all_failures = []

    for path in modules:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            module = load_module(path)
            if not hasattr(module, "run"):
                fails = [f"{name}: module has no run(repo_root) entry point"]
            else:
                result = module.run(REPO_ROOT)
                fails = list(result) if result else []
        except Exception:
            fails = [f"{name}: raised during run():\n{traceback.format_exc()}"]

        if fails:
            print(line(name, f"FAIL ({len(fails)})"))
        else:
            print(line(name, "PASS"))
        all_failures += fails

    if all_failures:
        print(f"\n{len(all_failures)} FAILURE(S):")
        for f in all_failures:
            print("  ✗  ", f)
        sys.exit(1)

    print("\nAll plugin checks passed.")


if __name__ == "__main__":
    main()
