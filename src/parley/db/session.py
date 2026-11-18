from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from parley.settings import get_settings


def to_driver_url(url: str) -> str:
    """Point a plain postgresql:// URL at the psycopg 3 driver."""
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def make_engine(
    url: str | None = None, pool_size: int | None = None, max_overflow: int | None = None
) -> Engine:
    raw = url if url is not None else str(get_settings().database_url)
    pool: dict[str, int] = {}
    if pool_size is not None:
        pool["pool_size"] = pool_size
    if max_overflow is not None:
        pool["max_overflow"] = max_overflow
    return create_engine(to_driver_url(raw), pool_pre_ping=True, **pool)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
