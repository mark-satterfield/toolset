"""Three bounded checks using a fake Claude executable, never a live agent."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orchestrator.core.agent_context import driver_module
from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.events import EventWriter
from orchestrator.core.models import AgentStep, RunContext, StepError

FAKE = """
import json, os, sys, time
from pathlib import Path
if "--version" in sys.argv:
    print("2.1.296 (Claude Code)")
    sys.exit(0)
args = sys.argv[1:]
brief = json.loads(sys.stdin.read())
record = {"argv": args, "brief": brief, "cwd": os.getcwd(),
          "agents": json.loads(Path(args[args.index("--agents") + 1]).read_text()),
          "settings": json.loads(Path(args[args.index("--settings") + 1]).read_text())}
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


def records(root: Path) -> list[dict]:
    path = root / "capture.jsonl"
    return (
        [json.loads(line) for line in path.read_text().splitlines()]
        if path.exists()
        else []
    )


def fixture(root: Path, module: object) -> tuple[AgentRunner, AgentStep, io.StringIO]:
    plugin, config = root / "plugin", root / "config"
    (plugin / "agents").mkdir(parents=True)
    config.mkdir()
    (plugin / "agents" / "sample.md").write_text(
        "---\ndescription: Sample\ntools: Read, Write\ndisallowedTools: Agent\n"
        "skills: [agent-teams-workforce:subagent-contract]\nmodel: fable\n"
        "isolation: worktree\n---\nWrite the supplied artifact.\n"
    )
    (config / "settings.json").write_text(
        json.dumps(
            {
                "model": "irrelevant",
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": "inject-context"}]}
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
                        }
                    ],
                },
            }
        )
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
            }
        )
    )
    work = root / "work"
    work.mkdir()
    context = RunContext(
        "epic", "prd-to-spec", {}, work, "fake-run", stage="architecture"
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


def check_command(
    runner: AgentRunner, step: AgentStep, root: Path, stream: io.StringIO
) -> None:
    os.environ["FAKE_MODE"] = "success"
    assert runner.run(step) == step.final
    row = records(root)[0]
    args = row["argv"]
    assert args[:4] == ["-p", "--output-format", "stream-json", "--verbose"]
    assert args[args.index("--setting-sources") + 1] == "project"
    assert "--strict-mcp-config" in args and "--mcp-config" not in args
    assert "--json-schema" not in args and "--worktree" not in args
    assert args[args.index("--permission-mode") + 1] == "bypassPermissions"
    assert "Agent" in args and "AskUserQuestion" in args
    agent = row["agents"]["atw-sample"]
    assert "isolation" not in agent and agent["model"] == "sonnet"
    assert agent["skills"] == ["agent-teams-workforce:subagent-contract"]
    assert row["settings"] == {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": "/hooks/pipeline-run-blocker.sh"}
                    ],
                }
            ]
        }
    }
    assert set(row["brief"]) == {"bead", "inputs", "output", "outcome"}
    assert row["brief"]["inputs"] == [
        {"label": "source", "path": str(root / "source.md")}
    ]
    assert Path(row["cwd"]).is_relative_to(root / "sessions")
    assert len(runner.context.sessions) == 1
    assert runner.run(step) == step.final and len(records(root)) == 1
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert [e["state"] for e in events if e["event"] == "session"] == [
        "started",
        "ended",
    ]
    print(
        "PASS: designed command/context/brief; accepted file reused without a session"
    )


def check_corrective(runner: AgentRunner, step: AgentStep, root: Path) -> None:
    os.environ["FAKE_MODE"] = "missing"
    step = replace(
        step, stage="missing", output=root / "missing.json", final=root / "fixed.json"
    )
    assert runner.run(step) == step.final
    first, second = records(root)[-2:]
    assert "--resume" in second["argv"]
    assert (
        second["argv"][second["argv"].index("--resume") + 1]
        == first["argv"][first["argv"].index("--session-id") + 1]
    )
    feedback = second["brief"]["inputs"][-1]
    assert feedback["label"] == "validation errors"
    assert json.loads(Path(feedback["path"]).read_text())["output"] == str(step.output)
    assert second["brief"]["outcome"] == "Correct the output named in the errors file."
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
        assert exc.cause == "other"
    else:
        raise AssertionError("missing output was accepted")
    assert len(records(root)) == before + 2
    assert not step.final.exists()
    print(
        "PASS: missing output resumes same UUID with exact errors; correction stops after one retry"
    )


def check_quota(runner: AgentRunner, step: AgentStep, root: Path) -> None:
    os.environ["FAKE_MODE"] = "quota"
    step = replace(
        step, stage="quota", output=root / "quota.json", final=root / "quota-final.json"
    )
    before = len(records(root))
    try:
        runner.run(step)
    except StepError as exc:
        assert exc.cause == "quota" and exc.resume_at == 2000000000
    else:
        raise AssertionError("quota was accepted")
    assert len(records(root)) == before + 1 and not step.final.exists()
    print("PASS: structured usage wall raises quota with resume time, without retry")
    fresh = AgentRunner(
        runner.context, runner.store, plugin=runner.plugin, emit=runner.emit
    )
    step = replace(
        step,
        stage="fable",
        model="fable",
        output=root / "fable.json",
        final=root / "fable-final.json",
    )
    os.environ["FAKE_MODE"] = "fable"
    assert fresh.run(step) == step.final
    first, second = records(root)[-2:]
    assert first["agents"]["atw-sample"]["model"] == "fable"
    assert second["agents"]["atw-sample"]["model"] == "opus"
    assert "--resume" in second["argv"]
    assert fresh.context.sessions[-1]["model"] == "opus"
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
            assert exc.cause == "other"
        else:
            raise AssertionError("idle session was accepted")
    print(
        "PASS: allowance fallback resumes on Opus; idle child is killed with cause other"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-script", required=True, type=Path)
    options = parser.parse_args()
    module = load_artifactio(options.artifact_script)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        values = {
            "PATH": str(root) + os.pathsep + os.environ["PATH"],
            "CLAUDE_CONFIG_DIR": str(root / "config"),
            "ATW_SESSION_ROOT": str(root / "sessions"),
            "ATW_CONTROL_REPO": str(options.artifact_script.resolve().parents[2]),
            "FAKE_CAPTURE": str(root / "capture.jsonl"),
            "ATW_SESSION_IDLE": "5",
            "ATW_SESSION_LIMIT": "10",
        }
        with patch.dict(os.environ, values):
            headless = driver_module("headlessenv")
            with patch.object(
                headless, "child_env", side_effect=lambda _scratch: dict(os.environ)
            ):
                runner, step, stream = fixture(root, module)
                check_command(runner, step, root, stream)
                check_corrective(runner, step, root)
                check_quota(runner, step, root)


if __name__ == "__main__":
    main()
