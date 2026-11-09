"""Übernahme-Leiste des Kompetenznetz-Popups: markieren, Markierung aufheben, übernehmen.

Das Popup kennt kein Ziel selbst, nur das `CompetenceImportTarget`-Protocol:
aus einer Sequenzleiter geöffnet übernimmt es „in diese Leiter“, frei geöffnet
fragt es die Sequenz in der Sequenzübersicht ab (beides in
`sequence_ladder_host.py`). Ein bereits offenes Popup wird über `set_target`
umgebunden, Filter und Markierung bleiben erhalten. Markierbar ist nur, was in
eine Leiter des Ziel-Kurses übernommen werden kann (`ladder_import_problem` mit
dem KC-Kontext des Ziels) – inhaltsbezogene Hauptkompetenzen werden übergangen.

Sind Kompetenzen mit Inhalts- **und** Prozessbereich markiert
(`sequence_ladder_import.mixed_side_ids`), fragt „Übernehmen“ vorher, in welche
Spalte diese kommen (`ask_mixed_side`); die übrigen folgen ihrem Primärbereich.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol

from bw_gui.dialogs import ChoiceDialogService, ChoiceOption
from bw_gui.runtime import widgets
from bw_gui.widgets import HoverTooltip

from kursplaner.adapters.gui.help_catalog import KOMPETENZGRAPH_HELP
from kursplaner.adapters.gui.kompetenzgraph_marking import clear_marks, mark_visible, toggle_mark
from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState
from kursplaner.adapters.gui.sequence_ladder_board_mapping import side_title
from kursplaner.core.domain.course_kc_context import CourseKcContext
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_view import KompetenzGraphView
from kursplaner.core.domain.sequence_ladder import COMPETENCE_SIDES, LadderSide
from kursplaner.core.domain.sequence_ladder_import import ladder_import_problem, mixed_side_ids


def ask_mixed_side(parent, mixed: int, total: int) -> LadderSide | None:
    """Fragt die Spalte für *mixed* von *total* markierten Kompetenzen mit Inhalts- und Prozessbereich.

    Returns:
        Die gewählte Spalte oder ``None`` bei Abbruch (dann wird nichts übernommen).
    """
    which = (
        "Alle markierten Kompetenzen gehören"
        if mixed == total
        else f"{mixed} der {total} markierten Kompetenzen gehören"
    )
    rest = "" if mixed == total else " Die übrigen kommen wie gewohnt in die Spalte ihres Bereichs."
    options = [
        ChoiceOption(side.value, side_title(side), f"Spalte {number}")
        for number, side in enumerate(COMPETENCE_SIDES, start=1)
    ]
    key = ChoiceDialogService().askchoice(
        "Spalte wählen",
        f"{which} zu einem Inhalts- und einem Prozessbereich. In welche Spalte sollen sie?{rest}",
        options,
        parent=parent,
    )
    return LadderSide(key) if key else None


class CompetenceImportTarget(Protocol):
    """Wohin markierte Kompetenzen übernommen werden."""

    def button_label(self, count: int) -> str:
        """Beschriftung des Übernahme-Knopfs für *count* markierte Kompetenzen."""
        ...

    def import_ids(
        self, kompetenz_ids: Iterable[str], snapshot: KompetenzGraphSnapshot, mixed_side: LadderSide | None = None
    ) -> None:
        """Übernimmt die Kompetenzen (ein Undo-Schritt in der Ziel-Leiter).

        *mixed_side*: gewählte Spalte für Kompetenzen mit Inhalts- und Prozessbereich
        (``None`` = Spalte des Primärbereichs).
        """
        ...

    def kc_context(self) -> CourseKcContext:
        """KC-Kontext (Bundesland/Schulform) des Ziel-Kurses; bestimmt, was markierbar ist."""
        ...


class KompetenzGraphImportBar:
    """Knöpfe der Übernahme; hält das Ziel und aktualisiert Beschriftung/Zustand."""

    def __init__(
        self,
        parent,
        *,
        state: KompetenzGraphUiState,
        snapshot: KompetenzGraphSnapshot,
        current_view: Callable[[], KompetenzGraphView | None],
        on_marks_changed: Callable[[], None],
        target: CompetenceImportTarget | None,
    ) -> None:
        """Baut die Leiste rechts in *parent*.

        Args:
            parent: Werkzeugleiste des Popups.
            state: UI-Zustand (enthält `marked_ids`).
            snapshot: Geladenes Kompetenznetz.
            current_view: Liefert die zuletzt gezeigte Ansicht (für „Alle gefilterten markieren“).
            on_marks_changed: Neu zeichnen nach Markierungsänderungen.
            target: Übernahme-Ziel (``None`` = Übernahme nicht möglich).
        """
        self._state, self._snapshot = state, snapshot
        self._current_view, self._on_marks_changed = current_view, on_marks_changed
        self._target = target
        self._frame = frame = widgets.Frame(parent)
        frame.pack(side="right")
        self._import_button = widgets.Button(frame, text="", command=self.do_import)
        self._import_button.pack(side="right", padx=(6, 0))
        clear_button = widgets.Button(frame, text="Markierung aufheben", command=self.clear)
        clear_button.pack(side="right", padx=(6, 0))
        mark_button = widgets.Button(frame, text="Alle gefilterten markieren", command=self.mark_visible)
        mark_button.pack(side="right")
        self._tooltips = [
            HoverTooltip(mark_button, KOMPETENZGRAPH_HELP["mark_visible"]),
            HoverTooltip(self._import_button, KOMPETENZGRAPH_HELP["import_marked"]),
        ]
        self.refresh()

    def set_target(self, target: CompetenceImportTarget | None) -> None:
        """Bindet ein neues Übernahme-Ziel (z. B. beim erneuten Öffnen aus einer Leiter)."""
        self._target = target
        self.refresh()

    def toggle(self, node_id: str) -> None:
        """Strg+Klick/Leertaste auf einer Kompetenz."""
        toggle_mark(self._state, self._snapshot, node_id, self._markable)
        self._changed()

    def mark_visible(self) -> None:
        """Alle aktuellen Filtertreffer markieren."""
        view = self._current_view()
        if view is not None:
            mark_visible(self._state, self._snapshot, view, self._markable)
            self._changed()

    def _markable(self, node_id: str) -> bool:
        context = self._target.kc_context() if self._target is not None else CourseKcContext()
        return ladder_import_problem(self._snapshot, node_id, context) is None

    def clear(self) -> None:
        """Alle Markierungen aufheben."""
        clear_marks(self._state)
        self._changed()

    def do_import(self) -> None:
        """Übernimmt die Markierung ins Ziel (Reihenfolge nach ID, deterministisch).

        Bei Kompetenzen mit Inhalts- und Prozessbereich wird vorher die Spalte
        erfragt; Abbrechen übernimmt nichts.
        """
        if self._target is None or not self._state.marked_ids:
            return
        ids = sorted(self._state.marked_ids)
        mixed = mixed_side_ids(self._snapshot, ids, self._target.kc_context())
        side = ask_mixed_side(self._frame, len(mixed), len(ids)) if mixed else None
        if mixed and side is None:
            return
        self._target.import_ids(ids, self._snapshot, side)

    def _changed(self) -> None:
        self.refresh()
        self._on_marks_changed()

    def refresh(self) -> None:
        """Knopf-Beschriftung und -Zustand aus Ziel und Anzahl."""
        count = len(self._state.marked_ids)
        label = self._target.button_label(count) if self._target is not None else f"Übernehmen ({count})"
        enabled = self._target is not None and count > 0
        self._import_button.configure(text=label, state="normal" if enabled else "disabled")
