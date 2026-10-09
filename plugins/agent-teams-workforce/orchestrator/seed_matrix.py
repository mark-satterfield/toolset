"""Seed architecture intent without asserting that any code is built or deployed."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN / "scripts/portfolio"))
sys.path.insert(0, str(PLUGIN))

from archmatrix import element_id
from archstate import _catalog, _state_of

from orchestrator.core.io import write_json
from orchestrator.core.matrix import write_seed
from orchestrator.core.tools import Tools, retry_call

BUILD_FIELDS = (
    "state",
    "task",
    "story",
    "pr",
    "commit",
    "deployedCommit",
    "changedAt",
    "changedBy",
)


def command(argv: list[str], *, cwd: Path, timeout: int = 120) -> str:
    """Require successful source acquisition rather than an empty inventory."""
    result = subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
    )
    if result.returncode:
        raise RuntimeError(f"{argv!r}: exit {result.returncode}: {result.stderr}")
    return result.stdout


def repositories(inventory: dict, root: Path) -> list[dict]:
    """Use only present, nonarchived, nonmarketing entries from the steward."""
    if not isinstance(inventory.get("repos"), list):
        raise TypeError(f"invalid inventory: {inventory}")
    marketing = (root / "apps/marketing").resolve()
    selected = []
    names = set()
    for repo in inventory["repos"]:
        path = Path(repo.get("path") or "/nonexistent").resolve()
        if (
            not repo.get("path")
            or not path.is_dir()
            or repo.get("lifecycle") == "archived"
        ):
            continue
        if path.is_relative_to(marketing):
            continue
        key = element_id(repo["name"])
        if key in names:
            raise ValueError(f"duplicate repository identity: {key}")
        names.add(key)
        selected.append(repo)
    return sorted(selected, key=lambda r: element_id(r["name"]))


def discover_stacks(repo: dict) -> dict:
    """List the actual CDK application and restore its lookup cache byte for byte."""
    path = Path(repo["path"])
    if not (path / "cdk.json").is_file():
        return {"names": [], "cdk": False}
    context = path / "cdk.context.json"
    before = context.read_bytes() if context.exists() else None
    with tempfile.TemporaryDirectory(prefix="atw-matrix-cdk-") as scratch:
        argv = ["cdk", "ls", "--profile", "dev", "--output", scratch]
        try:
            result = subprocess.run(
                argv,
                check=False,
                cwd=path,
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "NO_COLOR": "1"},
            )
            evidence = {"cdk": True, "command": argv, "exit": result.returncode}
            if result.returncode:
                return {
                    **evidence,
                    "names": [],
                    "error": result.stderr.strip()
                    or f"cdk ls exited {result.returncode}",
                }
            names = sorted(
                {line.strip() for line in result.stdout.splitlines() if line.strip()}
            )
            return {**evidence, "names": names}
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "cdk": True,
                "command": argv,
                "exit": None,
                "names": [],
                "error": str(exc),
                "failure": type(exc).__name__,
            }
        finally:
            if before is None:
                context.unlink(missing_ok=True)
            else:
                context.write_bytes(before)


def discover_views(vault: str, arc42: str, cwd: Path) -> list[dict]:
    """Read vault bytes through Obsidian, then use the pipeline's catalog parser."""
    code = (
        "JSON.stringify(await Promise.all(app.vault.getFiles().filter(f=>"
        f"f.path.startsWith({json.dumps(arc42.rstrip('/') + '/')})"
        ").map(async f=>({path:f.path,text:await app.vault.read(f)}))))"
    )
    output = command(
        ["obsidian-cli", f"vault={vault}", "eval", f"code=(async()=>{code})()"], cwd=cwd
    )
    output = output.removeprefix("=> ")
    files = json.loads(output)
    if not isinstance(files, list) or not files:
        raise ValueError(
            "Obsidian returned no architecture files; confirm vault is open"
        )
    views = []
    with tempfile.TemporaryDirectory(prefix="atw-matrix-views-") as scratch:
        for item in sorted(files, key=lambda f: f["path"]):
            relative = Path(item["path"]).relative_to(arc42)
            if (
                relative.parts[0] == "02-architecture-constraints"
                or relative.suffix != ".md"
            ):
                continue
            path = Path(scratch) / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item["text"], encoding="utf-8")
            if _state_of(path) != "effective":
                continue
            catalog = _catalog(path)
            if not catalog["shows"] and not catalog["subject"]:
                continue
            lines = item["text"].splitlines()
            title = next(
                (line[2:].strip() for line in lines if line.startswith("# ")),
                relative.stem,
            )
            repository = None
            if lines and lines[0] == "---":
                for line in lines[1:]:
                    if line == "---":
                        break
                    if line.startswith("repository:"):
                        repository = line.partition(":")[2].strip().strip("\"'") or None
            views.append(
                {
                    **catalog,
                    "path": relative.as_posix(),
                    "title": title,
                    "repository": repository,
                }
            )
    return views


def row(
    name: str, kind: str, repository: str | None = None, stack: str | None = None
) -> dict:
    """Construct an unknown row; only build writers can provide evidence fields."""
    prefix = {
        "element": "",
        "repository": "repository:",
        "stack": f"stack:{repository}/",
    }[kind]
    return {
        "id": element_id(prefix + name),
        "name": name,
        "kind": kind,
        "repository": repository,
        "repositorySource": "seed" if repository else None,
        "stack": stack,
        "views": [],
        "expected": "",
        "contains": [],
        **dict.fromkeys(BUILD_FIELDS),
        "state": "unknown",
    }


def seed(sources: dict, previous: dict) -> dict:
    """Exact-name joins only; conflicting placements are errors, never guessed."""
    rows = {}
    repo_names = {element_id(r["name"]): r["name"] for r in sources["repositories"]}
    matches: dict[str, set[tuple[str, str | None]]] = {}
    for repo in sources["repositories"]:
        name = repo["name"]
        item = row(name, "repository", name)
        item["expected"] = repo.get("purpose") or ""
        stacks = sources["stacks"][name]
        if stacks.get("error"):
            item["stacksError"] = {
                key: value for key, value in stacks.items() if key != "names"
            }
            item["stacksError"]["command"] = [
                "cdk",
                "ls",
                "--profile",
                "dev",
                "--output",
                "<scratch dir>",
            ]
        rows[item["id"]] = item
        matches.setdefault(element_id(name), set()).add((name, None))
        for stack in stacks["names"]:
            stackrow = row(stack, "stack", name, stack)
            if stackrow["id"] in rows:
                raise ValueError(f"duplicate stack identity: {stackrow['id']}")
            rows[stackrow["id"]] = stackrow
            matches.setdefault(element_id(stack), set()).add((name, stack))
    placements: dict[str, set[str]] = {}
    for view in sources["views"]:
        for name in view["shows"] or [view["subject"]]:
            key = element_id(name)
            if key.startswith(("repository:", "stack:")):
                raise ValueError(f"element uses reserved identity prefix: {name}")
            item = rows.setdefault(key, row(name, "element"))
            item["views"].append(view["path"])
            titles = item.setdefault("_titles", set())
            titles.add(view["title"])
            if element_id(view["subject"]) == key and view.get("repository"):
                repo_key = element_id(view["repository"])
                if repo_key not in repo_names:
                    raise ValueError(
                        f"view {view['path']} names unavailable repository {repo_key}"
                    )
                placements.setdefault(key, set()).add(repo_names[repo_key])
    for key, item in rows.items():
        if item["kind"] != "element":
            continue
        item["views"] = sorted(set(item["views"]))
        item["expected"] = "; ".join(sorted(item.pop("_titles")))
        explicit = placements.get(key, set())
        if len(explicit) > 1:
            raise ValueError(
                f"conflicting repository frontmatter for {key}: {sorted(explicit)}"
            )
        candidates = matches.get(key, set())
        if explicit:
            repository = next(iter(explicit))
            candidates = {(r, s) for r, s in candidates if r == repository and s}
            candidates = candidates or {(repository, None)}
        else:
            # A repository/stack with the same name in the same repo is one placement.
            candidates = {
                (r, s)
                for r, s in candidates
                if s or not any(x == r and y for x, y in candidates)
            }
        if len(candidates) > 1:
            raise ValueError(f"ambiguous exact-name placement for {key}: {candidates}")
        if candidates:
            item["repository"], item["stack"] = next(iter(candidates))
            item["repositorySource"] = "seed"
    oldrows = previous.get("elements", {})
    for key, old in oldrows.items():
        if key not in rows:
            rows[key] = {**old, "views": []}
        else:
            rows[key].update({field: old.get(field) for field in BUILD_FIELDS})
            if old.get("repositorySource") == "build":
                if rows[key]["repository"] != old.get("repository"):
                    rows[key]["stack"] = old.get("stack")
                rows[key].update(
                    repository=old.get("repository"), repositorySource="build"
                )
    for item in rows.values():
        if item["kind"] in {"repository", "stack"}:
            item["contains"] = []
    for key, item in rows.items():
        repository = item.get("repository")
        if not repository or item["kind"] == "repository":
            continue
        repo_key = "repository:" + element_id(repository)
        if repo_key in rows:
            rows[repo_key]["contains"].append(key)
        if item["kind"] == "element" and item.get("stack"):
            stack_key = element_id(f"stack:{repository}/{item['stack']}")
            if stack_key in rows:
                rows[stack_key]["contains"].append(key)
    for item in rows.values():
        item["contains"] = sorted(set(item["contains"]))
    return {
        "version": 1,
        "seededAt": previous.get("seededAt") or sources["acquiredAt"],
        "elements": rows,
    }


def publish(path: Path, root: Path) -> None:
    """Publish only the matrix while its write lock is held."""
    relative = str(path.relative_to(root))
    tools = Tools(root / "ops/sdlc-automation/state/matrix-evidence")
    tools.git(root, ["add", "--", relative], stage="matrix")
    changed = tools.command(
        ["git", "diff", "--cached", "--quiet", "--", relative],
        cwd=root,
        stage="matrix",
        check=False,
    )
    if changed.exit == 1:
        tools.git(
            root,
            [
                "commit",
                "--only",
                relative,
                "-m",
                "feat(orchestrator): seed the element status matrix",
                "-m",
                "rewrite-step: S05a\n\nPipeline-Run: seed-matrix",
            ],
            stage="matrix",
        )
    elif changed.exit:
        raise tools.failure("matrix", "other", vars(changed))
    tools.git(root, ["push", "origin", "main"], stage="matrix")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=os.environ.get("SKILLSPOKE_ROOT"),
        required=not os.environ.get("SKILLSPOKE_ROOT"),
    )
    parser.add_argument(
        "--control",
        type=Path,
        default=os.environ.get("ATW_CONTROL_REPO"),
        required=not os.environ.get("ATW_CONTROL_REPO"),
    )
    parser.add_argument("--vault", default="skillspoke-docs")
    parser.add_argument("--arc42", default="docs/tech/architecture/arc42")
    parser.add_argument(
        "--output", type=Path, default=os.environ.get("ATW_ELEMENT_MATRIX")
    )
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Leave the seed for independent review before publishing",
    )
    args = parser.parse_args()
    os.environ["SKILLSPOKE_APPS"] = str(args.root / "apps")
    inventory = json.loads(
        command(
            [
                "uv",
                "run",
                str(PLUGIN / "skills/polyrepo-repo/scripts/polyrepo.py"),
                "inventory",
                "--json",
                "--no-fetch",
            ],
            cwd=args.control,
        )
    )
    repos = repositories(inventory, args.root)
    sources = {
        "acquiredAt": datetime.now(UTC).isoformat(),
        "repositories": repos,
        "views": discover_views(args.vault, args.arc42, args.control),
        "stacks": {},
    }
    for repo in repos:
        sources["stacks"][repo["name"]] = discover_stacks(repo)
        print(f"discovered {repo['name']}", file=sys.stderr, flush=True)
    write_json(args.source_report, sources)
    output = args.output or args.control / "ops/sdlc-automation/element-matrix.json"
    result = retry_call(
        lambda: write_seed(
            output,
            args.control,
            lambda old: seed(sources, old),
            None if args.no_publish else lambda: publish(output, args.control),
        )
    )
    print(json.dumps({"rows": len(result["elements"]), "output": str(output)}))


if __name__ == "__main__":
    main()
