import re
from enum import StrEnum

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

_NOT_DONE = re.compile(
    r"\b(will|would|can|could|may|might|if|once|unless|cannot|can't|unable|pending|awaiting|"
    r"approval|approve|review)\b"
)
_NEGATED = re.compile(r"\b(no|not|never|yet|nothing)\b|\w+n't\b")
_REFUND_DONE = (
    re.compile(
        r"\b(i|we)(?:'ve| have| had)?\s+(?:already |just |now )?(?:fully |partially )?"
        r"(?:processed|issued|initiated|refunded|credited)\b"
    ),
    re.compile(r"\b(i|we)(?:'m| am| are)\s+(?:now )?(?:processing|issuing|initiating)\b"),
    re.compile(
        r"\brefund\b.{0,50}\b(?:has|have|had|was|is)\s+(?:now )?(?:been )?(?:fully |partially )?"
        r"(?:processed|issued|initiated|completed|sent)\b"
    ),
    re.compile(
        r"\b(?:has|have|was|were|is)\s+(?:now |been )+(?:fully |partially )?(?:refunded|credited)\b"
    ),
)
_CANCEL_DONE = re.compile(
    r"\b(i|we)(?:'ve| have)?\s+(?:just |now |successfully )?cancel(?:l)?ed\b|"
    r"\bsuccessfully cancel(?:l)?ed\b"
)
_HANDOVER = re.compile(
    r"\b(escalated|forwarded|handed|passed (it|this|your)|referred)\b|"
    r"\b(human|specialist|agent|team|colleague)s?\b.{0,40}\b(follow up|follow-up|contact you|"
    r"be in touch|reach out|take over|take it from here)\b"
)


class Claim(StrEnum):
    REFUND = "refund"
    CANCEL = "cancel"
    HANDOVER = "handover"


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT.split(text.lower()) if s.strip()]


def detect_claims(reply: str) -> set[Claim]:
    """Actions a reply says were taken or are being taken, found with sentence-level patterns."""
    found: set[Claim] = set()
    for sentence in sentences(reply):
        hedged = _NOT_DONE.search(sentence) or _NEGATED.search(sentence)
        if not hedged and any(p.search(sentence) for p in _REFUND_DONE):
            found.add(Claim.REFUND)
        if _CANCEL_DONE.search(sentence):
            found.add(Claim.CANCEL)
        if _HANDOVER.search(sentence):
            found.add(Claim.HANDOVER)
    return found


def unbacked_claims(
    reply: str, *, refunded: bool, cancelled: bool, handed_over: bool
) -> set[Claim]:
    """Claims in the reply that no executed action backs up."""
    backed = {
        Claim.REFUND: refunded,
        Claim.CANCEL: cancelled,
        Claim.HANDOVER: handed_over,
    }
    return {claim for claim in detect_claims(reply) if not backed[claim]}
