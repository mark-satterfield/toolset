#!/usr/bin/env python3
"""Generate composites_contract.py and composite-phases.js from schemas/composites.json.

composites.json, under schemas/composites.schema.json, is the one definition of every composite
id, its runner, its phases and their titles, its role sets and its opening kind. This script
validates it against the schema's vocabularies and renders the typed Python module the driver
and the orchestrator load, and the shared block every workflow script carries.

Usage:
  generate_composites.py           Write both generated files.
  generate_composites.py --check   Exit 1 when either generated file is stale.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

SCRIPTS_DIR: Final[Path] = Path(__file__).resolve().parent
SKILL_DIR: Final[Path] = SCRIPTS_DIR.parent
SCHEMA_PATH: Final[Path] = SKILL_DIR / "schemas" / "composites.schema.json"
DATA_PATH: Final[Path] = SKILL_DIR / "schemas" / "composites.json"
MODULE_PATH: Final[Path] = SCRIPTS_DIR / "composites_contract.py"
BLOCK_PATH: Final[Path] = SKILL_DIR.parent.parent / "scripts" / "shared-blocks" / "composite-phases.js"

_LINE_WIDTH: Final[int] = 120
_FALLBACK_IDS: Final[str] = 'tuple(phase["id"] for phase in _FALLBACK_SPECS)'


class ContractError(ValueError):
    """composites.json or its schema does not have the shape this generator renders."""


@dataclass(frozen=True)
class Phase:
    """One phase of a composite."""

    id: str
    title: str
    event: bool


@dataclass(frozen=True)
class Composite:
    """One active composite."""

    id: str
    runner: str
    phases: tuple[Phase, ...]
    sets: tuple[str, ...]
    opening_kind: str | None


@dataclass(frozen=True)
class Vocabulary:
    """The schema's closed vocabularies and the names the generated module gives them."""

    id_pattern: str
    runners: tuple[str, ...]
    opening_kinds: tuple[str, ...]
    sets: tuple[str, ...]
    set_frozensets: tuple[tuple[str, str], ...]
    set_singles: tuple[tuple[str, str], ...]
    known_name: str
    retired_name: str
    opening_mapping: str
    wire_names: tuple[tuple[str, str], ...]
    fallback_name: str
    event_name: str


@dataclass(frozen=True)
class Contract:
    """composites.json, parsed and validated."""

    digest: str
    vocabulary: Vocabulary
    wire: tuple[tuple[str, str], ...]
    fallback: tuple[Phase, ...]
    composites: tuple[Composite, ...]
    retired: tuple[tuple[str, tuple[str, ...]], ...]
    document: dict[str, object]


def _obj(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        msg: str = f"{where}: expected an object"
        raise ContractError(msg)
    result: dict[str, object] = {}
    key: object
    item: object
    for key, item in value.items():
        if not isinstance(key, str):
            msg = f"{where}: non-string key"
            raise ContractError(msg)
        result[key] = item
    return result


def _list(value: object, where: str) -> list[object]:
    if not isinstance(value, list):
        msg: str = f"{where}: expected an array"
        raise ContractError(msg)
    items: list[object] = list(value)
    return items


def _str(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        msg: str = f"{where}: expected a non-empty string"
        raise ContractError(msg)
    return value


def _strs(value: object, where: str) -> tuple[str, ...]:
    return tuple(_str(item, where) for item in _list(value, where))


def _pairs(value: object, where: str) -> tuple[tuple[str, str], ...]:
    return tuple((key, _str(item, where)) for key, item in _obj(value, where).items())


def _vocabulary(schema: dict[str, object]) -> Vocabulary:
    defs: dict[str, object] = _obj(schema["$defs"], "$defs")
    composite_id: dict[str, object] = _obj(defs["compositeId"], "$defs.compositeId")
    set_def: dict[str, object] = _obj(defs["set"], "$defs.set")
    set_python: dict[str, object] = _obj(set_def["x-python"], "$defs.set.x-python")
    sets: tuple[str, ...] = _strs(set_def["enum"], "$defs.set.enum")
    frozensets: tuple[tuple[str, str], ...] = _pairs(set_python["frozensets"], "$defs.set.x-python.frozensets")
    singles: tuple[tuple[str, str], ...] = _pairs(set_python["singles"], "$defs.set.x-python.singles")
    if sorted(name for name, _ in (*frozensets, *singles)) != sorted(sets):
        msg: str = "$defs.set: x-python must name every set exactly once"
        raise ContractError(msg)
    properties: dict[str, object] = _obj(schema["properties"], "properties")
    wire: dict[str, object] = _obj(_obj(properties["wire"], "properties.wire")["properties"], "wire.properties")
    phase_props: dict[str, object] = _obj(_obj(defs["phase"], "$defs.phase")["properties"], "$defs.phase")
    opening: dict[str, object] = _obj(defs["openingKind"], "$defs.openingKind")
    return Vocabulary(
        id_pattern=_str(composite_id["pattern"], "$defs.compositeId.pattern"),
        runners=_strs(_obj(defs["runner"], "$defs.runner")["enum"], "$defs.runner.enum"),
        opening_kinds=_strs(opening["enum"], "$defs.openingKind.enum"),
        sets=sets,
        set_frozensets=frozensets,
        set_singles=singles,
        known_name=_str(set_python["known"], "$defs.set.x-python.known"),
        retired_name=_str(set_python["retired"], "$defs.set.x-python.retired"),
        opening_mapping=_str(_obj(opening["x-python"], "$defs.openingKind")["mapping"], "openingKind.mapping"),
        wire_names=tuple(
            (key, _str(_obj(spec, f"wire.{key}")["x-constant"], f"wire.{key}")) for key, spec in wire.items()
        ),
        fallback_name=_str(_obj(properties["fallbackPhases"], "fallbackPhases")["x-constant"], "fallbackPhases"),
        event_name=_str(_obj(phase_props["event"], "$defs.phase.event")["x-collect"], "$defs.phase.event"),
    )


def _id(value: object, vocabulary: Vocabulary, where: str) -> str:
    text: str = _str(value, where)
    if re.fullmatch(vocabulary.id_pattern, text) is None:
        msg: str = f"{where}: {text!r} is not a kebab-case id"
        raise ContractError(msg)
    return text


def _sets(value: object, vocabulary: Vocabulary, where: str) -> tuple[str, ...]:
    sets: tuple[str, ...] = _strs(value, where)
    if len(set(sets)) != len(sets) or not set(sets) <= set(vocabulary.sets):
        msg: str = f"{where}: sets must be distinct values of $defs.set"
        raise ContractError(msg)
    return sets


def _phases(value: object, vocabulary: Vocabulary, where: str) -> tuple[Phase, ...]:
    phases: list[Phase] = []
    for index, raw in enumerate(_list(value, where)):
        entry: dict[str, object] = _obj(raw, f"{where}[{index}]")
        if not set(entry) <= {"id", "title", "event"}:
            msg: str = f"{where}[{index}]: unknown phase field"
            raise ContractError(msg)
        event: object = entry.get("event", False)
        if not isinstance(event, bool):
            msg = f"{where}[{index}].event: expected a boolean"
            raise ContractError(msg)
        phases.append(Phase(_id(entry["id"], vocabulary, where), _str(entry["title"], where), event))
    if len({phase.id for phase in phases}) != len(phases):
        msg = f"{where}: phase ids must be distinct"
        raise ContractError(msg)
    return tuple(phases)


def _composite(key: str, raw: object, vocabulary: Vocabulary) -> Composite:
    where: str = f"composites.{key}"
    entry: dict[str, object] = _obj(raw, where)
    if not set(entry) <= {"runner", "phases", "sets", "openingKind"}:
        msg: str = f"{where}: unknown composite field"
        raise ContractError(msg)
    runner: str = _str(entry["runner"], where)
    if runner not in vocabulary.runners:
        msg = f"{where}.runner: {runner!r} is not a $defs.runner value"
        raise ContractError(msg)
    opening: str | None = None
    if "openingKind" in entry:
        opening = _str(entry["openingKind"], where)
        if opening not in vocabulary.opening_kinds:
            msg = f"{where}.openingKind: {opening!r} is not a $defs.openingKind value"
            raise ContractError(msg)
    return Composite(
        id=_id(key, vocabulary, where),
        runner=runner,
        phases=_phases(entry["phases"], vocabulary, f"{where}.phases"),
        sets=_sets(entry["sets"], vocabulary, f"{where}.sets"),
        opening_kind=opening,
    )


def parse(schema_text: str, data_text: str) -> Contract:
    """Parse and validate composites.json under its schema.

    Args:
        schema_text: The schema file's text.
        data_text: composites.json's text.

    Returns:
        The validated contract.

    Raises:
        TypeError: An argument is not a string.
        ContractError: The schema or the data does not have the expected shape.

    """
    if not isinstance(schema_text, str) or not isinstance(data_text, str):
        argument_error: str = "parse: schema_text and data_text must be strings"
        raise TypeError(argument_error)
    vocabulary: Vocabulary = _vocabulary(_obj(json.loads(schema_text), "schema"))
    document: dict[str, object] = _obj(json.loads(data_text), "composites.json")
    if not set(document) <= {"$schema", "wire", "fallbackPhases", "composites", "retired"}:
        msg: str = "composites.json: unknown top-level field"
        raise ContractError(msg)
    wire_raw: dict[str, object] = _obj(document["wire"], "wire")
    wire: tuple[tuple[str, str], ...] = tuple(
        (constant, _str(wire_raw[key], f"wire.{key}")) for key, constant in vocabulary.wire_names
    )
    composites: tuple[Composite, ...] = tuple(
        _composite(key, raw, vocabulary) for key, raw in _obj(document["composites"], "composites").items()
    )
    retired: tuple[tuple[str, tuple[str, ...]], ...] = tuple(
        (
            _id(key, vocabulary, f"retired.{key}"),
            _sets(_obj(raw, f"retired.{key}")["sets"], vocabulary, f"retired.{key}.sets"),
        )
        for key, raw in _obj(document["retired"], "retired").items()
    )
    ids: list[str] = [composite.id for composite in composites] + [key for key, _ in retired]
    if len(set(ids)) != len(ids):
        msg = "composites.json: an id is both active and retired"
        raise ContractError(msg)
    memberships: dict[str, list[str]] = {name: [] for name in vocabulary.sets}
    for composite in composites:
        for name in composite.sets:
            memberships[name].append(composite.id)
    for key, sets in retired:
        for name in sets:
            memberships[name].append(key)
    for name, constant in vocabulary.set_singles:
        if len(memberships[name]) != 1:
            msg = f"set {name!r} ({constant}) must hold exactly one composite"
            raise ContractError(msg)
    digest: str = hashlib.sha256((schema_text + "\0" + data_text).encode("utf-8")).hexdigest()
    return Contract(
        digest=digest,
        vocabulary=vocabulary,
        wire=wire,
        fallback=_phases(document["fallbackPhases"], vocabulary, "fallbackPhases"),
        composites=composites,
        retired=retired,
        document=document,
    )


def constant_name(identifier: str) -> str:
    """Return the upper-snake constant name of a kebab-case id.

    Args:
        identifier: A kebab-case id.

    Returns:
        The constant name.

    """
    return identifier.replace("-", "_").upper()


def _literal(name: str, values: list[str]) -> list[str]:
    quoted: list[str] = [json.dumps(value) for value in values]
    single: str = f"type {name} = Literal[{', '.join(quoted)}]"
    if len(single) <= _LINE_WIDTH:
        return [single]
    return [f"type {name} = Literal[", *(f"    {value}," for value in quoted), "]"]


def _frozenset(head: str, members: list[str]) -> list[str]:
    single: str = f"{head}frozenset({{{', '.join(members)}}})"
    if len(single) <= _LINE_WIDTH:
        return [single]
    return [f"{head}frozenset({{", *(f"    {member}," for member in members), "})"]


def _phase_ids(contract: Contract) -> list[str]:
    seen: dict[str, None] = {}
    for composite in contract.composites:
        for phase in composite.phases:
            seen[phase.id] = None
    for phase in contract.fallback:
        seen[phase.id] = None
    return list(seen)


def _phase_line(phase: Phase) -> str:
    return f"{{{json.dumps('id')}: {json.dumps(phase.id)}, {json.dumps('title')}: {json.dumps(phase.title)}}},"


_HEAD: Final[tuple[str, ...]] = (
    '"""Composite ids, their phases and role sets, and the composite progress display vocabulary.',
    "",
    "GENERATED by generate_composites.py from schemas/composites.json under schemas/composites.schema.json.",
    "Do not edit: change composites.json and regenerate. check_composites_contract.py fails when this file",
    "is stale.",
    '"""',
    "",
    "from __future__ import annotations",
    "",
    "from types import MappingProxyType",
    "from typing import TYPE_CHECKING, Final, Literal, NotRequired, TypedDict, TypeIs",
    "",
    "if TYPE_CHECKING:",
    "    from collections.abc import Mapping",
    "",
)


def _render_vocabulary(lines: list[str], contract: Contract) -> None:
    vocabulary: Vocabulary = contract.vocabulary
    ids: list[str] = [composite.id for composite in contract.composites] + [key for key, _ in contract.retired]
    lines.extend(("#: SHA-256 of the schema and composites.json this module was generated from.",))
    lines.append(f"SOURCE_SHA256: Final[str] = {json.dumps(contract.digest)}")
    lines.extend(("", "#: Every composite id, active then retired."))
    lines.extend(_literal("CompositeId", ids))
    lines.extend(f"{constant_name(key)}: Final[CompositeId] = {json.dumps(key)}" for key in ids)
    lines.extend(("", "#: Every phase id a composite or the fallback declares."))
    lines.extend(_literal("PhaseId", _phase_ids(contract)))
    lines.extend(("", "#: What runs a composite."))
    lines.extend(_literal("Runner", list(vocabulary.runners)))
    lines.extend(("", "#: The kind of bead a composite opens a run budget for."))
    lines.extend(_literal("OpeningKind", list(vocabulary.opening_kinds)))
    lines.extend(("", "#: A role set a composite belongs to."))
    lines.extend(_literal("CompositeSet", list(vocabulary.sets)))
    lines.append("")
    for constant, value in contract.wire:
        lines.append(f"{constant}: Final[str] = {json.dumps(value)}")
    lines.extend((
        "",
        "",
        "class PhaseSpec(TypedDict):",
        '    """One phase of a composite, in run order."""',
        "",
        "    id: PhaseId",
        "    title: str",
        "",
        "",
        "class CompositeSpec(TypedDict):",
        '    """One composite: its runner, its phases in run order, its role sets and its opening kind."""',
        "",
        "    runner: Runner",
        "    phases: tuple[PhaseSpec, ...]",
        "    sets: frozenset[CompositeSet]",
        "    openingKind: NotRequired[OpeningKind]",
        "",
        "",
    ))


def _render_composites(lines: list[str], contract: Contract) -> None:
    vocabulary: Vocabulary = contract.vocabulary
    lines.extend((
        "#: Phases shown for a known composite that declares none (a retired id, or probe).",
        "_FALLBACK_SPECS: Final[tuple[PhaseSpec, ...]] = (",
    ))
    lines.extend(f"    {_phase_line(phase)}" for phase in contract.fallback)
    lines.extend((
        ")",
        f"{vocabulary.fallback_name}: Final[tuple[PhaseId, ...]] = {_FALLBACK_IDS}",
        "",
        "#: Every composite the pipeline dispatches.",
        "COMPOSITES: Final[Mapping[CompositeId, CompositeSpec]] = MappingProxyType({",
    ))
    for composite in contract.composites:
        lines.extend((f"    {constant_name(composite.id)}: {{", f'        "runner": {json.dumps(composite.runner)},'))
        if len(composite.phases) == 1:
            lines.append(f'        "phases": ({_phase_line(composite.phases[0])}),')
        elif composite.phases:
            lines.append('        "phases": (')
            lines.extend(f"            {_phase_line(phase)}" for phase in composite.phases)
            lines.append("        ),")
        else:
            lines.append('        "phases": (),')
        lines.append(f'        "sets": frozenset({{{", ".join(json.dumps(name) for name in composite.sets)}}}),')
        if composite.opening_kind is not None:
            lines.append(f'        "openingKind": {json.dumps(composite.opening_kind)},')
        lines.append("    },")
    lines.extend((
        "})",
        "#: Composite -> its phase ids in run order.",
        "PHASE_IDS: Final[Mapping[CompositeId, tuple[PhaseId, ...]]] = MappingProxyType({",
        '    composite: tuple(phase["id"] for phase in spec["phases"]) for composite, spec in COMPOSITES.items()',
        "})",
        "#: Composite -> its phase titles in run order.",
        "PHASE_TITLES: Final[Mapping[CompositeId, tuple[str, ...]]] = MappingProxyType({",
        '    composite: tuple(phase["title"] for phase in spec["phases"]) for composite, spec in COMPOSITES.items()',
        "})",
        "#: Composite -> the phase ids the orchestrator emits as phase events, in run order.",
        f"{vocabulary.event_name}: Final[Mapping[CompositeId, tuple[PhaseId, ...]]] = MappingProxyType({{",
    ))
    for composite in contract.composites:
        events: list[str] = [json.dumps(phase.id) for phase in composite.phases if phase.event]
        if events:
            lines.append(f"    {constant_name(composite.id)}: (")
            lines.extend(f"        {event}," for event in events)
            lines.append("    ),")
    lines.append("})")


def _render_sets(lines: list[str], contract: Contract) -> None:
    vocabulary: Vocabulary = contract.vocabulary
    members: dict[str, list[str]] = {name: [] for name in vocabulary.sets}
    for composite in contract.composites:
        for name in composite.sets:
            members[name].append(constant_name(composite.id))
    for key, sets in contract.retired:
        for name in sets:
            members[name].append(constant_name(key))
    lines.extend(("", "# Role sets."))
    for name, constant in vocabulary.set_frozensets:
        lines.append(f"#: The {name} set.")
        lines.extend(_frozenset(f"{constant}: Final[frozenset[CompositeId]] = ", members[name]))
    for name, constant in vocabulary.set_singles:
        lines.extend((f"#: The one {name} composite.", f"{constant}: Final[CompositeId] = {members[name][0]}"))
    retired: list[str] = [constant_name(key) for key, _ in contract.retired]
    lines.append("#: Ids no longer dispatched, kept only to attribute historical cost and ledger rows.")
    lines.extend(_frozenset(f"{vocabulary.retired_name}: Final[frozenset[CompositeId]] = ", retired))
    lines.extend((
        "#: Every composite id.",
        f"{vocabulary.known_name}: Final[frozenset[CompositeId]] = frozenset(COMPOSITES) | {vocabulary.retired_name}",
        "#: Composite -> the kind of bead it opens a run budget for.",
        f"{vocabulary.opening_mapping}: Final[Mapping[CompositeId, OpeningKind]] = MappingProxyType({{",
    ))
    lines.extend(
        f"    {constant_name(composite.id)}: {json.dumps(composite.opening_kind)},"
        for composite in contract.composites
        if composite.opening_kind is not None
    )
    lines.append("})")


_FUNCTIONS: Final[str] = '''

def is_composite_id(value: object) -> TypeIs[CompositeId]:
    """Return whether a value is a known composite id, active or retired.

    Args:
        value: Any value.

    Returns:
        True when the value is a string in KNOWN.

    """
    return isinstance(value, str) and value in KNOWN


def composite_id(value: object) -> CompositeId:
    """Narrow a wire value to a known composite id.

    Args:
        value: The value read from a bead, a ledger row or an argument.

    Returns:
        The composite id.

    Raises:
        TypeError: The value is not a string.
        ValueError: The string is not a known composite id.

    """
    if not isinstance(value, str):
        type_error: str = f"a composite id must be a string, not {type(value).__name__}"
        raise TypeError(type_error)
    if not is_composite_id(value):
        value_error: str = f"unknown composite id {value!r}"
        raise ValueError(value_error)
    return value


def _phase_specs(composite: str) -> tuple[PhaseSpec, ...]:
    spec: CompositeSpec | None = COMPOSITES.get(composite_id(composite))
    if spec is None or not spec["phases"]:
        return _FALLBACK_SPECS
    return spec["phases"]


def phases_for(composite: str) -> tuple[PhaseId, ...]:
    """Return a composite's phase ids in run order; an unknown id raises as composite_id does.

    Args:
        composite: A composite id.

    Returns:
        Its phase ids, or FALLBACK_PHASES for a known composite that declares none.

    """
    return tuple(phase["id"] for phase in _phase_specs(composite))


def title_of(composite: str, phase_id: str) -> str:
    """Return the display title of one phase of a composite.

    Args:
        composite: A composite id.
        phase_id: One of its phase ids.

    Returns:
        The phase's title.

    Raises:
        ValueError: The composite is unknown or has no such phase.

    """
    for phase in _phase_specs(composite):
        if phase["id"] == phase_id:
            return phase["title"]
    message: str = f"composite {composite!r} has no phase {phase_id!r}"
    raise ValueError(message)
'''


def render_module(contract: Contract) -> str:
    """Render composites_contract.py.

    Args:
        contract: The validated contract.

    Returns:
        The module text.

    Raises:
        TypeError: The argument is not a Contract.

    """
    if not isinstance(contract, Contract):
        argument_error: str = "render_module: contract must be a Contract"
        raise TypeError(argument_error)
    lines: list[str] = list(_HEAD)
    _render_vocabulary(lines, contract)
    _render_composites(lines, contract)
    _render_sets(lines, contract)
    return "\n".join(lines) + "\n" + _FUNCTIONS


_JS_FUNCTIONS: Final[str] = """const compositePhases = (composite) => {
  const spec = COMPOSITE_CONTRACT.composites[composite]
  if (spec && spec.phases.length) return spec.phases
  if (spec || COMPOSITE_CONTRACT.retired[composite]) return COMPOSITE_CONTRACT.fallbackPhases
  throw new Error(`unknown composite ${composite}`)
}
const compositePhaseTitle = (composite, phase) => {
  const found = compositePhases(composite).find(entry => entry.id === phase)
  if (!found) throw new Error(`composite ${composite} has no phase ${phase}`)
  return found.title
}"""


def render_block(contract: Contract) -> str:
    """Render the composite-phases shared block every workflow script carries.

    Args:
        contract: The validated contract.

    Returns:
        The block text.

    Raises:
        TypeError: The argument is not a Contract.

    """
    if not isinstance(contract, Contract):
        argument_error: str = "render_block: contract must be a Contract"
        raise TypeError(argument_error)
    data: dict[str, object] = {key: value for key, value in contract.document.items() if key != "$schema"}
    return "\n".join((
        "// GENERATED by skills/pipeline-contracts/scripts/generate_composites.py from",
        "// skills/pipeline-contracts/schemas/composites.json, the one definition of composite ids, their phases,",
        "// phase titles and role sets. Never restate any part of it in a workflow: change composites.json and",
        "// regenerate. check_composites_contract.py fails when this file is stale.",
        f"const COMPOSITE_CONTRACT = Object.freeze({json.dumps(data, ensure_ascii=True, separators=(',', ':'))})",
        _JS_FUNCTIONS,
        "",
    ))


def generated() -> dict[Path, str]:
    """Render both generated files from the sources on disk.

    Returns:
        Each generated file's path and its expected text.

    """
    contract: Contract = parse(SCHEMA_PATH.read_text(encoding="utf-8"), DATA_PATH.read_text(encoding="utf-8"))
    return {MODULE_PATH: render_module(contract), BLOCK_PATH: render_block(contract)}


def stale() -> list[Path]:
    """Return the generated files whose text on disk differs from what the sources generate.

    Returns:
        The stale or missing files.

    """
    return [
        path
        for path, text in generated().items()
        if (path.read_text(encoding="utf-8") if path.is_file() else "") != text
    ]


def main(argv: list[str] | None = None) -> int:
    """Write the generated files, or check they are current.

    Args:
        argv: Command-line arguments, or None for sys.argv.

    Returns:
        0 when written or current; 1 when --check finds a stale file.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when a generated file is stale")
    if bool(parser.parse_args(argv).check):
        outdated: list[Path] = stale()
        for path in outdated:
            sys.stderr.write(f"{path} is stale: run {Path(__file__).name} to regenerate it\n")
        return 1 if outdated else 0
    for path, text in generated().items():
        path.write_text(text, encoding="utf-8")
        sys.stdout.write(f"wrote {path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
