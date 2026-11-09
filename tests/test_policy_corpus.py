from datetime import date

from parley.policies.loader import DEFAULT_POLICY_DIR, load_policies
from parley.policies.models import PolicyDoc
from parley.policies.validate import current_docs, filename_problems, validate_corpus

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
