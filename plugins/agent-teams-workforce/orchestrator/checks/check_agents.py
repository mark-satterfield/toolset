"""Three bounded checks using a fake Claude executable, never a live agent."""

from __future__ import annotations

import argparse
import io
import json
import os
import shlex
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import TypedDict
from unittest.mock import patch

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orchestrator.checks.check_support import report, require
from orchestrator.core.agent_context import driver_module
from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.events import EventWriter
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.models import AgentStep, RunContext, StepError


class Brief(TypedDict):
    """Facts passed to the fake executable."""

    bead: str
    inputs: list[dict[str, str]]
    output: str
    outcome: str


class Capture(TypedDict):
    """Session evidence copied before temporary session cleanup."""

    argv: list[str]
    brief: Brief
    cwd: str
    agents: dict[str, dict[str, JsonValue]]
    settings: dict[str, JsonValue]
    feedback: list[dict[str, JsonValue]]


RESET_AT = 2_000_000_000
CORRECTION_ATTEMPTS = 2


FAKE = """
import json, os, sys, time
from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked
if "--version" in sys.argv:
    print("2.1.296 (Claude Code)")
    sys.exit(0)
args = sys.argv[1:]
brief = json.loads(sys.stdin.read())
record = {"argv": args, "brief": brief, "cwd": os.getcwd(),
          "agents": json.loads(Path(args[args.index("--agents") + 1]).read_text()),
          "settings": json.loads(Path(args[args.index("--settings") + 1]).read_text())}
record["feedback"] = [
    json.loads(Path(item["path"]).read_text()) for item in brief["inputs"]
    if item["label"] == "validation errors"
]
with open(os.environ["FAKE_CAPTURE"], "a") as handle:
    handle.write(json.dumps(record) + "\\n")
mode = os.environ["FAKE_MODE"]
if mode == "hang":
    time.sleep(10)
elif mode == "fable" and "--resume" not in args:
    print(json.dumps({"type": "rate_limit_event", "rate_limit_info": {
        "status": "rejected", "rateLimitType": "seven_day_overage_included",
        "overageDisabledReason": "out_of_credits", "resetsAt": 2000000000}}), flush=True)
elif mode == "quota":
    print(json.dumps({"type": "rate_limit_event", "rate_limit_info": {
        "status": "rejected", "rateLimitType": "five_hour", "resetsAt": 2000000000}}), flush=True)
else:
    output = Path(brief["output"])
    if mode == "success" or (mode in ("missing", "fable") and "--resume" in args):
        output.write_text('{"accepted": true}')
print(json.dumps({"type": "result", "subtype": "success", "is_error": False}), flush=True)
"""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def records(root: Path) -> list[Capture]:
    """Evaluate the existing isolated check contract.

    Returns:
        The captured session facts or typed fixture.

    """
    path = root / "capture.jsonl"
    return (
        [
            check_type(json.loads(line), Capture, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
            for line in path.read_text().splitlines()
        ]
        if path.exists()
        else []
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def fixture(root: Path, module: ModuleType) -> tuple[AgentRunner, AgentStep, io.StringIO]:
    """Evaluate the existing isolated check contract.

    Returns:
        The captured session facts or typed fixture.

    """
    plugin, config = root / "plugin", root / "config"
    (plugin / "agents").mkdir(parents=True)
    config.mkdir()
    (plugin / "agents" / "sample.md").write_text(
        "---\ndescription: Sample\ntools: Read, Write\ndisallowedTools: Agent\n"
        "skills: [agent-teams-workforce:subagent-contract]\nmodel: fable\n"
        "isolation: worktree\n---\nWrite the supplied artifact.\n",
    )
    (config / "settings.json").write_text(
        json.dumps(
            {
                "model": "irrelevant",
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": "inject-context"}]},
                    ],
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "/hooks/pipeline-run-blocker.sh",
                                },
                                {"type": "command", "command": "/hooks/irrelevant.sh"},
                            ],
                        },
                    ],
                },
            },
        ),
    )
    fake = root / "claude"
    fake.write_text(f"#!{sys.executable}\n" + FAKE)
    fake.chmod(0o755)
    source, schema = root / "source.md", root / "schema.json"
    source.write_text("input facts")
    schema.write_text(
        json.dumps(
            {
                "type": "object",
                "required": ["accepted"],
                "properties": {"accepted": {"const": True}},
            },
        ),
    )
    work = root / "work"
    work.mkdir()
    context = RunContext(
        "epic",
        "prd-to-spec",
        {},
        work,
        "fake-run",
        stage="architecture",
    )
    store = ArtifactStore(module, root, work, "epic", "fake-run")
    stream = io.StringIO()
    runner = AgentRunner(context, store, plugin=plugin, emit=EventWriter(stream))
    step = AgentStep(
        "survey",
        "sample",
        (str(source),),
        work / "candidate.json",
        "Write the survey.",
        schema,
        work / "result.json",
        "sonnet",
        "medium",
        (root,),
    )
    return runner, step, stream


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def check_command(
    runner: AgentRunner,
    step: AgentStep,
    root: Path,
    stream: io.StringIO,
) -> None:
    """Evaluate the existing isolated check contract."""
    os.environ["FAKE_MODE"] = "success"
    require(runner.run(step) == step.final, "runner.run(step) == step.final")
    row = records(root)[0]
    args = row["argv"]
    require(
        args[:4] == ["-p", "--output-format", "stream-json", "--verbose"],
        "args[:4] == ['-p', '--output-format', 'stream-json', '--verbose']",
    )
    require(
        args[args.index("--setting-sources") + 1] == "project",
        "args[args.index('--setting-sources') + 1] == 'project'",
    )
    require("--strict-mcp-config" in args, "'--strict-mcp-config' in args")
    require("--mcp-config" not in args, "'--mcp-config' not in args")
    require("--json-schema" not in args, "'--json-schema' not in args")
    require("--worktree" not in args, "'--worktree' not in args")
    require(
        args[args.index("--permission-mode") + 1] == "bypassPermissions",
        "args[args.index('--permission-mode') + 1] == 'bypassPermissions'",
    )
    require("Agent" in args, "'Agent' in args")
    require("AskUserQuestion" in args, "'AskUserQuestion' in args")
    agent = row["agents"]["atw-sample"]
    require("isolation" not in agent, "'isolation' not in agent")
    require(agent["model"] == "sonnet", "agent['model'] == 'sonnet'")
    require(
        agent["skills"] == ["agent-teams-workforce:subagent-contract"],
        "agent['skills'] == ['agent-teams-workforce:subagent-contract']",
    )
    hooks = json_object(row["settings"]["hooks"])
    before = check_type(
        hooks["PreToolUse"],
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    require(
        before == [{"matcher": "Bash", "hooks": [{"type": "command", "command": "/hooks/pipeline-run-blocker.sh"}]}],
        "required Bash guard changed",
    )
    after = check_type(
        hooks["PostToolUse"],
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    quality = check_type(
        after[0]["hooks"],
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )[0]
    command = shlex.split(check_type(quality["command"], str))
    require(after[0]["matcher"] == "Write|Edit", "quality hook matcher changed")
    require(
        command == [sys.executable, str(runner.plugin.resolve() / "orchestrator/hooks/python-quality.py")],
        "quality hook path must be absolute",
    )

    require(
        set(row["brief"]) == {"bead", "inputs", "output", "outcome"},
        "set(row['brief']) == {'bead', 'inputs', 'output', 'outcome'}",
    )
    require(
        row["brief"]["inputs"] == [{"label": "source", "path": str(root / "source.md")}],
        "row['brief']['inputs'] == [{'label': 'source', 'path': str(root / 'source.md')}]",
    )
    require(
        Path(row["cwd"]).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()),
        "Path(row['cwd']).is_relative_to(Path(tempfile.gettempdir()))",
    )
    require(not Path(row["cwd"]).exists(), "completed session directory was not removed")
    require(len(runner.context.sessions) == 1, "len(runner.context.sessions) == 1")
    require(runner.run(step) == step.final, "runner.run(step) == step.final")
    require(len(records(root)) == 1, "len(records(root)) == 1")
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    require(
        [e["state"] for e in events if e["event"] == "session"] == ["started", "ended"],
        "[e['state'] for e in events if e['event'] == 'session'] == ['started', 'ended']",
    )
    report("PASS: designed command/context/brief; accepted file reused without a session")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def check_corrective(runner: AgentRunner, step: AgentStep, root: Path) -> None:
    """Evaluate the existing isolated check contract.

    Raises:
        AssertionError: A failed session was incorrectly accepted.

    """
    os.environ["FAKE_MODE"] = "missing"
    step = replace(
        step,
        stage="missing",
        output=root / "missing.json",
        final=root / "fixed.json",
    )
    require(runner.run(step) == step.final, "runner.run(step) == step.final")
    first, second = records(root)[-2:]
    require("--resume" in second["argv"], "'--resume' in second['argv']")
    require(
        second["argv"][second["argv"].index("--resume") + 1] == first["argv"][first["argv"].index("--session-id") + 1],
        "correction did not resume the same session",
    )
    feedback = second["brief"]["inputs"][-1]
    require(feedback["label"] == "validation errors", "feedback['label'] == 'validation errors'")
    require(
        second["feedback"][-1]["output"] == str(step.output),
        "second['feedback'][-1]['output'] == str(step.output)",
    )
    require(
        second["brief"]["outcome"] == "Correct the output named in the errors file.",
        "second['brief']['outcome'] == 'Correct the output named in the errors file.'",
    )
    os.environ["FAKE_MODE"] = "never"
    step = replace(
        step,
        stage="never",
        output=root / "never.json",
        final=root / "not-accepted.json",
    )
    before = len(records(root))
    try:
        runner.run(step)
    except StepError as exc:
        require(exc.cause == "other", "exc.cause == 'other'")
    else:
        message = "missing output was accepted"
        raise AssertionError(message)
    require(len(records(root)) == before + CORRECTION_ATTEMPTS, "len(records(root)) == before + CORRECTION_ATTEMPTS")
    require(not check_type(step.final, Path).exists(), "not check_type(step.final, Path).exists()")
    report("PASS: missing output resumes same UUID with exact errors; correction stops after one retry")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def check_quota(runner: AgentRunner, step: AgentStep, root: Path) -> None:
    """Evaluate the existing isolated check contract.

    Raises:
        AssertionError: A failed session was incorrectly accepted.

    """
    os.environ["FAKE_MODE"] = "quota"
    step = replace(
        step,
        stage="quota",
        output=root / "quota.json",
        final=root / "quota-final.json",
    )
    before = len(records(root))
    try:
        runner.run(step)
    except StepError as exc:
        require(exc.cause == "quota", "exc.cause == 'quota'")
        require(exc.resume_at == RESET_AT, "exc.resume_at == RESET_AT")
    else:
        message = "quota was accepted"
        raise AssertionError(message)
    require(len(records(root)) == before + 1, "len(records(root)) == before + 1")
    require(not check_type(step.final, Path).exists(), "not check_type(step.final, Path).exists()")
    report("PASS: structured usage wall raises quota with resume time, without retry")
    fresh = AgentRunner(
        runner.context,
        runner.store,
        plugin=runner.plugin,
        emit=runner.emit,
    )
    step = replace(
        step,
        stage="fable",
        model="fable",
        output=root / "fable.json",
        final=root / "fable-final.json",
    )
    os.environ["FAKE_MODE"] = "fable"
    require(fresh.run(step) == step.final, "fresh.run(step) == step.final")
    first, second = records(root)[-2:]
    require(first["agents"]["atw-sample"]["model"] == "fable", "first['agents']['atw-sample']['model'] == 'fable'")
    require(second["agents"]["atw-sample"]["model"] == "opus", "second['agents']['atw-sample']['model'] == 'opus'")
    require("--resume" in second["argv"], "'--resume' in second['argv']")
    require(fresh.context.sessions[-1]["model"] == "opus", "fresh.context.sessions[-1]['model'] == 'opus'")
    os.environ["FAKE_MODE"] = "hang"
    with patch.dict(os.environ, {"ATW_SESSION_IDLE": "0.1"}):
        step = replace(
            step,
            stage="idle",
            output=root / "idle.json",
            final=root / "idle-final.json",
        )
        try:
            fresh.run(step)
        except StepError as exc:
            require(exc.cause == "other", "exc.cause == 'other'")
        else:
            message = "idle session was accepted"
            raise AssertionError(message)
    report("PASS: allowance fallback resumes on Opus; idle child is killed with cause other")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Evaluate the existing isolated check contract."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-script", required=True, type=Path)
    options = parser.parse_args()
    module = load_artifactio(options.artifact_script)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        values = {
            "PATH": str(root) + os.pathsep + os.environ["PATH"],
            "CLAUDE_CONFIG_DIR": str(root / "config"),
            "ATW_CONTROL_REPO": str(options.artifact_script.resolve().parents[2]),
            "FAKE_CAPTURE": str(root / "capture.jsonl"),
            "ATW_SESSION_IDLE": "5",
            "ATW_SESSION_LIMIT": "10",
        }
        with patch.dict(os.environ, values):
            headless = driver_module("headlessenv")
            with patch.object(
                headless,
                "child_env",
                side_effect=lambda _scratch: dict(os.environ),
            ):
                runner, step, stream = fixture(root, module)
                check_command(runner, step, root, stream)
                check_corrective(runner, step, root)
                check_quota(runner, step, root)


if __name__ == "__main__":
    main()
