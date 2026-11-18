from sqlalchemy import func, select
from sqlalchemy.orm import Session

from parley.db.models import Customer
from parley.db.session import make_engine, session_scope
from parley.policies.loader import load_policies
from parley.rag.freshness import StaleIndexError, assert_index_fresh
from parley.rag.service import DEFAULT_STRATEGY, build_default_index
from parley.seed.config import SeedConfig
from parley.seed.runner import seed_database
from parley.settings import get_settings


def needs_world(session: Session) -> bool:
    return not session.scalar(select(func.count()).select_from(Customer))


def needs_index(session: Session) -> bool:
    try:
        assert_index_fresh(session, DEFAULT_STRATEGY, load_policies())
    except StaleIndexError:
        return True
    return False


def main() -> None:
    """Prepare an empty database for the service: the synthetic world and, if live, the index."""
    settings = get_settings()
    with session_scope(make_engine()) as session:
        if needs_world(session):
            seed_database(session, SeedConfig())
            print("seeded the synthetic world", flush=True)
        if settings.llm_mode == "live" and needs_index(session):
            print(f"indexed {build_default_index(session)} policy chunks", flush=True)


if __name__ == "__main__":
    main()
