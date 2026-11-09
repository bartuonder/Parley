from datetime import date

from parley.policies.models import PolicyCategory, PolicyDoc, Region
from parley.policies.validate import current_docs, filename_problems, validate_corpus


def doc(
    doc_id: str = "POL-REF-001",
    version: int = 1,
    effective: date = date(2026, 1, 1),
    regions: list[Region] | None = None,
    overrides: list[str] | None = None,
    body: str = "## Rule\n\ntext",
    category: PolicyCategory = PolicyCategory.REFUNDS,
) -> PolicyDoc:
    return PolicyDoc(
        doc_id=doc_id,
        title="A policy",
        version=version,
        effective_date=effective,
        category=category,
        regions=regions or [Region.GLOBAL],
        overrides=overrides or [],
        body=body,
    )


def test_consistent_corpus_has_no_problems() -> None:
    docs = [doc(), doc(version=2, effective=date(2026, 3, 1)), doc("POL-SHP-001")]
    assert validate_corpus(docs) == []


def test_missing_section_heading_is_reported() -> None:
    assert validate_corpus([doc(body="just text")]) == [
        "POL-REF-001@v1: body has no '## ' section heading"
    ]


def test_duplicate_version_is_reported() -> None:
    assert "POL-REF-001@v1: duplicated" in validate_corpus([doc(), doc()])


def test_version_gap_is_reported() -> None:
    problems = validate_corpus([doc(), doc(version=3, effective=date(2026, 3, 1))])
    assert "POL-REF-001: versions must be consecutive starting at 1" in problems


def test_effective_dates_must_increase_with_version() -> None:
    problems = validate_corpus([doc(), doc(version=2, effective=date(2026, 1, 1))])
    assert "POL-REF-001@v2: effective_date must be after POL-REF-001@v1" in problems


def test_category_change_between_versions_is_reported() -> None:
    newer = doc(version=2, effective=date(2026, 3, 1), category=PolicyCategory.BILLING)
    problems = validate_corpus([doc(), newer])
    assert "POL-REF-001: category must not change between versions" in problems


def test_overrides_must_point_to_known_other_docs() -> None:
    problems = validate_corpus(
        [doc(overrides=["POL-REF-001"]), doc("POL-REF-002", overrides=["POL-XXX-999"])]
    )
    assert "POL-REF-001@v1: cannot override itself" in problems
    assert "POL-REF-002@v1: overrides unknown doc POL-XXX-999" in problems


def test_filename_mismatch_is_reported() -> None:
    assert filename_problems([doc()], ["POL-REF-001_v1.md", "wrong.md"]) == [
        "wrong.md: does not match its frontmatter"
    ]


def test_current_docs_picks_latest_effective_version() -> None:
    v1 = doc()
    v2 = doc(version=2, effective=date(2026, 3, 1))
    assert current_docs([v1, v2], date(2026, 2, 1)) == [v1]
    assert current_docs([v1, v2], date(2026, 3, 1)) == [v2]
    assert current_docs([v1, v2], date(2025, 12, 31)) == []


def test_current_docs_filters_by_region() -> None:
    eu_only = doc("POL-REF-002", regions=[Region.EU])
    assert current_docs([eu_only], date(2026, 6, 1), Region.US) == []
    assert current_docs([eu_only], date(2026, 6, 1), Region.EU) == [eu_only]
