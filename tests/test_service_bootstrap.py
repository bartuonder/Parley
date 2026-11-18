from sqlalchemy.orm import Session

from parley.service.bootstrap import needs_index, needs_world
from tests.factories import make_customer


def test_an_empty_database_needs_the_world_and_a_populated_one_does_not(session: Session) -> None:
    assert needs_world(session) is True
    make_customer(session, "ada@example.com")
    assert needs_world(session) is False


def test_a_database_without_an_index_needs_one(session: Session) -> None:
    assert needs_index(session) is True
