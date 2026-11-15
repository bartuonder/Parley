from parley.evals.loader import SCENARIO_SETS, load_set
from parley.orchestration.classifier import (
    MODEL_PATH,
    Embedder,
    RouterModel,
    train,
    training_texts,
)
from parley.orchestration.router import ACCEPTED_SPECIALISTS, Specialist
from parley.rag.embedders import get_embedder
from parley.rag.service import DEFAULT_EMBEDDING

EVAL_SETS = ("core", "heldout", "dialogue", "memory")


def accuracy(
    model: RouterModel, embedder: Embedder, threshold: float
) -> dict[str, tuple[int, int]]:
    """Per eval set: tickets sent to an accepted specialist, and tickets below the threshold."""
    result: dict[str, tuple[int, int]] = {}
    for name in EVAL_SETS:
        right = unsure = 0
        for s in load_set(name):
            probabilities = model.probabilities(
                embedder.embed_query(f"{s.ticket.subject}\n{s.ticket.body}")
            )
            best = max(range(len(probabilities)), key=probabilities.__getitem__)
            if probabilities[best] < threshold:
                unsure += 1
            right += Specialist(model.classes[best]) in ACCEPTED_SPECIALISTS[s.category.value]
        result[name] = (right, unsure)
    return result


def main() -> None:
    embedder = get_embedder(DEFAULT_EMBEDDING)
    texts, labels = training_texts()
    vectors = [embedder.embed_query(t) for t in texts]
    model = train(vectors, labels, DEFAULT_EMBEDDING)
    model.save()
    print(f"trained on {len(texts)} synthetic tickets, saved to {MODEL_PATH}")
    for threshold in (0.0, 0.5, 0.6, 0.7):
        scores = accuracy(model, embedder, threshold)
        line = ", ".join(
            f"{name} {right}/{len(load_set(name))} ({unsure} unsure)"
            for name, (right, unsure) in scores.items()
        )
        print(f"threshold {threshold}: {line}")
    assert set(EVAL_SETS) <= set(SCENARIO_SETS)


if __name__ == "__main__":
    main()
