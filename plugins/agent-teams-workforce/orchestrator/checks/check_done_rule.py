"""Pure S04e completion checks; no workflow, process, tracker or vault writes."""

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from orchestrator.checks.check_support import report, require

if TYPE_CHECKING:
    from orchestrator.core.io import JsonValue

from orchestrator.flows.elaboration_support import done_rule, repository_failure


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Evaluate the existing isolated check contract."""
    rows: list[dict[str, JsonValue]] = [
        {
            "repository": "one",
            "spec": {"ok": True, "story": {"id": "story-1"}},
            "tasks": {"ok": True, "tasks": [{"id": "task-1"}], "coverage": {}},
        },
        {
            "repository": "two",
            "spec": {"ok": True, "story": {"id": "story-2"}},
            "tasks": {
                "ok": True,
                "tasks": [{"id": "task-2"}],
                "coverage": {"uncitedAfter": []},
            },
        },
    ]
    require(done_rule(rows, True, [])["done"], "done_rule(rows, True, [])['done']")
    require(not done_rule([], True, [])["done"], "not done_rule([], True, [])['done']")
    require(not done_rule(rows, False, [])["done"], "not done_rule(rows, False, [])['done']")
    require(
        not done_rule(rows, True, [{"id": "task-2", "reason": "unsized"}])["done"],
        "not done_rule(rows, True, [{'id': 'task-2', 'reason': 'unsized'}])['done']",
    )
    missing_cases: tuple[dict[str, JsonValue], ...] = (
        {},
        {"ok": False},
        {"ok": True, "tasks": []},
        {"ok": True, "tasks": [{"id": "task-2"}], "coverage": {"uncitedAfter": ["D2"]}},
    )
    for missing in missing_cases:
        require(
            not done_rule([rows[0], {**rows[1], "tasks": missing}], True, [])["done"],
            "not done_rule([rows[0], {**rows[1], 'tasks': missing}], True, [])['done']",
        )
    require(
        not done_rule([{**rows[0], "spec": {"ok": True, "story": {}}}], True, [])["done"],
        "not done_rule([{**rows[0], 'spec': {'ok': True, 'story': {}}}], True, [])['done']",
    )
    bad: list[dict[str, JsonValue]] = [{"repository": "one", "spec": {"ok": False, "failure": {"cause": "quota"}}}]
    require(repository_failure(bad)["cause"] == "quota", "repository_failure(bad)['cause'] == 'quota'")
    bad.append(
        {"repository": "two", "tasks": {"ok": False, "failure": {"cause": "other"}}},
    )
    require(repository_failure(bad)["cause"] == "other", "repository_failure(bad)['cause'] == 'other'")
    report("PASS: repository Stories/Tasks/coverage, nonempty span, edges, scores and mixed failure causes")


if __name__ == "__main__":
    main()
