"""Pure S04e completion checks; no workflow, process, tracker or vault writes."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from orchestrator.flows.elaboration_support import done_rule, repository_failure


def main():
    rows = [
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
    assert done_rule(rows, True, [])["done"]
    assert not done_rule([], True, [])["done"]
    assert not done_rule(rows, False, [])["done"]
    assert not done_rule(rows, True, [{"id": "task-2", "reason": "unsized"}])["done"]
    for missing in (
        {},
        {"ok": False},
        {"ok": True, "tasks": []},
        {"ok": True, "tasks": [{"id": "task-2"}], "coverage": {"uncitedAfter": ["D2"]}},
    ):
        assert not done_rule([rows[0], {**rows[1], "tasks": missing}], True, [])["done"]
    assert not done_rule([{**rows[0], "spec": {"ok": True, "story": {}}}], True, [])[
        "done"
    ]
    bad = [{"repository": "one", "spec": {"ok": False, "failure": {"cause": "quota"}}}]
    assert repository_failure(bad)["cause"] == "quota"
    bad.append(
        {"repository": "two", "tasks": {"ok": False, "failure": {"cause": "other"}}}
    )
    assert repository_failure(bad)["cause"] == "other"
    print(
        "PASS: repository Stories/Tasks/coverage, nonempty span, edges, scores and mixed failure causes"
    )


if __name__ == "__main__":
    main()
