from collections.abc import AsyncIterator
from contextlib import AbstractContextManager, asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from parley.agent.llm import LiteLLMClient, LLMClient
from parley.clock import utcnow
from parley.db.session import make_engine, session_scope
from parley.observability.exporters import PostgresExporter
from parley.observability.tracing import telemetry
from parley.orchestration.checkpoint import postgres_checkpointer
from parley.rag.service import default_retriever
from parley.service.core import Limits, SessionFactory, TicketService
from parley.service.simulated import SimulatedLLM
from parley.settings import Settings, get_settings


@dataclass(frozen=True)
class Runtime:
    """What the HTTP layer needs: the ticket service and a way to open database sessions."""

    service: TicketService
    sessions: SessionFactory


def build_clients(settings: Settings) -> tuple[LLMClient, LLMClient]:
    if settings.llm_mode == "simulated":
        simulated = SimulatedLLM(settings.simulated_latency_s)
        return simulated, simulated
    if settings.llm_api_key is None:
        raise RuntimeError("PARLEY_LLM_API_KEY is not set; use PARLEY_LLM_MODE=simulated to demo")
    return LiteLLMClient(model=settings.agent_model), LiteLLMClient(model=settings.router_model)


def session_factory(engine: Engine) -> SessionFactory:
    def open_session() -> AbstractContextManager[Session]:
        return session_scope(engine)

    return open_session


@asynccontextmanager
async def open_runtime(settings: Settings | None = None) -> AsyncIterator[Runtime]:
    """Engine, tracing, checkpointer and service for one process; closed on exit."""
    settings = settings or get_settings()
    slots = settings.max_concurrent_tickets
    engine = make_engine(pool_size=2 * slots + 4, max_overflow=slots)
    telemetry.configure(
        [PostgresExporter(engine)], capture_content=settings.trace_content, batch=True
    )
    llm, router = build_clients(settings)
    live = settings.llm_mode == "live"
    sessions = session_factory(engine)
    try:
        async with postgres_checkpointer() as saver:
            service = TicketService(
                sessions,
                llm=llm,
                router_llm=router,
                checkpointer=saver,
                limits=Limits(
                    model=settings.agent_model if live else "simulated",
                    max_steps=settings.agent_max_steps,
                    max_cost_usd=settings.agent_max_cost_usd,
                    max_revisions=settings.agent_max_revisions,
                ),
                now=utcnow,
                max_concurrency=slots,
                retriever=default_retriever if live else (lambda _: None),
            )
            service.recover()
            try:
                yield Runtime(service, sessions)
            finally:
                await service.wait_idle()
    finally:
        telemetry.shutdown()
        engine.dispose()
