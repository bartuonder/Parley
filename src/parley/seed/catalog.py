from dataclasses import dataclass

from parley.db.enums import ItemCategory, SubscriptionPlan


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    category: ItemCategory
    price_cents: int


P, D, F = ItemCategory.PHYSICAL, ItemCategory.DIGITAL, ItemCategory.FINAL_SALE

PRODUCTS: tuple[Product, ...] = (
    Product("HOME-001", "Ceramic desk lamp", P, 4900),
    Product("HOME-002", "Linen throw blanket", P, 5900),
    Product("HOME-003", "Stoneware mug set", P, 3400),
    Product("HOME-004", "Bamboo shelf organizer", P, 2900),
    Product("HOME-005", "Scented candle trio", P, 2400),
    Product("TECH-001", "Wireless charging pad", P, 2900),
    Product("TECH-002", "Noise-cancelling headphones", P, 14900),
    Product("TECH-003", "Mechanical keyboard", P, 11900),
    Product("TECH-004", "USB-C hub 7-in-1", P, 4500),
    Product("TECH-005", "Portable SSD 1TB", P, 8900),
    Product("TECH-006", "Webcam 1080p", P, 5900),
    Product("WEAR-001", "Merino wool sweater", P, 8900),
    Product("WEAR-002", "Trail running shoes", P, 11000),
    Product("WEAR-003", "Waterproof jacket", P, 12900),
    Product("WEAR-004", "Cotton t-shirt 3-pack", P, 3900),
    Product("WEAR-005", "Leather belt", P, 3500),
    Product("FIT-001", "Yoga mat", P, 3200),
    Product("FIT-002", "Adjustable dumbbell pair", P, 15900),
    Product("FIT-003", "Resistance band kit", P, 1900),
    Product("KIT-001", "Cast iron skillet", P, 4500),
    Product("KIT-002", "Chef knife 8 inch", P, 7900),
    Product("KIT-003", "Pour-over coffee set", P, 5400),
    Product("DIG-001", "Photo editing preset pack", D, 1900),
    Product("DIG-002", "Productivity planner (PDF)", D, 1200),
    Product("DIG-003", "Language course, annual access", D, 8900),
    Product("DIG-004", "Stock music license", D, 4900),
    Product("CLR-001", "Clearance fleece vest", F, 1900),
    Product("CLR-002", "Clearance travel mug", F, 900),
    Product("CLR-003", "Engraved leather wallet", F, 3900),
    Product("CLR-004", "Custom-print tote bag", F, 2200),
)

CARRIERS: tuple[tuple[str, str], ...] = (
    ("DHL", "DH"),
    ("UPS", "1Z"),
    ("FedEx", "FX"),
    ("Royal Mail", "RM"),
    ("Aras Kargo", "AR"),
)

COUNTRY_CURRENCY: dict[str, str] = {
    "US": "USD",
    "CA": "USD",
    "GB": "GBP",
    "DE": "EUR",
    "FR": "EUR",
    "TR": "USD",
}

COUNTRY_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("US", 40),
    ("GB", 20),
    ("DE", 15),
    ("FR", 10),
    ("CA", 10),
    ("TR", 5),
)

PLAN_PRICES_CENTS: dict[SubscriptionPlan, int] = {
    SubscriptionPlan.BASIC: 900,
    SubscriptionPlan.PRO: 1900,
    SubscriptionPlan.TEAM: 4900,
}

ANNUAL_DISCOUNT_MONTHS = 10

FIRST_NAMES = (
    "Ada", "Alan", "Grace", "Linus", "Margaret", "Dennis", "Barbara", "Ken", "Radia", "Edsger",
    "Hedy", "Tim", "Katherine", "Donald", "Frances", "Guido", "Sophie", "Yusuf", "Elif", "Mehmet",
    "Zeynep", "Lukas", "Hannah", "Jonas", "Chloe", "Louis", "Emma", "Noah", "Olivia", "Liam",
)  # fmt: skip

LAST_NAMES = (
    "Lovelace", "Turing", "Hopper", "Torvalds", "Hamilton", "Ritchie", "Liskov", "Thompson",
    "Perlman", "Dijkstra", "Lamarr", "Berners", "Johnson", "Knuth", "Allen", "Rossum", "Germain",
    "Kaya", "Demir", "Yilmaz", "Schmidt", "Weber", "Fischer", "Martin", "Bernard", "Smith",
    "Brown", "Wilson", "Taylor", "Clark",
)  # fmt: skip
