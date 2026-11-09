import random
from dataclasses import dataclass
from datetime import UTC, datetime

REFERENCE_NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class SeedConfig:
    seed: int = 42
    now: datetime = REFERENCE_NOW
    n_customers: int = 200
    max_orders_per_customer: int = 5
    history_days: int = 180
    subscription_rate: float = 0.6


def rng_for(cfg: SeedConfig, stream: str) -> random.Random:
    """Independent RNG per stream so one generator never shifts another's output."""
    return random.Random(f"{cfg.seed}:{stream}")
