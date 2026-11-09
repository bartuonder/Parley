from pathlib import Path

import pytest

from parley.seed.static_data import check_static_data

POLICY = """---
doc_id: POL-REF-001
title: Returns
version: 1
effective_date: 2026-01-01
category: refunds
---

## Rule

text
"""


def test_shipped_data_is_consistent() -> None:
    counts = check_static_data()
    assert counts["policy_docs"] >= 30
    assert counts["scenarios"] >= 50


def test_inconsistent_policies_are_reported(tmp_path: Path) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "POL-REF-001_v2.md").write_text(POLICY.replace("version: 1", "version: 2"))
    scenarios = tmp_path / "scenarios"
    scenarios.mkdir()
    with pytest.raises(ValueError, match="consecutive"):
        check_static_data(policies, scenarios)
