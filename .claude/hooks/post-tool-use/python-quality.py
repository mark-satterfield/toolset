"""Return Python quality findings to the session immediately after an edit."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed checker argv lists, without shell execution.
import sys
from pathlib import Path

from typeguard import CollectionCheckStrategy, typechecked


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def edited_path(raw: str) -> Path | None:
    """Validate hook input and return the edited Python path.

    Returns:
        The edited Python path, or None for other file types.

    Raises:
        TypeError: The hook envelope does not contain the expected fields.

    """
    event: object = json.loads(raw)
    if not isinstance(event, dict) or not isinstance(event.get("tool_input"), dict):
        message = "hook.tool_input: expected object"
        raise TypeError(message)
    value: object = event["tool_input"].get("file_path")
    if not isinstance(value, str):
        message = "hook.tool_input.file_path: expected string"
        raise TypeError(message)
    path = Path(value)
    if not path.is_absolute():
        cwd: object = event.get("cwd")
        if not isinstance(cwd, str):
            message = "hook.cwd: expected string for relative file_path"
            raise TypeError(message)
        path = Path(cwd) / path
    return path.resolve() if path.suffix == ".py" else None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> int:
    """Run all three checkers and report their findings to the editing agent.

    Returns:
        Two when a checker or hook fails; zero otherwise.

    """
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        path = edited_path(sys.stdin.read())
    except (ValueError, TypeError, OSError) as exc:
        sys.stderr.write(f"Python quality hook input: {exc}\n")
        return 2
    if path is None:
        return 0
    uvx = shutil.which("uvx")
    if uvx is None:
        sys.stderr.write("Python quality hook: uvx executable is missing\n")
        return 2
    failed = False
    for arguments in (("ruff", "check"), ("ruff", "format", "--check"), ("mypy", "--strict")):
        try:
            result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Fixed uvx argv; no shell.
                [
                    uvx,
                    "--with",
                    "typeguard",
                    "--with",
                    "types-PyYAML",
                    "--with",
                    "types-jsonschema",
                    "--with",
                    "boto3-stubs[cognito-idp,ssm]",
                    "--with",
                    "chromadb==1.5.2",
                    "--with",
                    "ollama==0.6.1",
                    *arguments,
                    str(path),
                ],
                cwd=path.parent,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            failed = True
            sys.stderr.write(f"Python quality hook {arguments[0]}: {exc}\n")
            continue
        if result.returncode:
            failed = True
            sys.stderr.write(f"Python quality check {' '.join(arguments)} for {path}:\n")
            sys.stderr.write(result.stdout)
            sys.stderr.write(result.stderr)
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
