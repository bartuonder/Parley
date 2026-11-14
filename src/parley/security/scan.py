import base64
import binascii
import re
import unicodedata
from dataclasses import dataclass, field

TOOL_NAMES = (
    "issue_refund|cancel_subscription|propose_refund|propose_cancel_subscription|"
    "propose_escalation|escalate_to_human|check_refund_eligibility|get_customer_overview|"
    "search_policies"
)

RULES: dict[str, re.Pattern[str]] = {
    "override_instructions": re.compile(
        r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,50}\b(previous|prior|above|earlier|"
        r"all|any|your|the)\b[^.\n]{0,40}\b(instructions?|rules?|polic(?:y|ies)|prompt|"
        r"guidelines?|restrictions?|checks?)\b",
        re.IGNORECASE,
    ),
    "role_marker": re.compile(
        r"(?im)(?:^|[.;!?(\[|])\s*(?:\[\s*|<\s*\|?\s*|#{1,3}\s*)?(?:system|developer|admin(?:istrator)?"
        r"|assistant)\s*(?:\]|\|?\s*>)?\s*(?:notice|message|override|update|prompt|note)?\s*[:>\]]"
        r"|<\|?(?:im_start|im_end|system)\|?>"
    ),
    "addressed_to_assistant": re.compile(
        r"\b(?:notes?|instructions?|commands?)\s+(?:to|for)\s+(?:the\s+)?(?:assistant|"
        r"ai|bot|model)\b",
        re.IGNORECASE,
    ),
    "mode_switch": re.compile(
        r"\b(?:system|admin|developer|maintenance|debug|god|sudo)[\s_-]?(?:override|mode|access)\b"
        r"|\bjailbreak\b|\bdan mode\b|\byou are now\b|\bnew (?:rules|instructions)\b",
        re.IGNORECASE,
    ),
    "tool_command": re.compile(
        rf"\b(?:call|invoke|run|execute|use|trigger)\s+(?:the\s+)?(?:{TOOL_NAMES})\b"
        rf"|\b(?:{TOOL_NAMES})\s*\(",
        re.IGNORECASE,
    ),
    "preapproval": re.compile(
        r"\b(?:pre-?approved|pre-?authori[sz]ed|already approved|approved by (?:management|admin|"
        r"the system|a supervisor))\b",
        re.IGNORECASE,
    ),
    "prompt_extraction": re.compile(
        r"\b(?:reveal|print|show|repeat|output|display|leak|tell me)\b[^.\n]{0,40}\b(?:system "
        r"prompt|your (?:instructions|prompt|rules)|hidden (?:instructions|prompt)|tool list|"
        r"available tools|internal (?:rules|notes))\b",
        re.IGNORECASE,
    ),
    "authority_claim": re.compile(
        r"\b(?:i am|i'm|this is)\s+(?:the\s+|a\s+|your\s+)?(?:regional\s+|store\s+|senior\s+)?"
        r"(?:manager|administrator|admin|ceo|developer|supervisor|owner of this (?:store|platform))"
        r"\b[^.\n]{0,80}\b(?:approv|authori[sz]|override|exception|instruct)",
        re.IGNORECASE,
    ),
    "foreign_language_override": re.compile(
        r"önceki\s+talimat|talimatlar\w?\s+(?:yoksay|unut)|ignoriere?\s+(?:alle\s+)?(?:vorherigen|"
        r"obigen)\s+anweisungen|ignora\s+(?:todas\s+)?las\s+instrucciones|ignore[zr]?\s+(?:toutes\s+)?"
        r"les\s+instructions|игнорируй\s+(?:все\s+)?(?:предыдущие|прежние)",
        re.IGNORECASE,
    ),
}

INVISIBLE = {"Cf", "Co", "Cn"}
HTML_COMMENT = re.compile(r"<!--(.*?)-->", re.DOTALL)
BASE64_RUN = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{24,}={0,2}(?![A-Za-z0-9+/=])")


@dataclass(frozen=True)
class ScanResult:
    flagged: bool
    reasons: list[str] = field(default_factory=list)


def strip_invisible(text: str) -> str:
    """Remove zero-width, bidi and other format characters that hide text from reviewers."""
    return "".join(ch for ch in text if unicodedata.category(ch) not in INVISIBLE or ch in "\n\t")


def _decoded_parts(text: str) -> list[str]:
    parts = [m.group(1) for m in HTML_COMMENT.finditer(text)]
    for run in BASE64_RUN.findall(text):
        try:
            decoded = base64.b64decode(run + "=" * (-len(run) % 4), validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            continue
        if decoded.isprintable() or "\n" in decoded:
            parts.append(decoded)
    return parts


def scan_text(text: str) -> ScanResult:
    """Rule-based check for instructions aimed at the model; hidden parts are scanned too."""
    cleaned = strip_invisible(text)
    hidden = _decoded_parts(cleaned)
    reasons = [name for name, rule in RULES.items() if rule.search(cleaned)]
    reasons += [
        f"hidden_{name}"
        for name, rule in RULES.items()
        if name not in reasons and any(rule.search(part) for part in hidden)
    ]
    return ScanResult(bool(reasons), reasons)
