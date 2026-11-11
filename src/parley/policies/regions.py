from parley.policies.models import Region

COUNTRY_REGIONS: dict[str, Region] = {
    "US": Region.US,
    "CA": Region.CA,
    "GB": Region.UK,
    "DE": Region.EU,
    "FR": Region.EU,
    "TR": Region.TR,
}


def region_for_country(country: str) -> Region | None:
    """Policy region for a customer country, or None when no regional policy is known."""
    return COUNTRY_REGIONS.get(country.upper())
