from __future__ import annotations

from pathlib import Path
from typing import Callable, TypeVar

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.history_usecase import HistoryUseCase

TActionResult = TypeVar("TActionResult")


class TrackedWriteUseCase:
    """Kapselt Capture/Record-Orchestrierung für schreibende Adapter-Aktionen."""

    def __init__(self, history_usecase: HistoryUseCase):
        """Initialisiert den Orchestrator für nachverfolgbare Schreibaktionen."""
        self.history_usecase = history_usecase

    @staticmethod
    def _to_int(value: object, default: int = -1) -> int:
        """Konvertiert beliebige numerische UI-Werte robust nach `int`."""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                return int(text)
        return default

    @staticmethod
    def _normalize_paths(paths: list[Path] | None) -> list[Path]:
        """Normalisiert optionale Pfadlisten zu expandierten absoluten Pfaden."""
        return [path.expanduser().resolve() for path in (paths or [])]

    def capture_current_state(
        self,
        *,
        table: PlanTableData | None,
        day_columns: list[dict[str, object]],
        selected_day_indices: set[int],
        extra_paths: list[Path] | None = None,
    ) -> dict[Path, str | None]:
        """Erfasst den relevanten Vorherzustand aus Tabelle, Auswahl und Zusatzpfaden."""
        files: list[Path] = []
        if table is not None:
            files.append(table.markdown_path.resolve())
            selected = sorted(idx for idx in selected_day_indices if 0 <= idx < len(day_columns))
            for idx in selected:
                day = day_columns[idx]
                link = day.get("link") if isinstance(day, dict) else None
                if isinstance(link, Path):
                    files.append(link.resolve())

        files.extend(self._normalize_paths(extra_paths))
        return self.history_usecase.capture(files)

    def run_tracked_action(
        self,
        *,
        label: str,
        action: Callable[[], TActionResult],
        table: PlanTableData | None,
        day_columns: list[dict[str, object]],
        selected_day_indices: set[int],
        before_state: dict[Path, str | None] | None = None,
        extra_before: list[Path] | None = None,
        extra_after: list[Path] | None = None,
        extra_after_from_result: Callable[[TActionResult], list[Path]] | None = None,
    ) -> TActionResult:
        """Führt eine Aktion aus und protokolliert Deltas über HistoryUseCase."""
        return self.history_usecase.run_tracked_action(
            label=label,
            action=action,
            before_state=before_state,
            capture_before=lambda: self.capture_current_state(
                table=table,
                day_columns=day_columns,
                selected_day_indices=selected_day_indices,
                extra_paths=extra_before,
            ),
            extra_after=self._normalize_paths(extra_after),
            extra_after_from_result=(
                (lambda item: self._normalize_paths(extra_after_from_result(item)))
                if extra_after_from_result is not None
                else None
            ),
        )
