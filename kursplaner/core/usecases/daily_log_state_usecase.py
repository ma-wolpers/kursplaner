from __future__ import annotations

from datetime import date

from kursplaner.core.config.app_state_store import load_last_daily_log_date, save_last_daily_log_date


class DailyLogStateUseCase:
    """Kapselt den persistierten Tageszustand für Daily-Logs."""

    @staticmethod
    def last_logged_day() -> date | None:
        """Liefert das zuletzt protokollierte Datum oder `None`."""
        return load_last_daily_log_date()

    def should_log_for_day(self, day: date) -> bool:
        """Prüft, ob für das gegebene Datum ein neues Log erforderlich ist."""
        last = self.last_logged_day()
        return last != day

    @staticmethod
    def mark_logged(day: date) -> None:
        """Markiert das gegebene Datum als erfolgreich protokolliert."""
        save_last_daily_log_date(day)
