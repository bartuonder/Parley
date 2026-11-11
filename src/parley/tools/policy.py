from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from parley.policies.regions import region_for_country
from parley.rag.service import search_policies
from parley.tools.context import ToolContext
from parley.tools.permissions import Permission
from parley.tools.registry import ToolParams, ToolSpec, ToolUnavailableError


class SearchParams(ToolParams):
    query: str = Field(min_length=3, max_length=300, description="A question about company policy")


class Passage(BaseModel):
    citation: str
    effective_date: date
    text: str


class PolicySearchResult(BaseModel):
    passages: list[Passage]


def run_policy_search(ctx: ToolContext, params: SearchParams) -> PolicySearchResult:
    if ctx.retriever is None:
        raise ToolUnavailableError("policy search is not configured")
    customer = ctx.backend.get_customer(ctx.customer_id)
    hits = search_policies(
        ctx.retriever,
        params.query,
        as_of=ctx.backend.now().date(),
        region=region_for_country(customer.country),
    )
    return PolicySearchResult(
        passages=[
            Passage(
                citation=h.citation,
                effective_date=h.chunk.effective_date,
                text=h.chunk.text,
            )
            for h in hits
        ]
    )


POLICY_TOOLS: list[ToolSpec[Any]] = [
    ToolSpec(
        "search_policies",
        "Search the company policies in force today for the sender's region. Returns passages "
        "with citations such as POL-REF-001@v2 / Return window. Ask one focused question.",
        Permission.READ,
        SearchParams,
        run_policy_search,
    ),
]
