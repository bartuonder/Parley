import re
from collections.abc import Iterable
from dataclasses import dataclass

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
PHONE = re.compile(
    r"(?<![\w-])(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s.-]\d{3,4}[\s.-]\d{3,4}(?!\d)"
)
CARD = re.compile(r"(?<![\w-])(?:\d[ -]?){12,18}\d(?!\d)")


@dataclass(frozen=True)
class Finding:
    kind: str
    value: str


def luhn_ok(digits: str) -> bool:
    total = 0
    for position, char in enumerate(reversed(digits)):
        n = int(char)
        if position % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def _cards(text: str) -> list[str]:
    found = []
    for match in CARD.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if 13 <= len(digits) <= 19 and luhn_ok(digits):
            found.append(match.group(0))
    return found


def find_pii(text: str) -> list[Finding]:
    """Emails, phone numbers and card numbers in a text, in the order of their kind."""
    findings = [Finding("email", m.group(0)) for m in EMAIL.finditer(text)]
    findings += [Finding("card", value) for value in _cards(text)]
    card_values = {f.value for f in findings if f.kind == "card"}
    findings += [
        Finding("phone", m.group(0))
        for m in PHONE.finditer(text)
        if m.group(0) not in card_values and not luhn_ok(re.sub(r"\D", "", m.group(0)))
    ]
    return findings


def redact(text: str, keep: Iterable[str] = (), also: Iterable[str] = ()) -> str:
    """Mask personal data except values in `keep`; strings in `also` are masked as well."""
    allowed = {k.lower() for k in keep}
    for finding in find_pii(text):
        if finding.value.lower() not in allowed:
            text = text.replace(finding.value, f"[{finding.kind} removed]")
    for extra in also:
        if extra and extra.lower() not in allowed:
            text = re.sub(re.escape(extra), "[personal data removed]", text, flags=re.IGNORECASE)
    return text
