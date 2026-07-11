#!/usr/bin/env python3
"""Detect the active Python environment and recommend how (or whether) to
install this skill's dependencies. Single source of truth: SKILL.md and
install.md both defer to this script.

To reuse for another skill, edit REQUIRED and INSTALL_ARGS only.

The deps below are imported at runtime, not run as CLIs, so they must live in
the *active* interpreter's environment. pipx does not apply (it exposes CLI
entry points, not importable modules).
"""
import importlib.util
import os
import sys

REQUIRED = ("markitdown", "trafilatura")
INSTALL_ARGS = "'markitdown[all]' trafilatura"


def importable(mod):
    return importlib.util.find_spec(mod) is not None


def venv_made_by_uv():
    cfg = os.path.join(sys.prefix, "pyvenv.cfg")
    if not os.path.exists(cfg):
        return False
    try:
        with open(cfg) as f:
            for line in f:
                if line.split("=", 1)[0].strip().lower() == "uv":
                    return True
    except OSError:
        pass
    return False


def detect_manager(in_venv):
    if "CONDA_PREFIX" in os.environ:
        return "conda"
    if os.environ.get("POETRY_ACTIVE"):
        return "poetry"
    if os.environ.get("PIPENV_ACTIVE"):
        return "pipenv"
    if in_venv and (venv_made_by_uv() or os.path.exists("uv.lock")):
        return "uv"
    if in_venv:
        return "venv"
    return "global"


def main():
    exe = sys.executable
    in_venv = sys.prefix != sys.base_prefix
    mgr = detect_manager(in_venv)
    missing = [m for m in REQUIRED if not importable(m)]

    print(f"python   : {exe}")
    print(f"in_venv  : {in_venv}")
    print(f"manager  : {mgr}")
    print(f"missing  : {' '.join(missing) if missing else 'none'}")
    print("---")

    if not missing:
        print("ACTION: none")
        print("All dependencies already importable. Skip install.")
        return 0

    if mgr == "global":
        print("ACTION: stop")
        print("No active virtualenv. Refusing to install into system/Homebrew "
              "Python (PEP 668). These packages are imported, so pipx does not "
              "apply. Create and activate an environment, then re-run:")
        print("  python3 -m venv .venv && source .venv/bin/activate")
        print("  # or, for a uv project: uv venv && source .venv/bin/activate")
        return 1

    if mgr == "uv":
        print(f"ACTION: uv pip install {INSTALL_ARGS}")
    elif mgr == "conda":
        print(f"ACTION: {exe} -m pip install {INSTALL_ARGS}")
    elif mgr == "poetry":
        print(f"ACTION: poetry add {INSTALL_ARGS}")
        print(f"(or activate the env and: {exe} -m pip install {INSTALL_ARGS})")
    elif mgr == "pipenv":
        print(f"ACTION: pipenv install {INSTALL_ARGS}")
        print(f"(or activate the env and: {exe} -m pip install {INSTALL_ARGS})")
    else:  # venv
        print(f"ACTION: {exe} -m pip install {INSTALL_ARGS}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
