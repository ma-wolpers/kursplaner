"""Sequenzleiter im Hauptfenster: Einzelinstanz, Sequenzauswahl, Aktualisierung, Netz-Import.

Einziger Ort, der weiß, welche Sequenz das Leiter-Fenster zeigt und woher ihre
Läufe/Termine kommen (`app.topic_sequence_plans`, `app.raw_day_columns`).
`on_sequence_plans_changed` ist der eine Aktualisierungskanal: das
Hauptfenster ruft ihn bei jeder Neuberechnung der Sequenzen (Laden, Grid-Edit,
Undo/Redo, Kurswechsel) über `overview_controller._publish_sequence_plans`.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from bw_gui.dialogs import ChoiceDialogService, ChoiceOption

from kursplaner.adapters.gui.dialog_services import messagebox
from kursplaner.adapters.gui.plan_partial_refresh import refresh_after_files_written
from kursplaner.adapters.gui.sequence_ladder_assign_flow import AssignRungFlow
from kursplaner.adapters.gui.sequence_ladder_controller import LadderContext, SequenceLadderController, TkLadderDialogs
from kursplaner.adapters.gui.sequence_ladder_keys import bind_ladder_keys
from kursplaner.adapters.gui.sequence_ladder_window import SequenceLadderWindow
from kursplaner.core.domain.course_kc_context import CourseKcContext, course_kc_context
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.usecases.day_label_format import short_day_label
from kursplaner.core.usecases.sync_topic_sequence_plans_usecase import TopicSequencePlanView

_NO_SEQUENCE = (
    "Im geöffneten Kurs gibt es noch keine Sequenz – sie entsteht, sobald mindestens zwei "
    "benachbarte Einheiten dasselbe Oberthema tragen."
)


class SequenceLadderHost:
    """Öffnet, aktualisiert und befüllt das (eine) Leiter-Fenster."""

    def __init__(self, app) -> None:
        """Bindet den Host an das Hauptfenster."""
        self.app = app
        self._window: SequenceLadderWindow | None = None
        self._controller: SequenceLadderController | None = None

    # -- Sequenzen des Kurses ----------------------------------------------------

    def _views_by_path(self) -> dict[Path, list[TopicSequencePlanView]]:
        grouped: dict[Path, list[TopicSequencePlanView]] = {}
        for view in self.app.topic_sequence_plans:
            grouped.setdefault(view.sequence_path, []).append(view)
        return grouped

    def _context(self, path: Path) -> LadderContext | None:
        views = self._views_by_path().get(path)
        if not views:
            return None
        return views[0].run.oberthema, [view.run for view in views], list(self.app.raw_day_columns)

    def selected_sequence_path(self) -> Path | None:
        """Sequenz der markierten Spalte (auch ein Ausfall zwischen zwei Mitgliedern zählt)."""
        rows = {
            self.app.day_columns[index].row_index
            for index in self.app.selected_day_indices
            if 0 <= index < len(self.app.day_columns)
        }
        for view in self.app.topic_sequence_plans:
            members = view.run.member_row_indices
            if members and any(min(members) <= row <= max(members) for row in rows):
                return view.sequence_path
        return None

    def choose_sequence(self, *, title: str = "Sequenz wählen") -> Path | None:
        """Sequenzübersicht des geöffneten Kurses; ``None`` bei Abbruch oder ohne Sequenz."""
        grouped = self._views_by_path()
        if not grouped:
            messagebox.showinfo(title, _NO_SEQUENCE, parent=self.app)
            return None
        by_row = {day.row_index: day for day in self.app.raw_day_columns}
        options = []
        for path, views in grouped.items():
            members = sorted(row for view in views for row in view.run.member_row_indices)
            dates = [short_day_label(by_row[row].datum) for row in (members[0], members[-1]) if row in by_row]
            span = f" · {dates[0]} – {dates[-1]}" if dates else ""
            options.append(ChoiceOption(str(path), views[0].run.oberthema, f"{len(members)} Einheiten{span}"))
        key = ChoiceDialogService().askchoice(title, "Welche Sequenz?", options, parent=self.app)
        return Path(key) if key else None

    # -- Fenster -----------------------------------------------------------------

    def _live_window(self) -> SequenceLadderWindow | None:
        """Das offene Leiter-Fenster oder ``None`` (auch nach Schließen durch die Nutzerin)."""
        window = self._window
        return window if window is not None and bool(int(window.winfo_exists())) else None

    def show_for_selection(self) -> None:
        """Strg+Shift+L: Leiter der markierten Sequenz, sonst Auswahl."""
        path = self.selected_sequence_path() or self.choose_sequence()
        if path is not None:
            self.show_for_sequence(path)

    def show_for_sequence(self, path: Path) -> SequenceLadderController:
        """Zeigt die Leiter von *path* (vorhandenes Fenster wird wiederverwendet bzw. neu gebunden)."""
        live = self._live_window()
        if live is not None and self._controller is not None and self._controller.sequence_path == path:
            live.deiconify()
            live.lift()
            return self._controller
        if live is not None:
            live.destroy()
        deps = self.app.gui_dependencies
        window = SequenceLadderWindow(
            self.app, theme_key=self.app.theme_var.get(), on_import_click=self.open_competence_picker
        )
        dialogs = TkLadderDialogs(window)
        controller = SequenceLadderController(
            sequence_path=path,
            load=deps.load_sequence_ladder_usecase,
            edit=deps.edit_sequence_ladder_usecase,
            context=lambda: self._context(path),
            dialogs=dialogs,
            render=window.render,
            after_write=lambda written: refresh_after_files_written(self.app, written),
            assign=AssignRungFlow(
                usecase=deps.assign_ablage_rung_usecase,
                dialogs=dialogs,
                sequence_path=path,
                table=lambda: getattr(self.app, "current_table", None),
            ),
        )
        window.attach(controller)
        bind_ladder_keys(window, window.board, controller, undo=self._undo, redo=self._redo)
        self._window, self._controller = window, controller
        controller.reload()
        window.focus_board()
        return controller

    def _undo(self) -> None:
        """Strg+Z in der Leiter: der Undo-Weg des Hauptfensters veröffentlicht die Sequenzen neu
        und lädt dadurch die Leiter (`on_sequence_plans_changed`) – kein zweites Neuladen hier."""
        self.app.action_controller.undo_history()

    def _redo(self) -> None:
        """Strg+Y in der Leiter: wie `_undo`."""
        self.app.action_controller.redo_history()

    def on_sequence_plans_changed(self) -> None:
        """Sequenzen wurden neu berechnet: offene Leiter neu laden (Termine, Datei, Schreibschutz)."""
        if self._live_window() is not None and self._controller is not None:
            self._controller.reload()

    # -- Kompetenznetz -------------------------------------------------------------

    def open_competence_picker(self) -> None:
        """Öffnet das Kompetenznetz mit dieser Leiter als Übernahme-Ziel."""
        if self._controller is not None:
            target = _LadderTarget(self, self._controller.sequence_path)
            self.app.action_controller.show_kompetenzgraph(import_target=target)

    def free_import_target(self) -> _ChooserTarget:
        """Übernahme-Ziel für ein frei geöffnetes Kompetenznetz: Sequenz erst auswählen."""
        return _ChooserTarget(self)

    def kc_context(self) -> CourseKcContext:
        """KC-Kontext (Bundesland/Schulform) des geöffneten Kurses; ohne Kurs leer."""
        table = getattr(self.app, "current_table", None)
        return course_kc_context(table.metadata) if table is not None else CourseKcContext()

    def import_into(self, path: Path, snapshot: KompetenzGraphSnapshot, kompetenz_ids: Iterable[str]) -> None:
        """Übernimmt Kompetenzen in die Leiter von *path* und zeigt sie."""
        controller = self.show_for_sequence(path)
        controller.import_competences(snapshot, list(kompetenz_ids), self.kc_context())


class _LadderTarget:
    """Übernahme-Ziel: eine bestimmte, aus der Leiter heraus geöffnete Sequenz."""

    def __init__(self, host: SequenceLadderHost, path: Path) -> None:
        self._host, self._path = host, path

    def button_label(self, count: int) -> str:
        """Beschriftung des Übernahme-Knopfs im Kompetenznetz."""
        return f"In Leiter übernehmen ({count})"

    def kc_context(self) -> CourseKcContext:
        """KC-Kontext des Kurses dieser Leiter."""
        return self._host.kc_context()

    def import_ids(self, kompetenz_ids: Iterable[str], snapshot: KompetenzGraphSnapshot) -> None:
        """Übernimmt die markierten Kompetenzen in diese Leiter."""
        self._host.import_into(self._path, snapshot, kompetenz_ids)


class _ChooserTarget:
    """Übernahme-Ziel: Sequenz erst in der Sequenzübersicht wählen."""

    def __init__(self, host: SequenceLadderHost) -> None:
        self._host = host

    def button_label(self, count: int) -> str:
        """Beschriftung des Übernahme-Knopfs im Kompetenznetz."""
        return f"Zu einer Sequenz hinzufügen… ({count})"

    def kc_context(self) -> CourseKcContext:
        """KC-Kontext des geöffneten Kurses (nur dessen Sequenzen sind wählbar)."""
        return self._host.kc_context()

    def import_ids(self, kompetenz_ids: Iterable[str], snapshot: KompetenzGraphSnapshot) -> None:
        """Fragt die Ziel-Sequenz ab und übernimmt dorthin."""
        path = self._host.choose_sequence(title="Zu einer Sequenz hinzufügen")
        if path is not None:
            self._host.import_into(path, snapshot, kompetenz_ids)
