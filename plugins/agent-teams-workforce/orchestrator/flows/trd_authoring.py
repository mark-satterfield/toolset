"""Author one TRD, verify its architecture citations and mark the Epic."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from ..core.agents import AgentRunner, strict_json
from ..core.artifacts import ArtifactStore
from ..core.io import write_json
from ..core.models import AgentStep, RunContext, StepError
from ..core.tools import Tools, env_path


def document(path: Path, arch: Path) -> tuple[list[str], list[str]]:
    arch = arch.resolve()
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"missing or empty document: {path}")
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        raise ValueError(f"{path}: YAML frontmatter is missing")
    try:
        front = yaml.safe_load(text[4:].split("\n---", 1)[0]) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: invalid YAML frontmatter: {exc}") from exc
    if not isinstance(front, dict):
        raise ValueError(f"{path}: frontmatter must be an object")
    ids = front.get("decisionIds", [])
    if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
        raise ValueError(f"{path}: decisionIds must be a list of strings")
    unresolved = []
    for entry in ids:
        relative = entry.split("#", 1)[0]
        candidates = (
            (arch / relative).resolve(),
            (arch / "arc42" / relative).resolve(),
        )
        if (
            not relative
            or Path(relative).is_absolute()
            or not any(
                candidate.is_relative_to(arch) and candidate.is_file()
                for candidate in candidates
            )
        ):
            unresolved.append(entry)
    if unresolved:
        raise ValueError(f"unresolved decisionIds: {unresolved}")
    warnings = [] if ids else ["decisionIds is absent or empty"]
    return ids, warnings


def run(
    context: RunContext, store: ArtifactStore, runner: AgentRunner, tools: Tools
) -> dict:
    args, work = context.args, context.work
    context.stage = "trd-authoring"
    prd_value, target = args.get("prd", {}).get("path"), args.get("targetDir")
    if not prd_value or not target:
        raise StepError("input", "other", ("PRD path and targetDir are required",))
    prd, arch = Path(prd_value).resolve(), Path(args["archPath"]).resolve()
    item_path = work / "delta-items.json"
    elements = sorted({item["element"] for item in strict_json(item_path)["items"]})
    inputs = tuple(
        map(
            str,
            (
                prd,
                item_path,
                work / "architecture/decision.md",
                work / "architecture/target.json",
                work / "architecture/architecture-update.json",
                work / "architecture/survey.json",
                target,
                arch / "arc42/02-architecture-constraints",
            ),
        )
    ) + (
        "arch-views:"
        + json.dumps(
            {"dir": str(arch / "arc42"), "elements": elements}, sort_keys=True
        ),
    )
    output = work / "trd.md"
    reused = store.reusable(inputs, (output,))
    facts = work / "trd.context.json"
    feedback = work / "trd.feedback.json"
    ids, warnings, errors = [], [], []
    if reused:
        try:
            ids, warnings = document(output, arch)
        except (ValueError, OSError, UnicodeError) as exc:
            reused = False
            errors = [str(exc)]
    if not reused:
        store.invalidate((output,))
        write_json(
            facts,
            {
                "architectureChange": args.get("architectureChange"),
                "targetDir": target,
                "deltaDir": args.get("deltaDir"),
                "note": args.get("note"),
                "filingPath": args.get("trdPath"),
            },
        )
        write_json(feedback, {"errors": errors})
        runner.run(
            AgentStep(
                stage="trd",
                agent="trd-author",
                inputs=inputs + (str(facts), str(feedback)),
                output=output,
                final=None,
                validate=lambda path: document(path, arch),
                outcome="Technical requirements document with architecture citations.",
                model="fable",
                effort="medium",
                add_dirs=(work, arch, prd.parent),
                corrective=not bool(errors),
            )
        )
        ids, warnings = document(output, arch)
    store.accept("trd", inputs, (output,))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    relative = str(output.resolve().relative_to(env_path("SKILLSPOKE_ROOT")))
    control = env_path("ATW_CONTROL_REPO")

    def mark() -> None:
        raw = json.loads(tools.bd(["show", context.bead, "--json"], stage="trd"))
        bead = raw[0] if isinstance(raw, list) else raw
        metadata = bead.get("metadata") or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        pairs = {"artifact_trd_path": relative, "artifact_trd_sha256": digest}
        if all(metadata.get(key) == value for key, value in pairs.items()):
            return
        tools.portfolio(
            "beadgraph", "write_metadata", context.bead, pairs, control, stage="trd"
        )

    tools.operation("trd", mark)
    return {
        "ok": True,
        "trdPath": str(output),
        "filingPath": args.get("trdPath"),
        "decisionIds": ids,
        "warnings": warnings,
    }
