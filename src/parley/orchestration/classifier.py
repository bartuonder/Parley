import json
import random
from pathlib import Path
from typing import Protocol

import numpy as np
from pydantic import BaseModel

from parley.agent.llm import LLMClient, Usage
from parley.agent.ticket import Ticket
from parley.db.enums import TicketCategory
from parley.observability.tracing import span
from parley.orchestration.router import (
    CATEGORY_SPECIALIST,
    RouteDecision,
    Specialist,
    route_ticket,
)
from parley.seed.ticket_templates import TEMPLATES, Template
from parley.settings import PROJECT_ROOT

MODEL_PATH = PROJECT_ROOT / "data" / "models" / "router.json"
CLASSES = [s.value for s in Specialist]
FILLS = {
    "name": ["Ada", "Ben", "Chen", "Dara", "Eli", "Fatima", "Gus", "Hana"],
    "item": [
        "lamp",
        "headphones",
        "jacket",
        "keyboard",
        "blender",
        "backpack",
        "kettle",
        "speaker",
    ],
    "carrier": ["DHL", "UPS", "FedEx", "Aras Kargo"],
    "plan": ["Basic", "Pro", "Team"],
    "reason": ["it broke", "wrong size", "not as described"],
    "days": ["3", "5", "9"],
    "eta": ["Monday", "last week", "Friday"],
    "amount": ["19.00", "49.00", "120.00"],
}


class Embedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


class RouterModel(BaseModel):
    """Softmax regression over ticket embeddings, small enough to commit as JSON."""

    embedding: str
    classes: list[str]
    weights: list[list[float]]
    bias: list[float]

    def probabilities(self, vector: list[float]) -> list[float]:
        logits = np.asarray(self.weights) @ np.asarray(vector) + np.asarray(self.bias)
        exp = np.exp(logits - logits.max())
        return [float(p) for p in exp / exp.sum()]

    def save(self, path: Path = MODEL_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json() + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> "RouterModel":
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))


def train(
    vectors: list[list[float]],
    labels: list[str],
    embedding: str,
    *,
    l2: float = 1e-3,
    rate: float = 1.0,
    epochs: int = 400,
) -> RouterModel:
    x = np.asarray(vectors)
    y = np.asarray([CLASSES.index(label) for label in labels])
    onehot = np.eye(len(CLASSES))[y]
    weights = np.zeros((len(CLASSES), x.shape[1]))
    bias = np.zeros(len(CLASSES))
    for _ in range(epochs):
        logits = x @ weights.T + bias
        exp = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs = exp / exp.sum(axis=1, keepdims=True)
        grad = (probs - onehot) / len(x)
        weights -= rate * (grad.T @ x + l2 * weights)
        bias -= rate * grad.sum(axis=0)
    return RouterModel(
        embedding=embedding,
        classes=CLASSES,
        weights=weights.tolist(),
        bias=bias.tolist(),
    )


def render_template(template: Template, rng: random.Random) -> list[str]:
    """Subjects and bodies of a ticket template with the placeholders filled in."""

    def fill(text: str) -> str:
        values = {k: rng.choice(v) for k, v in FILLS.items()}
        values.update(order_id=str(rng.randint(1, 900)), invoice_id=str(rng.randint(1, 900)))
        values.update(tracking=f"TRK{rng.randint(1000, 9999)}")
        return text.format_map(values)

    return [fill(f"{s}\n{b}") for s in template.subjects for b in template.bodies]


def training_texts(seed: int = 7, copies: int = 3) -> tuple[list[str], list[str]]:
    """Synthetic historical tickets and the specialist each category belongs to."""
    rng = random.Random(seed)
    texts: list[str] = []
    labels: list[str] = []
    for template in TEMPLATES.values():
        specialist = CATEGORY_SPECIALIST[TicketCategory(template.category).value].value
        for _ in range(copies):
            rendered = render_template(template, rng)
            texts += rendered
            labels += [specialist] * len(rendered)
    return texts, labels


class ClassifierRouter:
    """Routes by embedding; below the confidence threshold the model router decides."""

    def __init__(
        self,
        model: RouterModel,
        embedder: Embedder,
        threshold: float = 0.6,
        fallback: LLMClient | None = None,
    ) -> None:
        self.model = model
        self.embedder = embedder
        self.threshold = threshold
        self.fallback = fallback

    async def route(self, ticket: Ticket, fence: bool = False) -> RouteDecision:
        vector = self.embedder.embed_query(f"{ticket.subject}\n{ticket.body}")
        probabilities = self.model.probabilities(vector)
        best = max(range(len(probabilities)), key=probabilities.__getitem__)
        if probabilities[best] >= self.threshold or self.fallback is None:
            label = self.model.classes[best]
            with span("router.classifier", "router", label=label, confidence=probabilities[best]):
                pass
            return RouteDecision(
                specialist=Specialist(label),
                usage=Usage(),
                raw=f"classifier:{label}:{probabilities[best]:.2f}",
            )
        return await route_ticket(self.fallback, ticket, fence=fence)
