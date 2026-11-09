from datetime import date

from parley.backend import rules
from parley.policies.loader import DEFAULT_POLICY_DIR, load_policies
from parley.policies.models import PolicyCategory, PolicyDoc
from parley.policies.validate import current_docs, filename_problems, validate_corpus
from parley.seed.catalog import PLAN_PRICES_CENTS

REFERENCE_DATE = date(2026, 6, 1)


def corpus() -> list[PolicyDoc]:
    return load_policies()


def test_corpus_is_internally_consistent() -> None:
    assert validate_corpus(corpus()) == []


def test_filenames_match_frontmatter() -> None:
    names = [p.name for p in DEFAULT_POLICY_DIR.glob("*.md")]
    assert filename_problems(corpus(), names) == []


def test_refund_window_in_force_on_reference_date() -> None:
    in_force = {d.doc_id: d for d in current_docs(corpus(), REFERENCE_DATE)}
    assert in_force["POL-REF-001"].version == 2
    assert "30 days" in in_force["POL-REF-001"].body


def test_future_policy_version_is_not_in_force() -> None:
    future = [d for d in corpus() if d.effective_date > REFERENCE_DATE]
    assert any(d.key == "POL-REF-001@v3" for d in future)
    in_force = {d.key for d in current_docs(corpus(), REFERENCE_DATE)}
    assert "POL-REF-001@v3" not in in_force


def in_force_text(doc_id: str) -> str:
    docs = {d.doc_id: d for d in current_docs(corpus(), REFERENCE_DATE)}
    return docs[doc_id].body


def test_corpus_size_and_category_coverage() -> None:
    docs = corpus()
    assert 30 <= len({d.doc_id for d in docs}) <= 50
    assert {d.category for d in docs} == set(PolicyCategory)


def test_expired_promotion_is_not_in_force() -> None:
    in_force = {d.doc_id for d in current_docs(corpus(), REFERENCE_DATE)}
    assert "POL-PRM-001" not in in_force
    assert "POL-PRM-002" in in_force


def test_in_force_policies_agree_with_backend_rules() -> None:
    assert f"{rules.PHYSICAL_WINDOW_DAYS} days of delivery" in in_force_text("POL-REF-001")
    assert f"{rules.PREMIUM_WINDOW_DAYS} days of delivery" in in_force_text("POL-REF-002")
    assert f"{rules.DIGITAL_WINDOW_DAYS} days of purchase" in in_force_text("POL-REF-004")
    assert f"more than {rules.LOST_GRACE_DAYS} days after" in in_force_text("POL-REF-005")
    assert f"{rules.ANNUAL_COOLING_OFF_DAYS} days of the charge date" in in_force_text(
        "POL-SUB-003"
    )
    assert f"above {rules.APPROVAL_THRESHOLD_CENTS / 100:.2f}" in in_force_text("POL-REF-007")


def test_in_force_prices_agree_with_catalog() -> None:
    text = in_force_text("POL-SUB-001")
    for plan, cents in PLAN_PRICES_CENTS.items():
        assert f"{plan.value.capitalize()} costs {cents / 100:.2f}" in text
