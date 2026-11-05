"""Owner-invoked portfolio judgments with direct Python commands and no command-relay agents."""

from __future__ import annotations

import argparse
import json
import sys
from functools import partial
from pathlib import Path
from typing import Final
from uuid import uuid4

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import strictschema
from typeguard import check_type

from orchestrator.core.agents import AgentRunner
from orchestrator.core.handback_contract import ACCOUNT_CAUSES, OTHER_CAUSE, SHUTDOWN_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import AgentStep, RunContext, StepError
from orchestrator.core.tools import Tools
from orchestrator.flows.elaboration_support import parallel

PLUGIN: Final = Path(__file__).resolve().parent.parent
DEPSCORE: Final = PLUGIN / "scripts" / "portfolio" / "depscore.py"
SCHEMAS: Final = PLUGIN / "skills" / "artifact-handoff" / "schemas"


def _command(context: RunContext, tools: Tools, arguments: list[str]) -> dict[str, JsonValue]:
    """Run one existing depscore operation directly and retain its factual result.

    Returns:
        The checked command result.

    """
    repository: str = check_type(context.args["repoPath"], str)
    result = tools.command(
        [sys.executable, str(DEPSCORE), arguments[0], "-C", repository, *arguments[1:]],
        stage=arguments[0],
    )
    return json_object(json.loads(result.stdout))


def _judge(
    context: RunContext,
    runner: AgentRunner,
    agent: str,
    files: tuple[Path, Path, str],
    request: str,
) -> Path:
    """Start one genuine judgment session against the shared source contract.

    Returns:
        Its schema-validated judgment file.

    """
    source, output, contract = files
    schema: Path = context.work / "contracts" / f"{output.parent.name}-{output.stem}.schema.json"
    write_json(schema, {"$ref": str(SCHEMAS / contract)})
    step: AgentStep = AgentStep(
        stage="portfolio-judgment",
        agent=agent,
        inputs=("judge input",),
        output=output,
        outcome="portfolio judgment",
        validate=schema,
        request=request,
    )
    context.stage = "portfolio-judgment"
    return runner.run_session(step, [("judge input", source)], session=str(uuid4()))


def assess(context: RunContext, tools: Tools, runner: AgentRunner) -> dict[str, JsonValue]:
    """Assess one Epic's dependency edges while preserving the manual apply/propose behavior.

    Args:
        context: Owner command arguments and evidence directory.
        tools: Direct command boundary.
        runner: Genuine reasoning-session runner.

    Returns:
        Plan, accepted edge proposal, validation and apply/diff evidence.

    """
    epic: str = check_type(context.args["epic"], str)
    plan: Path = context.work / "assess-plan.json"
    source: Path = context.work / "context.json"
    edges: Path = context.work / "edges.json"
    scope: list[str] = ["--epic", epic]
    planned = _command(context, tools, ["assess-plan", *scope, "--out", str(plan)])
    _command(context, tools, ["assess-context", *scope, "--out", str(source)])
    _judge(
        context,
        runner,
        "epic-dependency-assessor",
        (source, edges, "epic-edge-proposal.schema.json"),
        request=f"Assess the Epic-to-Epic edges touching {epic} from the supplied context and recorded item judgments",
    )
    validated = _command(context, tools, ["validate", "--edges", str(edges), *scope])
    if validated.get("ok") is not True:
        return {"ok": False, "stage": "validate", "plan": planned, "validation": validated, "edgesFile": str(edges)}
    flags: list[str] = [] if context.args.get("apply", True) is True else ["--dry-run"]
    applied = _command(
        context,
        tools,
        [
            "apply-edges",
            "--edges",
            str(edges),
            "--plan",
            str(plan),
            *scope,
            *flags,
            "--out",
            str(context.work / "apply-edges.json"),
        ],
    )
    return {"ok": True, "plan": planned, "validation": validated, "edges": applied, "edgesFile": str(edges)}


def _score_jobs(summary: dict[str, JsonValue], level: str) -> list[tuple[str, list[str]]]:
    """Name one Epic judgment or one Epic's grouped Task judgment per session.

    Returns:
        Job key and its exact item IDs.

    """
    if level == "epic":
        return [(identifier, [identifier]) for identifier in check_type(summary.get("ids", []), list[str])]
    groups = check_type(summary.get("groups", []), list[dict[str, JsonValue]])
    return [(check_type(group["key"], str), check_type(group["tasks"], list[str])) for group in groups]


def _judge_scores(
    context: RunContext,
    tools: Tools,
    runner: AgentRunner,
    plan: Path,
    level: str,
) -> tuple[list[str], int]:
    """Judge only planned jobs and keep successful files when another job fails.

    Returns:
        Failed item IDs and number of sessions attempted.

    """
    source: Path = context.work / f"judge-input-{level}.json"
    given = _command(context, tools, ["judge-input", "--plan", str(plan), "--level", level, "--out", str(source)])
    summary: dict[str, JsonValue] = json_object(given.get("summary", {}))
    jobs: list[tuple[str, list[str]]] = _score_jobs(summary, level)
    outcomes: list[list[str]] = parallel(
        context,
        [partial(_score_job, context, runner, source, level, job=(key, identifiers)) for key, identifiers in jobs],
    )
    return [identifier for failed in outcomes for identifier in failed], len(jobs)


def _score_job(
    context: RunContext,
    runner: AgentRunner,
    source: Path,
    level: str,
    job: tuple[str, list[str]],
) -> list[str]:
    """Run the bounded genuine scorer session for one planned group.

    Returns:
        Item IDs left unjudged by a failed session, otherwise an empty list.

    Raises:
        StepError: The operation cannot proceed with the supplied evidence.

    """
    key, identifiers = job
    output: Path = context.work / "candidates" / level / f"{key}.json"
    scoped: Path = _scoped_input(context, source, level, key, identifiers)
    definition: str = "EpicJudgment" if level == "epic" else "TaskJudgment"
    try:
        _judge(
            context,
            runner,
            "wsjf-scorer",
            (scoped, output, f"wsjf-judgment.schema.json#/$defs/{definition}"),
            request=f"Judge exactly these {level} items from their supplied input: {', '.join(identifiers)}",
        )
        accepted: dict[str, JsonValue] = _accepted_judgment(output, identifiers)
    except StepError as failure:
        if failure.cause in ACCOUNT_CAUSES or failure.cause == SHUTDOWN_CAUSE:
            raise
        return identifiers
    write_json(
        context.work / "judgments" / level / f"{key}.json",
        accepted,
    )
    return []


def _accepted_judgment(path: Path, identifiers: list[str]) -> dict[str, JsonValue]:
    """Accept exactly one disposition per supplied item, with no cross-group judgment.

    Returns:
        The schema-validated result after exact-ID coverage validation.

    Raises:
        StepError: Item coverage is incomplete, duplicated or outside this session's group.

    """
    document: dict[str, JsonValue] = json_object(json.loads(path.read_text(encoding="utf-8")))
    scores = check_type(document["scores"], list[dict[str, JsonValue]])
    unscored = check_type(document["unscored"], list[dict[str, JsonValue]])
    named: list[str] = [check_type(item["id"], str) for item in [*scores, *unscored]]
    if len(named) != len(set(named)) or set(named) != set(identifiers):
        msg = "portfolio-judgment"
        raise StepError(
            msg,
            OTHER_CAUSE,
            (f"Judgment must name exactly once each of {identifiers}: {path}",),
        )
    return document


def _scoped_input(context: RunContext, source: Path, level: str, key: str, identifiers: list[str]) -> Path:
    """Give each scorer only its own Epic or Task group, with common reference jobs retained.

    Returns:
        A shared-schema-valid per-session input path.

    """
    document: dict[str, JsonValue] = json_object(json.loads(source.read_text(encoding="utf-8")))
    items = check_type(document["items"], list[dict[str, JsonValue]])
    document["items"] = [item for item in items if item["id"] in identifiers]
    summary: dict[str, JsonValue] = json_object(document["summary"])
    summary["items"] = len(identifiers)
    summary["toJudge"] = len(identifiers)
    if level == "epic":
        summary["ids"] = list(identifiers)
    else:
        summary["groups"] = [
            group for group in check_type(summary["groups"], list[dict[str, JsonValue]]) if group["key"] == key
        ]
    document["summary"] = summary
    output: Path = context.work / "inputs" / level / f"{key}.json"
    schema_path: Path = SCHEMAS / "wsjf-judge-input.schema.json"
    strictschema.validate(
        document,
        json_object(json.loads(schema_path.read_text(encoding="utf-8"))),
        location=schema_path,
    )
    write_json(output, document)
    return output


def score(context: RunContext, tools: Tools, runner: AgentRunner) -> dict[str, JsonValue]:
    """Preserve manual WSJF judgment and whole-portfolio scoring without model relays.

    Args:
        context: Owner command arguments and work directory.
        tools: Direct command boundary.
        runner: Genuine scorer-session runner.

    Returns:
        Planning, partial-judgment, recording and arithmetic evidence.

    """
    plan: Path = context.work / "score-plan.json"
    flags: list[str] = [
        flag for key, flag in (("all", "--all"), ("rejudge", "--rejudge")) if context.args.get(key) is True
    ]
    only: list[str] = check_type(context.args.get("only", []), list[str])
    if only:
        flags.extend(["--only", ",".join(only)])
    planned = _command(context, tools, ["score-plan", *flags, "--out", str(plan)])
    summary: dict[str, JsonValue] = json_object(planned.get("summary", {}))
    failures: list[str] = []
    sessions: dict[str, JsonValue] = {}
    for level, count_key in (("epic", "epicsToJudge"), ("task", "tasksToJudge")):
        failed, count = _judge_scores(context, tools, runner, plan, level) if summary.get(count_key) else ([], 0)
        failures.extend(failed)
        sessions[level] = {"sessions": count, "failed": list(failed)}
    dry: list[str] = ["--dry-run"] if context.args.get("dryRun") is True else []
    recorded = _command(
        context,
        tools,
        [
            "record",
            "--plan",
            str(plan),
            "--epics-dir",
            str(context.work / "judgments" / "epic"),
            "--tasks-dir",
            str(context.work / "judgments" / "task"),
            *dry,
            "--out",
            str(context.work / "record.json"),
        ],
    )
    scored = _command(context, tools, ["score", *dry, "--out", str(context.work / "score.json")])
    return {
        "ok": True,
        "plan": planned,
        "judging": sessions,
        "judgingFailed": list(failures),
        "record": recorded,
        "score": scored,
    }


def main() -> int:
    """Run an explicit owner portfolio command, never a keeper or supervisor pipeline.

    Returns:
        Zero on successful completion; one on a recorded work failure.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("dependency-assessment", "wsjf-scoring"))
    parser.add_argument("--args", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    args: dict[str, JsonValue] = json_object(json.loads(options.args.read_text(encoding="utf-8")))
    schema_path: Path = PLUGIN / "skills" / "pipeline-contracts" / "schemas" / "portfolio-command.schema.json"
    schema: dict[str, JsonValue] = json_object(json.loads(schema_path.read_text(encoding="utf-8")))
    definition: str = "DependencyArgs" if options.command == "dependency-assessment" else "ScoreArgs"
    strictschema.validate(args, {"$defs": schema["$defs"], "$ref": f"#/$defs/{definition}"}, location=schema_path)
    if Path(check_type(args["pluginRoot"], str)).resolve() != PLUGIN.resolve():
        parser.error("pluginRoot must name the plugin executing this portfolio command")
    work: Path = Path(check_type(args["workDir"], str))
    context: RunContext = RunContext(check_type(args.get("epic", ""), str), options.command, args, work, str(uuid4()))
    tools: Tools = Tools(work / "evidence")
    runner: AgentRunner = AgentRunner(context)
    try:
        result: dict[str, JsonValue] = (
            assess(context, tools, runner)
            if options.command == "dependency-assessment"
            else score(context, tools, runner)
        )
    except StepError as failure:
        result = {"ok": False, "stage": context.stage, "reason": str(failure)}
    finally:
        runner.processes.stop_all()
    write_json(options.output, result)
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
