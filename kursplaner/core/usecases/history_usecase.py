from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

from kursplaner.core.usecases.command_executor_usecase import CommandEntry, CommandExecutorUseCase

TActionResult = TypeVar("TActionResult")


@dataclass(frozen=True)
class HistoryStepResult:
    """Strukturiertes Ergebnis einer Undo/Redo-Operation."""

    applied: bool
    entry: CommandEntry | None
    can_undo: bool
    can_redo: bool


@dataclass(frozen=True)
class RecentUndoEntry:
    """Read-Modell eines Undo-Eintrags für die Verlaufsvorschau."""

    recent_index: int
    label: str


@dataclass(frozen=True)
class UndoToRecentResult:
    """Strukturiertes Ergebnis für Undo bis zu einem Verlaufseintrag."""

    applied_count: int
    last_entry: CommandEntry | None
    can_undo: bool
    can_redo: bool


class HistoryUseCase:
    """Orchestriert undo/redo-verlauf für schreibende Aktionen.

    Die Klasse verwaltet Command-History und delegiert Delta-Anwendung an den Command-Executor.
    """

    def __init__(self, command_executor: CommandExecutorUseCase, *, max_history: int = 30):
        """Initialisiert die Historie mit einem Command-Executor.

        Args:
            command_executor: Executor für Capture/Delta-Anwendung.
            max_history: Maximale Anzahl gespeicherter Command-Einträge.
        """
        self.command_executor = command_executor
        self.max_history = max(1, int(max_history))
        self.undo_stack: list[CommandEntry] = []
        self.redo_stack: list[CommandEntry] = []
        self._is_restoring_history = False

    @property
    def is_restoring_history(self) -> bool:
        """Kennzeichnet, ob gerade ein Undo/Redo-Restore läuft."""
        return self._is_restoring_history

    def can_undo(self) -> bool:
        """Prüft, ob ein Undo-Eintrag vorhanden ist."""
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        """Prüft, ob ein Redo-Eintrag vorhanden ist."""
        return bool(self.redo_stack)

    def capture(self, paths: list[Path]) -> dict[Path, str | None]:
        """Erfasst einen Dateizustand für die übergebenen Pfade."""
        return self.command_executor.capture(paths)

    @staticmethod
    def _merge_state_keys(*states: dict[Path, str | None]) -> list[Path]:
        """Vereinigt Pfadschlüssel aus mehreren Zustands-Snapshots."""
        keys: set[Path] = set()
        for state in states:
            keys.update(state.keys())
        return sorted(keys, key=lambda item: str(item).lower())

    def record(
        self, label: str, before: dict[Path, str | None], *, extra_after: list[Path] | None = None
    ) -> CommandEntry | None:
        """Erzeugt und speichert einen Command-History-Eintrag.

        Args:
            label: Sichtbarer Name der Aktion.
            before: Vorherzustand der relevanten Dateien.
            extra_after: Zusätzliche Pfade, die im Nachherzustand geprüft werden.

        Returns:
            Gespeicherter CommandEntry oder ``None`` bei keiner Änderung.
        """
        if self._is_restoring_history:
            return None

        normalized_before: dict[Path, str | None] = dict(before)
        for path in extra_after or []:
            resolved = path.expanduser().resolve()
            if resolved not in normalized_before:
                normalized_before[resolved] = None

        after = self.capture(self._merge_state_keys(normalized_before) + (extra_after or []))
        if normalized_before == after:
            return None

        entry = self.command_executor.build_entry(label=label, before=normalized_before, after=after)
        if entry is None:
            return None

        self.undo_stack.append(entry)
        if len(self.undo_stack) > self.max_history:
            self.undo_stack = self.undo_stack[-self.max_history :]
        self.redo_stack.clear()
        return entry

    def run_tracked_action(
        self,
        *,
        label: str,
        action: Callable[[], TActionResult],
        before_state: dict[Path, str | None] | None = None,
        capture_before: Callable[[], dict[Path, str | None]] | None = None,
        extra_after: list[Path] | None = None,
        extra_after_from_result: Callable[[TActionResult], list[Path]] | None = None,
    ) -> TActionResult:
        """Führt eine Aktion aus und erzeugt den passenden History-Eintrag.

        Damit bleibt die Capture/Record-Orchestrierung im Use Case statt im Adapter.
        """
        before = before_state
        if before is None:
            if capture_before is None:
                raise RuntimeError("Für run_tracked_action wird before_state oder capture_before benötigt.")
            before = capture_before()

        result = action()
        tracked_after = list(extra_after or [])
        if extra_after_from_result is not None:
            tracked_after.extend(extra_after_from_result(result))
        self.record(label=label, before=before, extra_after=tracked_after)
        return result

    def _apply_entry(self, entry: CommandEntry, *, use_before: bool) -> None:
        """Wendet einen History-Eintrag als Undo oder Redo an."""
        self._is_restoring_history = True
        try:
            self.command_executor.apply_deltas(entry.deltas, use_before=use_before)
        finally:
            self._is_restoring_history = False

    def undo(self) -> CommandEntry | None:
        """Führt ein Undo aus und verschiebt den Eintrag auf den Redo-Stack."""
        if not self.undo_stack:
            return None
        entry = self.undo_stack.pop()
        self._apply_entry(entry, use_before=True)
        self.redo_stack.append(entry)
        return entry

    def redo(self) -> CommandEntry | None:
        """Führt ein Redo aus und verschiebt den Eintrag auf den Undo-Stack."""
        if not self.redo_stack:
            return None
        entry = self.redo_stack.pop()
        self._apply_entry(entry, use_before=False)
        self.undo_stack.append(entry)
        return entry

    def execute_undo(self) -> HistoryStepResult:
        """Führt Undo aus und liefert den aktualisierten History-Zustand."""
        entry = self.undo()
        return HistoryStepResult(
            applied=entry is not None,
            entry=entry,
            can_undo=self.can_undo(),
            can_redo=self.can_redo(),
        )

    def execute_redo(self) -> HistoryStepResult:
        """Führt Redo aus und liefert den aktualisierten History-Zustand."""
        entry = self.redo()
        return HistoryStepResult(
            applied=entry is not None,
            entry=entry,
            can_undo=self.can_undo(),
            can_redo=self.can_redo(),
        )

    def list_recent_undo_entries(self, *, limit: int = 5) -> list[RecentUndoEntry]:
        """Liefert die letzten Undo-Einträge (neueste zuerst) für die GUI."""
        max_items = max(0, int(limit))
        entries: list[RecentUndoEntry] = []
        for idx, entry in enumerate(reversed(self.undo_stack)):
            if idx >= max_items:
                break
            entries.append(RecentUndoEntry(recent_index=idx, label=entry.label))
        return entries

    def execute_undo_to_recent_index(self, *, recent_index: int, limit: int = 5) -> UndoToRecentResult:
        """Führt Undo bis zum gewählten Verlaufseintrag aus.

        `recent_index=0` entspricht dem normalen Undo des neuesten Eintrags.
        """
        entries = self.list_recent_undo_entries(limit=limit)
        if not entries:
            return UndoToRecentResult(
                applied_count=0,
                last_entry=None,
                can_undo=self.can_undo(),
                can_redo=self.can_redo(),
            )

        target = next((item for item in entries if item.recent_index == recent_index), None)
        if target is None:
            return UndoToRecentResult(
                applied_count=0,
                last_entry=None,
                can_undo=self.can_undo(),
                can_redo=self.can_redo(),
            )

        undo_steps = target.recent_index + 1
        applied_count = 0
        last_entry: CommandEntry | None = None
        for _ in range(undo_steps):
            entry = self.undo()
            if entry is None:
                break
            applied_count += 1
            last_entry = entry

        return UndoToRecentResult(
            applied_count=applied_count,
            last_entry=last_entry,
            can_undo=self.can_undo(),
            can_redo=self.can_redo(),
        )
