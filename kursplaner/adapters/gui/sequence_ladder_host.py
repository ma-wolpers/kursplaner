"""Sequenzleiter-Ansicht im Hauptfenster: gezeigte Sequenz, Auswahl-Sync, Aktualisierung, Netz-Import.

Einziger Ort, der weiß, welche Sequenz die Leiter-Oberfläche zeigt
(`controller.sequence_path`, auch „zuletzt gezeigt“) und woher ihre Läufe/Termine kommen
(`app.topic_sequence_plans`, `app.raw_day_columns`). Ein- und ausgeblendet wird die
Oberfläche nur von `MainViewSwitcher`, der beim Einblenden `on_shown` ruft.
`on_sequence_plans_changed` ist der eine Aktualisierungskanal: das Hauptfenster ruft ihn
bei jeder Neuberechnung der Sequenzen (Laden, Grid-Edit, Undo/Redo, Kurswechsel) über
`overview_controller._publish_sequence_plans`.

Auswahl: die Spaltenauswahl des Grids ist die eine Quelle. Beim Einblenden steht der
Cursor auf der Sprosse der markierten Spalte; jede Cursorbewegung auf eine Termin-Sprosse
markiert deren Spalte (`select_row`).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from bw_gui.dialogs import ChoiceDialogService, ChoiceOption
from bw_gui.widgets.card_board import Cursor

from kursplaner.adapters.gui.detail_surface import DetailSurface
from kursplaner.adapters.gui.dialog_services import messagebox
from kursplaner.adapters.gui.plan_partial_refresh import refresh_after_files_written
from kursplaner.adapters.gui.sequence_choices import SequenceChoice, sequence_choices, views_by_path
from kursplaner.adapters.gui.sequence_ladder_assign_flow import AssignRungFlow
from kursplaner.adapters.gui.sequence_ladder_board_mapping import cursor_rung, rung_cursor
from kursplaner.adapters.gui.sequence_ladder_controller import LadderContext, SequenceLadderController, TkLadderDialogs
from kursplaner.adapters.gui.sequence_ladder_keys import bind_ladder_keys
from kursplaner.adapters.gui.sequence_ladder_panel import SequenceLadderPanel
from kursplaner.core.domain.course_kc_context import CourseKcContext, course_kc_context
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.sequence_ladder import LadderSide
from kursplaner.core.usecases.load_sequence_ladder_usecase import sequence_term_days

_NO_SEQUENCE = (
    "Im geöffneten Kurs gibt es noch keine Sequenz – sie entsteht, sobald mindestens zwei "
    "benachbarte Einheiten dasselbe Oberthema tragen."
)


class SequenceLadderHost:
    """Bindet, aktualisiert und befüllt die (eine) Leiter-Oberfläche."""

    def __init__(self, app) -> None:
        """Bindet den Host an das Hauptfenster; die Oberfläche kommt über `attach_panel`."""
        self.app = app
        self._panel: SequenceLadderPanel | None = None
        self._controller: SequenceLadderController | None = None

    # -- Sequenzen des Kurses ----------------------------------------------------

    def sequence_choices(self) -> list[SequenceChoice]:
        """Sequenzen des geöffneten Kurses (Dialog und Auswahlliste lesen nur hier)."""
        return sequence_choices(self.app.topic_sequence_plans, self.app.raw_day_columns)

    def _context(self, path: Path) -> LadderContext | None:
        views = views_by_path(self.app.topic_sequence_plans).get(path)
        if not views:
            return None
        return views[0].run.oberthema, [view.run for view in views], list(self.app.raw_day_columns)

    def _selected_rows(self) -> set[int]:
        """Plan-Zeilen der markierten Spalten (die Spaltenauswahl ist die eine Auswahlquelle)."""
        return {
            self.app.day_columns[index].row_index for index in self.app.selection_controller.selected_indices_sorted()
        }

    def selected_sequence_path(self) -> Path | None:
        """Sequenz der markierten Spalte (auch ein Ausfall zwischen zwei Mitgliedern zählt)."""
        rows = self._selected_rows()
        for view in self.app.topic_sequence_plans:
            if any(view.run.covers(row) for row in rows):
                return view.sequence_path
        return None

    def choose_sequence(self, *, title: str = "Sequenz wählen") -> Path | None:
        """Sequenzübersicht des geöffneten Kurses; ``None`` bei Abbruch oder ohne Sequenz."""
        choices = self.sequence_choices()
        if not choices:
            messagebox.showinfo(title, _NO_SEQUENCE, parent=self.app)
            return None
        options = [ChoiceOption(str(choice.path), choice.title, choice.detail) for choice in choices]
        key = ChoiceDialogService().askchoice(title, "Welche Sequenz?", options, parent=self.app)
        return Path(key) if key else None

    # -- Oberfläche ---------------------------------------------------------------

    def attach_panel(self, panel: SequenceLadderPanel) -> None:
        """Verbindet die (einmal gebaute) Leiter-Oberfläche und bindet ihre Tasten."""
        self._panel = panel
        bind_ladder_keys(panel.board, lambda: self._controller, self.move_cursor)

    @property
    def controller(self) -> SequenceLadderController | None:
        """Controller der gezeigten Sequenz (``None`` ohne Sequenz)."""
        return self._controller

    def _visible(self) -> bool:
        return bool(getattr(self.app, "is_detail_view", False)) and (
            self.app.ui_state.detail_surface is DetailSurface.LADDER
        )

    def resolve_sequence(self) -> Path | None:
        """Sequenz beim Einblenden: markierte Spalte → zuletzt gezeigte (falls im Kurs) → erste."""
        paths = [choice.path for choice in self.sequence_choices()]
        shown = self._controller.sequence_path if self._controller is not None else None
        for candidate in (self.selected_sequence_path(), shown):
            if candidate in paths:
                return candidate
        return paths[0] if paths else None

    def on_shown(self, path: Path | None = None) -> None:
        """Leiter wurde eingeblendet (`MainViewSwitcher`): Sequenz binden, Cursor auf die markierte Spalte."""
        self._show(path or self.resolve_sequence(), from_selection=True)
        if self._panel is not None:
            self._panel.focus_board()

    def show_for_sequence(self, path: Path) -> SequenceLadderController | None:
        """Zeigt die Leiter von *path* (schaltet die Leiter-Ansicht ein, falls nötig)."""
        if self._visible():
            self._show(path, from_selection=False)
        else:
            self.app.main_view_switcher.show_surface(DetailSurface.LADDER, sequence=path)
        return self._controller

    def _show(self, path: Path | None, *, from_selection: bool) -> None:
        panel = self._panel
        if panel is None:
            return
        panel.set_choices(self.sequence_choices(), path)
        if path is None:
            self._controller = None
            panel.attach(None)
            panel.show_empty(_NO_SEQUENCE)
            return
        if self._controller is None or self._controller.sequence_path != path:
            self._controller = self._new_controller(path, panel)
            panel.attach(self._controller)
        self._controller.reload(self._selection_cursor(path) if from_selection else None)

    def _new_controller(self, path: Path, panel: SequenceLadderPanel) -> SequenceLadderController:
        deps = self.app.gui_dependencies
        dialogs = TkLadderDialogs(self.app)
        return SequenceLadderController(
            sequence_path=path,
            load=deps.load_sequence_ladder_usecase,
            edit=deps.edit_sequence_ladder_usecase,
            context=lambda: self._context(path),
            dialogs=dialogs,
            text_input=panel,
            render=panel.render,
            after_write=lambda written: refresh_after_files_written(self.app, written),
            assign=AssignRungFlow(
                usecase=deps.assign_ablage_rung_usecase,
                dialogs=dialogs,
                sequence_path=path,
                table=lambda: getattr(self.app, "current_table", None),
            ),
        )

    def _selection_cursor(self, path: Path) -> Cursor:
        """Cursor auf die Sprosse der markierten Spalte (``None``: Standardcursor des Controllers).

        Die Sprossen-Position kommt aus `sequence_term_days` – derselben Regel, nach der
        die Leiter ihre Termine bildet.
        """
        context = self._context(path)
        if context is None:
            return None
        _oberthema, runs, days = context
        rows = self._selected_rows()
        for index, day in enumerate(sequence_term_days(days, runs)):
            if day.row_index in rows:
                return rung_cursor(index)
        return None

    def move_cursor(self, cursor: Cursor) -> None:
        """Einziger Cursor-Weg (Klick und Pfeiltaste): Controller und Spaltenauswahl folgen."""
        controller = self._controller
        if controller is None:
            return
        controller.set_cursor(cursor)
        rung = cursor_rung(cursor)
        view = controller.view
        if view is not None and rung is not None and 0 <= rung < len(view.rungs):
            row = view.rungs[rung].row_index
            if row is not None:
                self.app.selection_controller.select_row(row)

    def on_sequence_plans_changed(self) -> None:
        """Sequenzen wurden neu berechnet: sichtbare Leiter aktualisieren (verborgen: beim Einblenden)."""
        if not self._visible():
            return
        paths = [choice.path for choice in self.sequence_choices()]
        shown = self._controller.sequence_path if self._controller is not None else None
        self._show(shown if shown in paths else self.resolve_sequence(), from_selection=False)

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

    def import_into(
        self,
        path: Path,
        snapshot: KompetenzGraphSnapshot,
        kompetenz_ids: Iterable[str],
        mixed_side: LadderSide | None = None,
    ) -> None:
        """Übernimmt Kompetenzen in die Leiter von *path* und zeigt sie (*mixed_side* siehe `CompetenceImportTarget`)."""
        controller = self.show_for_sequence(path)
        if controller is not None:
            controller.import_competences(snapshot, list(kompetenz_ids), self.kc_context(), mixed_side)


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

    def import_ids(
        self, kompetenz_ids: Iterable[str], snapshot: KompetenzGraphSnapshot, mixed_side: LadderSide | None = None
    ) -> None:
        """Übernimmt die markierten Kompetenzen in diese Leiter."""
        self._host.import_into(self._path, snapshot, kompetenz_ids, mixed_side)


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

    def import_ids(
        self, kompetenz_ids: Iterable[str], snapshot: KompetenzGraphSnapshot, mixed_side: LadderSide | None = None
    ) -> None:
        """Fragt die Ziel-Sequenz ab und übernimmt dorthin."""
        path = self._host.choose_sequence(title="Zu einer Sequenz hinzufügen")
        if path is not None:
            self._host.import_into(path, snapshot, kompetenz_ids, mixed_side)
