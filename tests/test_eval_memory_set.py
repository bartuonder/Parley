import asyncio
from datetime import date

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from parley.backend.services import Backend
from parley.evals.actions import apply_all, is_refused
from parley.evals.agent_run import Architecture, run_scenario
from parley.evals.loader import MEMORY_SCENARIO_DIR, load_scenarios
from parley.evals.schema import MemorySpec, Scenario
from parley.evals.state import diff_snapshots, normalize, take_snapshot
from parley.evals.world import build_world
from parley.memory.store import recall
from parley.policies.loader import load_policies
from parley.policies.models import Region
from parley.policies.validate import current_docs
from parley.seed.config import REFERENCE_NOW
from tests.fakes import reference_multi_llm, router_for

SCENARIOS = load_scenarios(MEMORY_SCENARIO_DIR)
IDS = [s.id for s in SCENARIOS]


def test_memory_set_is_not_part_of_the_core_set() -> None:
    core = {s.id for s in load_scenarios()}
    assert not core & set(IDS) and len(SCENARIOS) == 4
    assert any(s.expected.requires_human for s in SCENARIOS)
    assert any(not s.expected.requires_human for s in SCENARIOS)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_memory_is_seeded_with_ids_filled_in(scenario: Scenario, session: Session) -> None:
    index = build_world(session, scenario)
    customer_id = index.customers[scenario.memory[0].customer]
    facts = recall(session, customer_id)
    assert len(facts) == len(
        [m for m in scenario.memory if m.customer == scenario.memory[0].customer]
    )
    assert all("{" not in f.content and f.created_at < REFERENCE_NOW for f in facts)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_reference_solution_and_forbidden_actions_hold_against_the_backend(
    scenario: Scenario, session: Session
) -> None:
    backend = Backend(session, lambda: REFERENCE_NOW)
    index = build_world(session, scenario)
    before = take_snapshot(session, index)
    apply_all(backend, index, scenario.reference_actions, scenario.id)
    after = take_snapshot(session, index)
    assert normalize(diff_snapshots(before, after)) == normalize(scenario.expected.diff)
    for n, action in enumerate(scenario.forbidden_actions, start=1):
        assert is_refused(backend, index, action, f"{scenario.id}-forbidden-{n}")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_cited_policies_are_in_force(scenario: Scenario) -> None:
    docs = load_policies()
    in_force = {d.key for r in Region for d in current_docs(docs, date(2026, 6, 1), r)}
    assert set(scenario.expected.policy_refs) <= in_force


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_reference_plan_passes_through_the_multi_agent_graph(
    scenario: Scenario, session: Session
) -> None:
    outcome = asyncio.run(
        run_scenario(
            session,
            scenario,
            reference_multi_llm,
            lambda _: None,
            model="scripted",
            max_steps=8,
            max_cost_usd=1.0,
            arch=Architecture(name="multi", router_llm_factory=router_for),
        )
    )
    assert outcome.success and outcome.handover_ok and outcome.error is None


def test_memory_for_an_unknown_customer_is_rejected() -> None:
    raw = SCENARIOS[0].model_dump()
    raw["memory"] = [MemorySpec(customer="nobody", kind="k", content="c").model_dump()]
    with pytest.raises(ValidationError, match="unknown customers"):
        Scenario(**raw)
