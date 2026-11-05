"""Read the repository's recorded publish and deploy commands without an agent session."""

from __future__ import annotations

from pathlib import Path

from typeguard import check_type

from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.models import RunContext, StepError
from orchestrator.core.tools import Tools
from orchestrator.flows.deploy_support import PLUGIN, arguments, command, handback


def run(context: RunContext) -> dict[str, JsonValue]:
    """Resolve the Story repository's mechanism from the matrix's stack declarations.

    Returns:
        The existing mechanism handback with its exact declared publish command.

    Raises:
        StepError: Git or the matrix query fails.

    """
    args = arguments(context, "DeployMechanismArgs")
    tree = Path(check_type(args["repoPath"], str))
    tools = Tools(context.work / "evidence")
    remote = tools.git(tree, ["remote", "get-url", "origin"], stage="deploy:mechanism").stdout.strip()
    repository = remote.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    queried = command(
        tools,
        "deploy:mechanism",
        [str(PLUGIN / "bin" / "atw-matrix"), "stacks", "--repository", repository],
    )
    stacks = check_type(queried["stacks"], list[dict[str, JsonValue]])
    commands = [json_object(json_object(row["stack"]).get("commands") or {}) for row in stacks]
    publish = {check_type(item["publish"], str).strip() for item in commands if item.get("publish")}
    if not stacks or len(publish) > 1:
        message = f"{repository}: missing stacks or conflicting publish commands in the matrix"
        msg = "no-deploy-mechanism"
        raise StepError(msg, OTHER_CAUSE, (message,))
    publishes = bool(publish)
    deploys = any(bool(item.get("deploy")) for item in commands)
    mechanism: dict[str, JsonValue] = {
        "repository": str(tree),
        "publishes": publishes,
        "publishCommand": ["/bin/sh", "-c", next(iter(publish))] if publishes else [],
        "deploys": deploys,
        "reason": f"Declared commands of {len(stacks)} stack(s) in {repository}",
    }
    return handback(context, "ask", f"{repository}: mechanism read from its stack declarations", mechanism=mechanism)
