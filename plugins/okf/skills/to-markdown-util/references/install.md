# Dependency Installation

The skill imports `markitdown` and `trafilatura` at runtime. Because they are
imported (not run as standalone CLIs), they must live in the environment of the
interpreter that runs the skill's scripts. `pipx` does not satisfy this: it
exposes CLI entry points, not importable modules.

## Prerequisites

- Python 3.10+. Verify: `python3 --version`
- An active virtual environment. The skill will not install into system or
  Homebrew Python: PEP 668 blocks it, and it pollutes the base interpreter.

## Let the check decide

`references/env_check.py` resolves the active interpreter, detects the manager,
and reports what to do:

```bash
python3 references/env_check.py
```

It prints the active `python`, whether a virtualenv is active, the detected
manager, which required packages are missing, and an `ACTION:` line. Follow the
ACTION. You should not need the rest of this file unless the ACTION is `stop` or
you want a smaller, format-specific install.

## How detection works

Active interpreter and isolation:

```bash
python3 -c "import sys; print(sys.executable)"
python3 -c "import sys; print('in_venv:', sys.prefix != sys.base_prefix)"
```

`in_venv: False` means no environment is active and the shell is on
system/global Python; fix that before installing. `in_venv: True` means installs
land in that environment.

Manager resolution order: `CONDA_PREFIX` → `POETRY_ACTIVE` → `PIPENV_ACTIVE` →
uv → plain venv → global. A uv-managed venv is identified by a `uv = <version>`
line in its `pyvenv.cfg`, with `uv.lock` in the working directory as a fallback
signal.

## No active environment

Create and activate one, then re-run the check:

```bash
python3 -m venv .venv && source .venv/bin/activate
# or, for a uv project:
uv venv && source .venv/bin/activate
```

## Install command by manager

| Detected manager | Install command                                        |
| ---------------- | ------------------------------------------------------ |
| uv               | `uv pip install 'markitdown[all]' trafilatura`         |
| venv / pip       | `python -m pip install 'markitdown[all]' trafilatura`  |
| conda            | `python -m pip install 'markitdown[all]' trafilatura`  |
| poetry           | `poetry add 'markitdown[all]' trafilatura`             |
| pipenv           | `pipenv install 'markitdown[all]' trafilatura`         |
| global           | do not install; create a venv first                    |

`uv pip install` and `python -m pip install` target the active environment
without touching a project's `pyproject.toml` or lockfile, which is correct for
a skill runtime dependency. `poetry add` / `pipenv install` record the package
as a project dependency; use them only if you want that.

## Selective installs (smaller footprint)

`markitdown[all]` pulls every format. Install only what you need, prefixed with
the manager's install verb from the table above:

| Use case                    | Package/extra                                |
| --------------------------- | -------------------------------------------- |
| PDF only                    | `'markitdown[pdf]'`                           |
| Office docs                 | `'markitdown[docx,pptx,xlsx]'`                |
| Audio transcription         | `'markitdown[audio-transcription]'`           |
| Azure Document Intelligence | `'markitdown[az-doc-intel]'`                  |
| URL fetching (static)       | `trafilatura`                                 |
| URL fetching (JS-rendered)  | `playwright` + `playwright install chromium`  |
| LLM image description       | `anthropic`                                   |

Example: `uv pip install 'markitdown[pdf]'`.

## Verification

```bash
python3 -c "from markitdown import MarkItDown; print('markitdown OK')"
python3 -c "import trafilatura; print('trafilatura OK')"
```

A successful base import does not guarantee optional format extras are present.
If a specific format fails at runtime, install its extra from the selective
table.