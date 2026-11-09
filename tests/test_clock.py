from datetime import UTC, datetime

import pytest

from parley.clock import utcnow
from parley.settings import Settings

DB_URL = "postgresql://user:pw@localhost:5432/parley"


def settings_with(fixed_now: datetime | None) -> Settings:
    return Settings(_env_file=None, database_url=DB_URL, fixed_now=fixed_now)  # type: ignore[call-arg]


def test_utcnow_uses_pinned_time(monkeypatch: pytest.MonkeyPatch) -> None:
    pinned = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    monkeypatch.setattr("parley.clock.get_settings", lambda: settings_with(pinned))
    assert utcnow() == pinned


def test_utcnow_falls_back_to_wall_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("parley.clock.get_settings", lambda: settings_with(None))
    before = datetime.now(UTC)
    assert before <= utcnow() <= datetime.now(UTC)
