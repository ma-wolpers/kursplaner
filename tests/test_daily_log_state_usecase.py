from __future__ import annotations

from datetime import date

from kursplaner.core.config import app_state_store
from kursplaner.core.usecases.daily_log_state_usecase import DailyLogStateUseCase


def test_daily_log_state_marks_day_and_prevents_duplicate(tmp_path, monkeypatch):
    state_file = tmp_path / "app_state.json"
    monkeypatch.setattr(app_state_store, "_app_state_file", lambda: state_file)

    usecase = DailyLogStateUseCase()
    day = date(2026, 3, 31)

    assert usecase.should_log_for_day(day) is True
    usecase.mark_logged(day)
    assert usecase.should_log_for_day(day) is False


def test_daily_log_state_handles_invalid_json_gracefully(tmp_path, monkeypatch):
    state_file = tmp_path / "app_state.json"
    state_file.write_text("{invalid json", encoding="utf-8")
    monkeypatch.setattr(app_state_store, "_app_state_file", lambda: state_file)

    usecase = DailyLogStateUseCase()
    day = date(2026, 3, 31)

    assert usecase.should_log_for_day(day) is True
    usecase.mark_logged(day)
    assert usecase.should_log_for_day(day) is False
