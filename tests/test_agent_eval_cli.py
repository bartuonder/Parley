import pytest

from parley.evals.agent_eval import (
    ABLATIONS,
    build_report,
    default_out,
    is_complete,
    select_scenarios,
)
from parley.evals.loader import SCENARIO_SETS, load_scenarios, load_set
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


def test_repeated_runs_add_variance_to_the_report() -> None:
    runs = [[outcome("A")], [outcome("A", state_ok=False)]]
    flat = [o for run in runs for o in run]
    report = build_report(flat, "m", {"arch": "multi"}, runs)
    assert report["repeats"]["runs"] == 2 and report["repeats"]["unstable"] == ["A"]
    assert len(report["per_run"]) == 2 and report["meta"]["arch"] == "multi"
    assert "repeats" not in build_report(runs[0], "m", {}, runs[:1])


def test_each_architecture_writes_its_own_report() -> None:
    assert default_out("single").name == "agent_single.json"
    assert default_out("multi").name == "agent_multi.json"


def test_the_memory_set_writes_its_own_report_files() -> None:
    assert default_out("multi", "memory").name == "agent_multi_memory.json"
    assert default_out("single", "core").name == "agent_single.json"


def test_named_sets_load_and_unknown_sets_are_rejected() -> None:
    assert {s.id for s in load_set("core")} == {s.id for s in SCENARIOS}
    assert {s.id for s in load_set("memory")} >= {"MEM-001"}
    assert set(SCENARIO_SETS) == {"core", "heldout", "memory", "dialogue"}
    with pytest.raises(KeyError, match="unknown scenario set"):
        load_set("nope")


def test_ablated_runs_write_their_own_reports() -> None:
    assert default_out("multi", "core", "critic").name == "agent_multi_no_critic.json"
    assert default_out("multi", "heldout", "router").name == "agent_multi_no_router_heldout.json"
    assert set(ABLATIONS) == {"critic", "rewrite", "router"}
    assert ABLATIONS["critic"].critic is False and ABLATIONS["critic"].route is True
