import json
import re
from dataclasses import dataclass
from typing import Literal

from parley.agent.llm import LLMClient, Usage
from parley.evals.schema import DialogueSpec

SIMULATOR_PROMPT = """\
You play a customer writing to the support team of an online store with subscriptions. You \
are not an assistant: you are a person with a problem, and you write only what that person \
would write next.

Your persona: {persona}
What you want: {goal}
Facts you know (share one only when it is asked for or clearly useful, in your own words):
{facts}

Rules:
- Stay in character. Write one to three sentences, with no greeting after the first message.
- You know nothing beyond the facts above. If the support team asks for something that is not \
in them, say you do not know or do not have it. Never invent order numbers, amounts or dates.
- React to what support just said: answer questions, accept or push back, change your mind if \
your persona would.
- Set "done" to true when your issue is resolved, when you accept a refusal and give up, or \
when you would stop writing. Otherwise set it to false and write the next message.
Answer with JSON only: {{"message": "<next message, empty when done>", "done": true or false}}"""

Role = Literal["customer", "support"]


@dataclass(frozen=True)
class Turn:
    role: Role
    text: str


@dataclass(frozen=True)
class CustomerMove:
    message: str
    done: bool
    usage: Usage


def render_transcript(turns: list[Turn]) -> str:
    return "\n".join(f"[{t.role}] {t.text}" for t in turns)


def _parse(text: str) -> tuple[str, bool] | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        return None
    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("done"), bool):
        return None
    return str(value.get("message") or "").strip(), value["done"]


async def next_customer_move(llm: LLMClient, spec: DialogueSpec, turns: list[Turn]) -> CustomerMove:
    """Ask the simulated customer for the next message; an unreadable answer ends the dialogue."""
    facts = "\n".join(f"- {f}" for f in spec.facts) or "- (none)"
    system = SIMULATOR_PROMPT.format(persona=spec.persona, goal=spec.goal, facts=facts)
    response = await llm.complete(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Conversation so far:\n{render_transcript(turns)}"},
        ],
        [],
    )
    parsed = _parse(response.content or "")
    if parsed is None:
        return CustomerMove("", True, response.usage)
    message, done = parsed
    return CustomerMove(message, done or not message, response.usage)
