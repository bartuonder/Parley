from datetime import date

from parley.policies.models import PolicyCategory, Region
from parley.rag.filters import SearchFilter, apply_filters
from parley.rag.models import Chunk


def chunk(
    doc_id: str,
    version: int,
    effective: date,
    expires: date | None = None,
    regions: list[Region] | None = None,
) -> Chunk:
    return Chunk(
        chunk_id=f"{doc_id}@v{version}#0",
        doc_id=doc_id,
        version=version,
        title="t",
        category=PolicyCategory.REFUNDS,
        regions=regions or [Region.GLOBAL],
        effective_date=effective,
        expires_date=expires,
        section="s",
        text="x",
    )


V1 = chunk("POL-REF-001", 1, date(2025, 1, 1))
V2 = chunk("POL-REF-001", 2, date(2025, 9, 1))
V3 = chunk("POL-REF-001", 3, date(2026, 7, 1))
PROMO = chunk("POL-PRM-001", 1, date(2025, 11, 15), date(2025, 12, 31))
EU_ONLY = chunk("POL-REF-008", 1, date(2025, 1, 1), regions=[Region.EU])
ALL = [V1, V2, V3, PROMO, EU_ONLY]
JUNE = date(2026, 6, 1)


def ids(chunks: list[Chunk]) -> list[str]:
    return [c.chunk_id for c in chunks]


def test_no_filter_returns_everything_including_stale_versions() -> None:
    assert apply_filters(ALL, SearchFilter()) == ALL


def test_as_of_keeps_only_the_newest_version_in_force() -> None:
    kept = apply_filters(ALL, SearchFilter(as_of=JUNE))
    assert V2 in kept
    assert V1 not in kept
    assert V3 not in kept


def test_future_versions_become_current_once_effective() -> None:
    kept = apply_filters(ALL, SearchFilter(as_of=date(2026, 7, 1)))
    assert V3 in kept
    assert V2 not in kept


def test_expired_promotions_are_dropped() -> None:
    assert PROMO in apply_filters(ALL, SearchFilter(as_of=date(2025, 12, 31)))
    assert PROMO not in apply_filters(ALL, SearchFilter(as_of=date(2026, 1, 1)))


def test_latest_only_can_be_turned_off_to_keep_older_in_force_versions() -> None:
    kept = apply_filters(ALL, SearchFilter(as_of=JUNE, latest_only=False))
    assert V1 in kept and V2 in kept


def test_region_filter_keeps_global_and_matching_regional_policies() -> None:
    assert EU_ONLY in apply_filters(ALL, SearchFilter(region=Region.EU))
    assert EU_ONLY not in apply_filters(ALL, SearchFilter(region=Region.US))
    assert V2 in apply_filters(ALL, SearchFilter(region=Region.US))


def test_filters_combine() -> None:
    kept = apply_filters(ALL, SearchFilter(as_of=JUNE, region=Region.US))
    assert ids(kept) == [V2.chunk_id]
