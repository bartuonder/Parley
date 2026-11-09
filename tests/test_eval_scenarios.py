from datetime import date

import pytest
from sqlalchemy.orm import Session

from parley.backend.services import Backend
from parley.evals.actions import apply_all, is_refused
from parley.evals.loader import load_scenarios
from parley.evals.schema import Scenario
from parley.evals.state import diff_snapshots, normalize, take_snapshot
from parley.evals.world import build_world, render_text
from parley.policies.loader import load_policies
from parley.policies.models import Region
from parley.policies.validate import current_docs
from parley.seed.config import REFERENCE_NOW

SCENARIOS = load_scenarios()


def ids(scenarios: list[Scenario]) -> list[str]:
    return [s.id for s in scenarios]


@pytest.fixture
def backend(session: Session) -> Backend:
    return Backend(session, lambda: REFERENCE_NOW)


def test_scenario_ids_are_unique() -> None:
    assert len(set(ids(SCENARIOS))) == len(SCENARIOS)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=ids(SCENARIOS))
def test_reference_solution_produces_expected_state_diff(
    scenario: Scenario, session: Session, backend: Backend
) -> None:
    index = build_world(session, scenario)
    before = take_snapshot(session, index)
    apply_all(backend, index, scenario.reference_actions, scenario.id)
    after = take_snapshot(session, index)
    assert normalize(diff_snapshots(before, after)) == normalize(scenario.expected.diff)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=ids(SCENARIOS))
def test_forbidden_actions_are_refused_by_the_backend(
    scenario: Scenario, session: Session, backend: Backend
) -> None:
    index = build_world(session, scenario)
    for n, action in enumerate(scenario.forbidden_actions, start=1):
        assert is_refused(backend, index, action, f"{scenario.id}-forbidden-{n}"), action


@pytest.mark.parametrize("scenario", SCENARIOS, ids=ids(SCENARIOS))
def test_cited_policies_exist_and_are_in_force(scenario: Scenario) -> None:
    docs = load_policies()
    in_force = {d.key for region in Region for d in current_docs(docs, date(2026, 6, 1), region)}
    for ref in scenario.expected.policy_refs:
        assert ref in in_force, ref


@pytest.mark.parametrize("scenario", SCENARIOS, ids=ids(SCENARIOS))
def test_ticket_placeholders_resolve_to_database_ids(scenario: Scenario, session: Session) -> None:
    index = build_world(session, scenario)
    for text in (scenario.ticket.subject, scenario.ticket.body):
        assert text.strip()
        rendered = render_text(text, index)
        assert "{" not in rendered and "}" not in rendered
