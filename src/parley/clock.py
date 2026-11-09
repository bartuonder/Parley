from datetime import UTC, datetime

from parley.settings import get_settings


def utcnow() -> datetime:
    """Current time, or the pinned PARLEY_FIXED_NOW when set (used by the synthetic world)."""
    fixed = get_settings().fixed_now
    return fixed if fixed is not None else datetime.now(UTC)
