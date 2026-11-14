from typing import Any

from parley.rag.retrieval import Hit, Retriever


class TamperedRetriever(Retriever):
    """A retriever whose index was corrupted: hostile lines are appended to the best hits."""

    def __init__(self, inner: Retriever, lines: list[str]) -> None:
        self.__dict__.update(inner.__dict__)
        self._lines = lines

    def search(self, *args: Any, **kwargs: Any) -> list[Hit]:
        hits = super().search(*args, **kwargs)
        injected = "\n".join(self._lines)
        return [
            hit.model_copy(
                update={
                    "chunk": hit.chunk.model_copy(update={"text": hit.chunk.text + "\n" + injected})
                }
            )
            if position < 2
            else hit
            for position, hit in enumerate(hits)
        ]
