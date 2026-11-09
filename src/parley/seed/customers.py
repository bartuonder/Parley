from datetime import timedelta

from parley.db.enums import CustomerTier
from parley.db.models import Customer
from parley.seed.catalog import COUNTRY_WEIGHTS, FIRST_NAMES, LAST_NAMES
from parley.seed.config import SeedConfig, rng_for

PREMIUM_RATE = 0.15
MAX_TENURE_DAYS = 730
MIN_TENURE_DAYS = 30


def generate_customers(cfg: SeedConfig) -> list[Customer]:
    rng = rng_for(cfg, "customers")
    countries = [c for c, _ in COUNTRY_WEIGHTS]
    weights = [w for _, w in COUNTRY_WEIGHTS]
    customers: list[Customer] = []
    for i in range(cfg.n_customers):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        tenure_days = rng.randint(MIN_TENURE_DAYS, MAX_TENURE_DAYS)
        tier = CustomerTier.PREMIUM if rng.random() < PREMIUM_RATE else CustomerTier.STANDARD
        customers.append(
            Customer(
                email=f"{first}.{last}.{i + 1}@example.com".lower(),
                name=f"{first} {last}",
                country=rng.choices(countries, weights)[0],
                tier=tier,
                created_at=cfg.now - timedelta(days=tenure_days),
            )
        )
    return customers
