from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from parley.db.session import make_engine, to_driver_url
from parley.seed.config import SeedConfig
from parley.seed.runner import seed_database
from parley.settings import get_settings

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _test_url() -> str:
    url = make_url(str(get_settings().database_url))
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


def _recreate_database(url: str) -> None:
    target = make_url(url)
    admin = create_engine(
        to_driver_url(target.set(database="postgres").render_as_string(hide_password=False)),
        isolation_level="AUTOCOMMIT",
    )
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{target.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = _test_url()
    _recreate_database(url)
    config = Config(str(ALEMBIC_INI))
    config.attributes["url"] = url
    command.upgrade(config, "head")
    eng = make_engine(url)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    sess = Session(connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield sess
    sess.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="module")
def seeded(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    sess = Session(connection, expire_on_commit=False)
    seed_database(sess, SeedConfig())
    yield sess
    sess.close()
    transaction.rollback()
    connection.close()
