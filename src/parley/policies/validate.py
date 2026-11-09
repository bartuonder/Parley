from collections import defaultdict
from datetime import date
from itertools import pairwise

from parley.policies.models import PolicyDoc, Region


def validate_corpus(docs: list[PolicyDoc]) -> list[str]:
    """Return a list of human-readable problems; empty means the corpus is consistent."""
    problems: list[str] = []
    by_id: dict[str, list[PolicyDoc]] = defaultdict(list)
    for doc in docs:
        by_id[doc.doc_id].append(doc)
        if "## " not in doc.body:
            problems.append(f"{doc.key}: body has no '## ' section heading")

    keys = [d.key for d in docs]
    problems += [f"{key}: duplicated" for key in sorted({k for k in keys if keys.count(k) > 1})]

    for doc_id, versions in by_id.items():
        ordered = sorted(versions, key=lambda d: d.version)
        if [d.version for d in ordered] != list(range(1, len(ordered) + 1)):
            problems.append(f"{doc_id}: versions must be consecutive starting at 1")
        for older, newer in pairwise(ordered):
            if newer.effective_date <= older.effective_date:
                problems.append(f"{newer.key}: effective_date must be after {older.key}")
        if len({d.category for d in ordered}) > 1:
            problems.append(f"{doc_id}: category must not change between versions")

    for doc in docs:
        for target in doc.overrides:
            if target == doc.doc_id:
                problems.append(f"{doc.key}: cannot override itself")
            elif target not in by_id:
                problems.append(f"{doc.key}: overrides unknown doc {target}")
    return sorted(problems)


def filename_problems(docs: list[PolicyDoc], filenames: list[str]) -> list[str]:
    expected = {d.filename for d in docs}
    return [f"{name}: does not match its frontmatter" for name in filenames if name not in expected]


def current_docs(
    docs: list[PolicyDoc], as_of: date, region: Region = Region.GLOBAL
) -> list[PolicyDoc]:
    """Latest effective version of each policy that applies to the region on a given date."""
    latest: dict[str, PolicyDoc] = {}
    for doc in docs:
        if doc.effective_date > as_of or not doc.applies_to(region):
            continue
        best = latest.get(doc.doc_id)
        if best is None or doc.version > best.version:
            latest[doc.doc_id] = doc
    return sorted(latest.values(), key=lambda d: d.doc_id)
