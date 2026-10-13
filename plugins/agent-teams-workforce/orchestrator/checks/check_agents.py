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
from typing import TypedDict
from unittest.mock import patch

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/pipeline-contracts/scripts"))

from driver_surface_types import (
    ACCOUNT_WINDOWS,
    CONTROL_REPO_ENV,
    DRIVER_MODULES,
    HEADLESSENV_MODULE,
    MODEL_OVERAGE_TYPE,
    OUT_OF_CREDITS_REASON,
    RATE_LIMIT_EVENT_TYPE,
    RATE_LIMIT_INFO_KEY,
    REJECTED_STATUS,
    HeadlessEnvironment,
    RateLimitEvent,
    RateLimitInfo,
)
from orchestrator.checks.check_support import report, require
from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifact_contract import ArtifactProducer
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.driver_contracts import dispatch_arguments, driver_module
from orchestrator.core.events import EventWriter
from orchestrator.core.handback_contract import (
    EVENT_KEY,
    OTHER_CAUSE,
    PRD_TO_SPEC_PHASES,
    QUOTA_CAUSE,
    SESSION_ENDED,
    SESSION_EVENT,
    SESSION_STARTED,
    OrchestratorEvent,
    SessionState,
    validate_event,
)
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
SKILL_MARKER = "The fixture skill sentence."


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def write_agent(plugin: Path, model: str) -> None:
    """Write the fixture agent definition with the model its session runs on."""
    (plugin / "agents" / "sample.md").write_text(
        "---\ndescription: Sample\ntools: Read, Write\ndisallowedTools: Agent\n"
        f"skills: [agent-teams-workforce:subagent-contract]\nmodel: {model}\neffort: medium\n"
        "isolation: worktree\n---\nWrite the supplied artifact.\n",
    )


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
    print(os.environ["FAKE_FABLE_EVENT"], flush=True)
elif mode == "quota":
    print(os.environ["FAKE_QUOTA_EVENT"], flush=True)
else:
    output = Path(brief["output"])
    if mode == "success" or (mode in ("missing", "fable") and "--resume" in args):
        output.write_text('{"accepted": true}')
print(json.dumps({"type": "result", "subtype": "success", "is_error": False}), flush=True)
"""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def rate_limit_line(info: RateLimitInfo) -> str:
    """Build one stream-json rate-limit event line from the driver-surface contract.

    Returns:
        The serialized event the fake executable prints.

    """
    event: RateLimitEvent = check_type(
        {"type": RATE_LIMIT_EVENT_TYPE, RATE_LIMIT_INFO_KEY: info},
        RateLimitEvent,
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    return json.dumps(event)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def fable_line() -> str:
    """Build the model-specific out-of-credits refusal the fake prints before a resume.

    Returns:
        The serialized rate-limit event.

    """
    return rate_limit_line(
        RateLimitInfo(
            status=REJECTED_STATUS,
            rateLimitType=MODEL_OVERAGE_TYPE,
            overageDisabledReason=OUT_OF_CREDITS_REASON,
            resetsAt=RESET_AT,
        ),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def quota_line() -> str:
    """Build the account-window rejection the fake prints in quota mode.

    Returns:
        The serialized rate-limit event.

    """
    window: str = min(ACCOUNT_WINDOWS)
    return rate_limit_line(RateLimitInfo(status=REJECTED_STATUS, rateLimitType=window, resetsAt=RESET_AT))


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
def fixture(root: Path, module: ArtifactProducer) -> tuple[AgentRunner, AgentStep, io.StringIO]:
    """Evaluate the existing isolated check contract.

    Returns:
        The captured session facts or typed fixture.

    """
    plugin, config = root / "plugin", root / "config"
    (plugin / "agents").mkdir(parents=True)
    config.mkdir()
    write_agent(plugin, "sonnet")
    skill = plugin / "skills" / "subagent-contract"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: subagent-contract\ndescription: Fixture.\n---\n{SKILL_MARKER}\n")
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
        dispatch_arguments().FLOW_PRD_TO_SPEC,
        {},
        work,
        "fake-run",
        stage=PRD_TO_SPEC_PHASES[0],
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
    require(agent["effort"] == "medium", "agent['effort'] == 'medium'")
    require("skills" not in agent, "the launched agent must not carry a skills list Claude Code never preloads")
    prompt = check_type(agent["prompt"], str)
    require(prompt.count(SKILL_MARKER) == 1, "the launched agent's prompt must hold its skill text once")
    require(
        f"Base directory for this skill: {(runner.plugin / 'skills' / 'subagent-contract').resolve()}" in prompt,
        "the skill text must name the skill's base directory",
    )
    require("env" not in row["settings"], "a session that starts no agent sets no nesting environment")
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
    states: list[SessionState] = []
    for line in stream.getvalue().splitlines():
        event: OrchestratorEvent = validate_event(json.loads(line))
        if event[EVENT_KEY] == SESSION_EVENT:
            states.append(event["state"])
    require(states == [SESSION_STARTED, SESSION_ENDED], "session events are not started then ended")
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
        require(exc.cause == OTHER_CAUSE, "missing output must fail with the other cause")
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
        require(exc.cause == QUOTA_CAUSE, "a usage wall must fail with the quota cause")
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
        output=root / "fable.json",
        final=root / "fable-final.json",
    )
    write_agent(fresh.plugin, "fable")
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
            require(exc.cause == OTHER_CAUSE, "an idle session must fail with the other cause")
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
            CONTROL_REPO_ENV: str(options.artifact_script.resolve().parents[2]),
            "FAKE_CAPTURE": str(root / "capture.jsonl"),
            "FAKE_FABLE_EVENT": fable_line(),
            "FAKE_QUOTA_EVENT": quota_line(),
            "ATW_SESSION_IDLE": "5",
            "ATW_SESSION_LIMIT": "10",
        }
        child_env: str = HeadlessEnvironment.child_env.__name__
        require(child_env in DRIVER_MODULES[HEADLESSENV_MODULE], "child_env is not in the headlessenv driver surface")
        with patch.dict(os.environ, values):
            headless = driver_module(HEADLESSENV_MODULE)
            with patch.object(
                headless,
                child_env,
                side_effect=lambda _scratch: dict(os.environ),
            ):
                runner, step, stream = fixture(root, module)
                check_command(runner, step, root, stream)
                check_corrective(runner, step, root)
                check_quota(runner, step, root)


if __name__ == "__main__":
    main()
