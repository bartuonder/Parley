from datetime import date
from pathlib import Path

import pytest

from parley.policies.loader import PolicyFormatError, load_policies, parse_policy
from parley.policies.models import PolicyCategory, Region

VALID = """---
doc_id: POL-REF-001
title: Returns for physical goods
version: 2
effective_date: 2026-03-01
category: refunds
regions: [global]
---

## Window

Items can be returned within 30 days of delivery.

---

Horizontal rules in the body are fine.
"""


def test_parse_valid_policy() -> None:
    doc = parse_policy(VALID)
    assert doc.key == "POL-REF-001@v2"
    assert doc.filename == "POL-REF-001_v2.md"
    assert doc.effective_date == date(2026, 3, 1)
    assert doc.category == PolicyCategory.REFUNDS
    assert doc.body.startswith("## Window")
    assert "Horizontal rules" in doc.body


def test_regions_default_to_global() -> None:
    doc = parse_policy(VALID.replace("regions: [global]\n", ""))
    assert doc.regions == [Region.GLOBAL]
    assert doc.applies_to(Region.EU)


def test_regional_policy_applies_only_to_its_regions() -> None:
    doc = parse_policy(VALID.replace("[global]", "[EU, UK]"))
    assert doc.applies_to(Region.EU)
    assert not doc.applies_to(Region.US)


@pytest.mark.parametrize(
    "text",
    [
        "no frontmatter at all",
        "---\n: not: yaml: [\n---\nbody",
        "---\n- a list\n---\nbody",
        VALID.replace("doc_id: POL-REF-001", "doc_id: bad-id"),
        VALID.replace("category: refunds", "category: unknown"),
        VALID.replace("version: 2", "version: 0"),
    ],
)
def test_invalid_policies_raise_format_error(text: str) -> None:
    with pytest.raises(PolicyFormatError):
        parse_policy(text, "x.md")


def test_error_message_names_the_source() -> None:
    with pytest.raises(PolicyFormatError, match=r"broken\.md"):
        parse_policy("nope", "broken.md")


def test_load_policies_reads_sorted_markdown_files(tmp_path: Path) -> None:
    (tmp_path / "POL-REF-001_v2.md").write_text(VALID)
    (tmp_path / "POL-REF-001_v1.md").write_text(VALID.replace("version: 2", "version: 1"))
    (tmp_path / "notes.txt").write_text("ignored")
    assert [d.version for d in load_policies(tmp_path)] == [1, 2]
