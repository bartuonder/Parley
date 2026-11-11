import pytest

from parley.policies.models import Region
from parley.policies.regions import region_for_country
from parley.seed.catalog import COUNTRY_WEIGHTS


@pytest.mark.parametrize(
    ("country", "region"),
    [("US", Region.US), ("gb", Region.UK), ("DE", Region.EU), ("FR", Region.EU), ("TR", Region.TR)],
)
def test_country_maps_to_policy_region(country: str, region: Region) -> None:
    assert region_for_country(country) == region


def test_unknown_country_has_no_region() -> None:
    assert region_for_country("JP") is None


def test_every_seeded_country_has_a_region() -> None:
    assert all(region_for_country(country) is not None for country, _ in COUNTRY_WEIGHTS)
