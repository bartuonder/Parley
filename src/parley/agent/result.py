import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from parley.agent.llm import Usage

CITATION = re.compile(r"POL-[A-Z]{3,4}-\d{3}@v\d+")


class StopReason(StrEnum):
    REPLY = "reply"
    MAX_STEPS = "max_steps"
    BUDGET = "budget"
    UNKNOWN_SENDER = "unknown_sender"


class ToolInvocation(BaseModel):
    name: str
    arguments: dict[str, Any]
    ok: bool
    output: dict[str, Any]


class EscalationRecord(BaseModel):
    reason: str
    summary: str


class AgentResult(BaseModel):
    ticket_id: str
    model: str
    reply: str
    stop_reason: StopReason
    steps: int
    latency_s: float
    usage: Usage = Field(default_factory=Usage)
    tool_calls: list[ToolInvocation] = Field(default_factory=list)
    escalations: list[EscalationRecord] = Field(default_factory=list)

    @property
    def cited_policies(self) -> list[str]:
        """Policy versions named in the reply or returned by policy search, without repeats."""
        found = CITATION.findall(self.reply)
        for call in self.tool_calls:
            if call.name == "search_policies" and call.ok:
                found += CITATION.findall(str(call.output))
        return list(dict.fromkeys(found))
