import pytest

from parley.evals.agent_eval import build_report, is_complete, select_scenarios
from parley.evals.loader import load_scenarios
from tests.test_eval_report import outcome

SCENARIOS = load_scenarios()


def test_select_by_ids_category_and_limit() -> None:
    assert [s.id for s in select_scenarios(SCENARIOS, ["REF-001", "ADV-001"], None, None)] == [
        s.id for s in SCENARIOS if s.id in {"REF-001", "ADV-001"}
    ]
    billing = select_scenarios(SCENARIOS, [], "billing", None)
    assert billing and all(s.category == "billing" for s in billing)
    assert len(select_scenarios(SCENARIOS, [], None, 3)) == 3


def test_unknown_scenario_id_aborts() -> None:
    with pytest.raises(SystemExit, match="NOPE-999"):
        select_scenarios(SCENARIOS, ["NOPE-999"], None, None)


def test_report_carries_meta_summary_groups_and_every_outcome() -> None:
    report = build_report([outcome("A"), outcome("B", category="billing")], "m", {"max_steps": 5})
    assert report["meta"]["model"] == "m" and report["meta"]["max_steps"] == 5
    assert report["summary"]["n"] == 2
    assert set(report["by_category"]) == {"billing", "refund"}
    first = report["outcomes"][0]
    assert first["scenario_id"] == "A" and first["success"] is True and first["handover_ok"] is True


def test_incomplete_or_crashed_runs_are_not_complete() -> None:
    good = [outcome("A"), outcome("B")]
    assert is_complete(good, 2)
    assert not is_complete(good, 3)
    assert not is_complete([outcome("A"), outcome("B", error="RateLimitError")], 2)
