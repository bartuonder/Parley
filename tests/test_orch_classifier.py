import asyncio
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from parley.agent.ticket import Ticket
from parley.evals.agent_run import Architecture, run_scenario
from parley.evals.loader import load_set
from parley.orchestration.classifier import (
    CLASSES,
    MODEL_PATH,
    ClassifierRouter,
    RouterModel,
    train,
    training_texts,
)
from parley.orchestration.router import Specialist
from tests.fakes import ScriptedLLM, reply_turn

KEYWORDS = {
    "billing": ["refund", "charge"],
    "shipping": ["parcel", "tracking"],
    "subscription": ["plan", "cancel"],
}


class KeywordEmbedder:
    """A stand-in embedder: one dimension per keyword group, no model download."""

    def embed_query(self, text: str) -> list[float]:
        lowered = text.lower()
        vector = [float(sum(w in lowered for w in words)) for words in KEYWORDS.values()]
        return [*vector, 0.1]


def toy_model() -> RouterModel:
    texts = ["refund charge", "parcel tracking", "plan cancel", "refund", "tracking", "cancel plan"]
    labels = ["billing", "shipping", "subscription", "billing", "shipping", "subscription"]
    vectors = [KeywordEmbedder().embed_query(t) for t in texts]
    return train(vectors, labels, "keyword", epochs=300)


def ticket(text: str) -> Ticket:
    return Ticket(id="T", sender_email="a@x.io", subject=text, body=text)


def test_the_training_tickets_are_filled_in_labeled_and_reproducible() -> None:
    texts, labels = training_texts()
    assert len(texts) == len(labels) > 100 and set(labels) == set(CLASSES)
    assert not any("{" in t or "}" in t for t in texts)
    assert training_texts() == (texts, labels) and training_texts(seed=8)[0] != texts


def test_a_trained_model_separates_its_classes_and_gives_probabilities() -> None:
    model = toy_model()
    embedder = KeywordEmbedder()
    for text, expected in [("my parcel tracking", "shipping"), ("cancel my plan", "subscription")]:
        probs = model.probabilities(embedder.embed_query(text))
        assert model.classes[probs.index(max(probs))] == expected
        assert sum(probs) == pytest.approx(1.0)


def test_a_model_survives_a_save_and_load(tmp_path: Path) -> None:
    model = toy_model()
    model.save(tmp_path / "models" / "router.json")
    loaded = RouterModel.load(tmp_path / "models" / "router.json")
    assert loaded == model


def test_a_confident_ticket_is_routed_without_any_model_call() -> None:
    fallback = ScriptedLLM([])
    router = ClassifierRouter(toy_model(), KeywordEmbedder(), threshold=0.5, fallback=fallback)
    decision = asyncio.run(router.route(ticket("refund the charge please")))
    assert decision.specialist == Specialist.BILLING and decision.usage.cost_usd == 0.0
    assert decision.raw.startswith("classifier:billing:") and fallback.requests == []


def test_an_unsure_ticket_goes_to_the_model_router_when_there_is_one() -> None:
    model = toy_model()
    unsure = ticket("hello there")
    fallback = ScriptedLLM([reply_turn("shipping")])
    asked = ClassifierRouter(model, KeywordEmbedder(), threshold=0.99, fallback=fallback)
    decision = asyncio.run(asked.route(unsure))
    assert decision.specialist == Specialist.SHIPPING and len(fallback.requests) == 1
    alone = ClassifierRouter(model, KeywordEmbedder(), threshold=0.99)
    assert asyncio.run(alone.route(unsure)).raw.startswith("classifier:")


def test_the_graph_uses_the_classifier_and_never_calls_the_router_model(session: Session) -> None:
    from tests.fakes import reference_multi_llm

    scenario = next(s for s in load_set("core") if s.id == "SHP-006")
    router_llm = ScriptedLLM([])
    classifier = ClassifierRouter(toy_model(), KeywordEmbedder(), threshold=0.0)
    arch = Architecture(
        name="multi", router_llm_factory=lambda s, i: router_llm, classifier=classifier
    )
    outcome = asyncio.run(
        run_scenario(
            session,
            scenario,
            reference_multi_llm,
            lambda _: None,
            model="m",
            max_steps=8,
            max_cost_usd=1.0,
            arch=arch,
        )
    )
    assert outcome.error is None and outcome.specialist in {s.value for s in Specialist}
    assert router_llm.requests == []


def test_the_committed_model_has_the_expected_shape() -> None:
    model = RouterModel.load(MODEL_PATH)
    assert model.classes == CLASSES and len(model.weights) == 3 and len(model.weights[0]) == 384
    assert model.embedding == "minilm"


@pytest.mark.model
def test_the_committed_model_routes_every_eval_ticket_to_an_accepted_specialist() -> None:
    from parley.orchestration.train_router import EVAL_SETS, accuracy
    from parley.rag.embedders import get_embedder

    scores = accuracy(RouterModel.load(MODEL_PATH), get_embedder("minilm"), threshold=0.0)
    for name in EVAL_SETS:
        assert scores[name][0] == len(load_set(name)), name
