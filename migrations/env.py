from logging.config import fileConfig

from alembic import context

from parley.db import models  # noqa: F401  (registers tables on the metadata)
from parley.db.base import Base
from parley.db.session import make_engine
from parley.rag import tables  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = make_engine(config.attributes.get("url"))
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_online()
