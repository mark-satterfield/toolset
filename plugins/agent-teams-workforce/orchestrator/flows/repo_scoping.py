"""Place approved elements, then create only the repositories the steward names."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

from ..core.agents import AgentRunner, strict_json
from ..core.artifacts import ArtifactStore
from ..core.io import write_json
from ..core.matrix import read_snapshot, row_for, snapshot
from ..core.models import AgentStep, RunContext, StepError
from ..core.tools import Tools, env_path
from .repo_placement import accept_placement, app_space


def inventory(tools: Tools) -> dict:
    result = tools.polyrepo(["inventory"], stage="repo-scoping")
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or not isinstance(value.get("repos"), list):
        raise tools.failure("repo-scoping", "other", {"inventory": value})
    return value


def create_repositories(ruling: dict, tools: Tools, config: dict, work: Path) -> dict:
    created, failures = [], []
    preflight_done = False
    for missing in ruling["missingRepos"]:
        facts = {key: missing[key] for key in ("name", "template", "itemIds")}
        try:
            live = inventory(tools)
            existing = next(
                (
                    r
                    for r in live["repos"]
                    if r["name"].casefold() == missing["name"].casefold()
                    and r.get("path")
                ),
                None,
            )
            if existing:
                created.append({**facts, "repoPath": existing["path"], "existed": True})
                continue
            if not preflight_done:
                signed_in = tools.command(
                    ["gh", "auth", "status"], stage="repo-creation", check=False
                )
                owner = config["github_owner"]
                membership = None
                if signed_in.exit == 0:
                    membership = tools.command(
                        [
                            "gh",
                            "api",
                            f"user/memberships/orgs/{owner}",
                            "--jq",
                            ".state",
                        ],
                        stage="repo-creation",
                        check=False,
                    )
                if signed_in.exit:
                    need = "The GitHub CLI is not signed in on this machine; run gh auth login."
                elif membership.exit or membership.stdout.strip() != "active":
                    need = f"The signed-in GitHub account is not an active member of {owner}; sign in with an active member account or arrange organisation membership."
                else:
                    need = None
                if need:
                    failures.append({**facts, "error": need, "ownerFact": True})
                    break
                preflight_done = True
            result = tools.polyrepo(
                [
                    "create",
                    missing["name"],
                    "--space",
                    app_space(missing["name"], config),
                    "--template",
                    missing["template"],
                    "--purpose",
                    missing["purpose"],
                ],
                stage="repo-creation",
            )
            value = json.loads(result.stdout)
            path = value.get("path")
            if not path or not Path(path).is_absolute():
                raise tools.failure("repo-creation", "other", {"result": value})
            created.append({**facts, "repoPath": path, "existed": False})
        except (StepError, ValueError, OSError, KeyError) as exc:
            failures.append(
                {
                    **facts,
                    "error": list(exc.evidence)
                    if isinstance(exc, StepError)
                    else str(exc),
                    "ownerFact": False,
                }
            )
            break
    result = {"created": created, "failures": failures}
    write_json(work / "repo-creation.json", result)
    return result


def run(
    context: RunContext,
    store: ArtifactStore,
    runner: AgentRunner,
    tools: Tools,
    *,
    matrix_path: Path | None = None,
) -> dict:
    args, work = context.args, context.work
    context.stage = "repo-scoping"
    target = args.get("targetDir")
    if not target:
        raise StepError("input", "other", ("targetDir is required",))
    items_path = work / "delta-items.json"
    delta = strict_json(items_path)
    items = delta["items"]
    if not items:
        raise StepError("input", "other", ("delta-items.json has no build items",))
    arch = Path(args["archPath"]).resolve()
    prd = Path(args["prd"]["path"]).resolve()
    control = env_path("ATW_CONTROL_REPO")
    marketing = env_path("SKILLSPOKE_ROOT") / "apps/marketing"
    config_path = control / ".polyrepo/config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    matrix = matrix_path or snapshot(context, tools)
    matrix_data = read_snapshot(matrix)
    elements = sorted({" ".join(item["element"].split()).casefold() for item in items})
    rows = {name: row_for(matrix_data, name) for name in elements}
    binding = "matrix-rows:" + json.dumps(
        {"matrix": str(matrix), "elements": elements}, sort_keys=True
    )
    inputs = tuple(
        map(
            str,
            (
                prd,
                work / "architecture/decision.md",
                work / "architecture/target.json",
                items_path,
                target,
            ),
        )
    ) + (binding,)
    if args.get("deltaDir"):
        inputs += (str(args["deltaDir"]),)
    schema = runner.plugin / "skills/artifact-handoff/schemas/placement.schema.json"
    final = work / "repo-scoping.json"
    live = inventory(tools)
    warnings = []

    def validate(path: Path, *, reused: bool = False) -> dict:
        nonlocal warnings
        value, warnings = accept_placement(
            path,
            schema,
            items,
            live,
            rows,
            config,
            control,
            arch,
            marketing,
            reused=reused,
            avoid=args.get("avoidRepos", []),
        )
        return value

    ruling = None
    feedback = work / "repo-scoping.feedback.json"
    feedback_data = {"avoid": args.get("avoidRepos", [])}
    if store.reusable(inputs, (final,)) and not args.get("avoidRepos"):
        try:
            ruling = validate(final, reused=True)
        except (ValueError, OSError, jsonschema.ValidationError) as exc:
            feedback_data["errors"] = [str(exc)]
    if ruling is None:
        store.invalidate((final,))
        inventory_path = work / "repo-scoping.inventory.json"
        rows_path = work / "repo-scoping.matrix.json"
        facts_path = work / "repo-scoping.context.json"
        write_json(inventory_path, live)
        write_json(
            rows_path, {"elements": {key: rows.get(key, {}) for key in elements}}
        )
        write_json(feedback, feedback_data)
        write_json(
            facts_path,
            {
                "architectureChange": args.get("architectureChange"),
                "note": args.get("note"),
                "targetDir": target,
                "deltaDir": args.get("deltaDir"),
            },
        )
        candidate = work / "candidates/repo-scoping.json"
        store.invalidate((candidate,))
        runner.run(
            AgentStep(
                stage="repo-scoping",
                agent="polyrepo-steward",
                inputs=inputs
                + tuple(map(str, (inventory_path, rows_path, feedback, facts_path))),
                output=candidate,
                final=None,
                validate=validate,
                outcome="Repository placement ruling for the approved architecture elements.",
                model="sonnet",
                effort="high",
                add_dirs=(work, arch, prd.parent),
                corrective=not bool(feedback_data.get("errors")),
            )
        )
        ruling = validate(candidate)
        write_json(final, ruling)
        store.accept("repo-scoping", inputs, (final,))
    creation = create_repositories(ruling, tools, config, work)
    creation_path = work / "repo-creation.json"
    store.accept("repo-creation", (str(final),), (creation_path,))
    if creation["failures"]:
        if all(item["ownerFact"] for item in creation["failures"]):
            return {
                "ok": False,
                "stage": "requires-human-action",
                "requiredHumanActions": [
                    item["error"] for item in creation["failures"]
                ],
                "creationPath": str(creation_path),
            }
        raise StepError("repo-creation", "other", (str(creation_path),))
    paths = {repo["name"].casefold(): repo["repoPath"] for repo in creation["created"]}
    placements = [
        {**p, "repoPath": p["repoPath"] or paths[p["repoName"].casefold()]}
        for p in ruling["placements"]
    ]
    # Downstream consumers read the accepted ruling by path, including new repos.
    ruling["placements"] = placements
    write_json(final, ruling)
    store.accept("repo-scoping", inputs, (final,))
    store.accept("repo-creation", (str(final),), (creation_path,))
    repos = list(dict.fromkeys(p["repoPath"] for p in placements))
    return {
        "ok": True,
        "repos": repos,
        "placements": placements,
        "noCode": ruling["noCode"],
        "createdRepos": creation["created"],
        "warnings": warnings,
        "artifactPath": str(final),
        "creationPath": str(creation_path),
        "spanRationale": ruling["spanRationale"],
        "ledger": {
            "phase": "repo-scoping",
            "beadId": context.bead,
            "subject": args.get("architectureSubject", ""),
            "chosen": ["polyrepo-steward"],
            "mode": "fixed",
            "repoCount": len(repos),
            "itemCount": len(items),
            "createdRepoCount": len(creation["created"]),
            "ok": True,
        },
    }
