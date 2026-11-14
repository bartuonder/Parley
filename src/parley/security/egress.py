import re

from sqlalchemy import select

from parley.db.models import Customer
from parley.security.redact import redact
from parley.security.scan import TOOL_NAMES
from parley.tools.context import ToolContext

FALLBACK_REPLY = "I cannot share that. I can help with your own orders, invoices and subscriptions."

PROMPT_MARKERS = re.compile(
    rf"you are a (?:customer support agent|\w+ specialist)|<<\s*(?:DATA|END)\b|<ticket_body>|"
    rf"untrusted text:|\b(?:{TOOL_NAMES})\b|how to work:|final reply: when you are done",
    re.IGNORECASE,
)
MIN_NAME_LENGTH = 6


def foreign_identifiers(ctx: ToolContext) -> list[str]:
    """Emails and full names of every other customer, so a reply cannot repeat them."""
    rows = ctx.backend.session.execute(
        select(Customer.email, Customer.name).where(Customer.id != ctx.customer_id)
    )
    found: list[str] = []
    for email, name in rows:
        found.append(email)
        if len(name) >= MIN_NAME_LENGTH and " " in name:
            found.append(name)
    return found


def guard_reply(ctx: ToolContext, reply: str) -> tuple[str, list[str]]:
    """Final check of a reply: no prompt or tool internals, no personal data of anyone else."""
    if PROMPT_MARKERS.search(reply):
        return FALLBACK_REPLY, ["prompt_leak"]
    sender = ctx.backend.get_customer(ctx.customer_id).email
    cleaned = redact(reply, keep=[sender], also=foreign_identifiers(ctx))
    return cleaned, (["pii_redacted"] if cleaned != reply else [])
