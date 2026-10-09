"""Evidence binding consumed by architecture claims, coverage and saved-target reuse."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def view_content(path: str, heading: str = "") -> str:
    """Bind a unique section and catalog, falling back to the entire view."""
    p = Path(path)
    if not p.is_absolute():
        return "invalid: expected absolute path"
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return f"unreadable: {exc}"
    front = ""
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end >= 0:
            front = re.sub(
                r"(?m)^lifecycle_state:.*$",
                "lifecycle_state: <review-state>",
                text[:end],
            )
            text = front + text[end:]
    if heading:
        lines = text.splitlines(keepends=True)
        hits = [
            (i, len(m[1]))
            for i, line in enumerate(lines)
            if (m := re.match(r"^(#{1,6})\s+(.+?)\s*$", line)) and m[2] == heading
        ]
        if len(hits) == 1:
            start, level = hits[0]
            end = next(
                (
                    i
                    for i in range(start + 1, len(lines))
                    if (m := re.match(r"^(#{1,6})\s", lines[i])) and len(m[1]) <= level
                ),
                len(lines),
            )
            text = front + "\n" + "".join(lines[start:end])
    return digest(text)


def evidence_state(refs: object) -> tuple[list, list[str]]:
    """Bind cited source bytes; unrelated main commits do not invalidate evidence.

    The second list holds warnings about the references, never reasons to refuse them: a
    repository reference with no commit is bound to the file's content on `main`, a reference
    with an absolute path is bound as a file whatever `repo` says, and a cited file whose
    content moved on `main` is bound to the new content.
    """
    states, errors = [], []
    if not isinstance(refs, list):
        return [], ["evidenceRefs must be a list"]
    for ref in refs:
        if not isinstance(ref, dict):
            errors.append("invalid evidence reference")
            continue
        path, repo = ref.get("path", ""), ref.get("repo", "")
        if repo and path and Path(path).is_absolute():
            content = view_content(path, ref.get("heading", ""))
            states.append({"ref": ref, "content": content})
            if content.startswith(("invalid:", "unreadable:")):
                errors.append(content)
            continue
        if repo:
            try:
                revision = ref.get("revision")
                if not isinstance(revision, str) or not re.fullmatch(
                    r"[0-9a-fA-F]{7,40}", revision
                ):
                    # No commit cited: bound to the file's content on main, which a commit
                    # elsewhere on main does not move.
                    content = subprocess.run(
                        ["git", "-C", repo, "show", f"main:{path}"],
                        capture_output=True,
                        timeout=10,
                        check=True,
                    ).stdout
                    states.append(
                        {"ref": ref, "content": hashlib.sha256(content).hexdigest()}
                    )
                    continue
                commit = subprocess.run(
                    [
                        "git",
                        "-C",
                        repo,
                        "rev-parse",
                        "--verify",
                        f"{revision}^{{commit}}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                ).stdout.strip()
                content = subprocess.run(
                    ["git", "-C", repo, "show", f"main:{path}"],
                    capture_output=True,
                    timeout=10,
                    check=True,
                ).stdout
                cited = subprocess.run(
                    ["git", "-C", repo, "show", f"{commit}:{path}"],
                    capture_output=True,
                    timeout=10,
                    check=True,
                ).stdout
                state = {
                    "ref": ref,
                    "commit": commit,
                    "content": hashlib.sha256(content).hexdigest(),
                }
                if cited != content:
                    state["moved"] = True
                    errors.append(
                        f"cited source content moved on main since {commit[:12]}: {repo}:{path}"
                    )
            except (OSError, subprocess.SubprocessError) as exc:
                state = {"ref": ref, "error": str(exc)}
                errors.append(f"source unreadable: {repo}:{path}")
        elif path:
            content = view_content(path, ref.get("heading", ""))
            state = {"ref": ref, "content": content}
            if content.startswith(("invalid:", "unreadable:")):
                errors.append(content)
        elif ref.get("url") and ref.get("revision"):
            state = {"ref": ref}
        else:
            state = {"ref": ref, "error": "missing path or external version"}
            errors.append("evidence reference lacks path or external version")
        states.append(state)
    return states, errors


def view_bindings(paths: list[str], refs: list) -> dict[str, str]:
    """Scope only explicitly referenced views; unknown legacy scope remains whole-file."""
    result = {}
    for path in paths:
        sections = [
            r
            for r in refs
            if isinstance(r, dict)
            and not r.get("repo")
            and r.get("path") == path
            and r.get("heading")
        ]
        values = (
            [view_content(path, r["heading"]) for r in sections]
            if sections
            else [view_content(path)]
        )
        invalid = next(
            (v for v in values if v.startswith(("invalid:", "unreadable:"))), None
        )
        result[path] = invalid or (digest(values) if sections else values[0])
    return result


def saved_evidence_current(work: str) -> bool:
    """Consumed by composite target shortcut; no writes or agent dispatch."""
    try:
        survey = json.loads((Path(work) / "survey.json").read_text())
        if (
            not isinstance(survey, dict)
            or not survey.get("subject")
            or not isinstance(survey.get("coverage"), list)
            or not survey["coverage"]
        ):
            return False
        ledger = json.loads((Path(work) / "ledger.json").read_text())
        if ledger.get("contractVersion") != 2 or any(
            not p.get("complete") for p in ledger.get("roundPlans", [])
        ):
            return False
        if any(
            f.get("verdict") != "verified"
            and (f.get("resolution") or {}).get("verdict") != "accepted"
            for f in ledger.get("findings", [])
        ):
            return False
        if any(
            c.get("active", True) and not c.get("verdicts")
            for c in ledger.get("claims", [])
        ):
            return False
        for row in ledger.get("claims", []) + ledger.get("coverage", []):
            if row.get("active") is False:
                continue
            refs = row.get("evidenceRefs", [])
            states, errors = evidence_state(refs)
            if errors or ("evidenceState" in row and states != row["evidenceState"]):
                return False
            if (
                "viewState" in row
                and view_bindings(row.get("views", []), refs) != row["viewState"]
            ):
                return False
        return True
    except OSError, ValueError, TypeError:
        return False
