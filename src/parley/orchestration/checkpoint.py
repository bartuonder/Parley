from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from parley.settings import get_settings


@asynccontextmanager
async def postgres_checkpointer(url: str | None = None) -> AsyncIterator[AsyncPostgresSaver]:
    """Postgres checkpointer on the project database; LangGraph creates its own tables."""
    conn_string = url or str(get_settings().database_url)
    async with AsyncPostgresSaver.from_conn_string(conn_string) as saver:
        await saver.setup()
        yield saver
