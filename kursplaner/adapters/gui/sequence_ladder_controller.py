"""Sequenzleiter-Editor: Cursor, Zwischenablage und Aktionen → Operationen (GUI ohne Fachentscheidung).

Jede Nutzeraktion wird hier zu genau einer Operation (`sequence_ladder_ops`) und
geht über `EditSequenceLadderUseCase` – dem einzigen Schreibweg, der pro Aktion
einen Undo-Eintrag erzeugt (§37). Der Controller kennt kein Tk: Dialoge laufen
über das `LadderDialogs`-Protocol (Adapter `TkLadderDialogs`), die Anzeige über
den `render`-Callback des Fensters. Cursor-Werte sind Board-Cursor (Kartenschlüssel
eines `BlockRef` oder Board-Zelle, siehe `sequence_ladder_board_mapping`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol

from bw_gui.dialogs import ChoiceDialogService, ChoiceOption
from bw_gui.widgets.card_board import BoardCell, BoardSlot, Cursor

from kursplaner.adapters.gui.dialog_services import messagebox, simpledialog
from kursplaner.adapters.gui.sequence_ladder_board_mapping import (
    block_ref,
    board_cell,
    card_key,
    cell_slot,
    initial_cursor,
    ladder_slot,
    rung_index,
    view_hints,
)
from kursplaner.core.domain.course_kc_context import CourseKcContext
from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.sequence_ladder import (
    BlockRef,
    LadderBlock,
    LadderSlot,
    SequenceLadder,
    block_text_error,
    locked_message,
)
from kursplaner.core.domain.sequence_ladder_homes import locked_reason
from kursplaner.core.domain.sequence_ladder_ops import (
    AddBlock,
    LadderOperation,
    MoveBlock,
    RemoveBlock,
    RenameBlock,
    SetIdeas,
    StepBlock,
)
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.usecases.edit_sequence_ladder_usecase import EditSequenceLadderResult, EditSequenceLadderUseCase
from kursplaner.core.usecases.load_sequence_ladder_usecase import LoadSequenceLadderUseCase, SequenceLadderView

LadderContext = tuple[str, Sequence[TopicSequenceRun], Sequence[DayColumn]]
"""(Oberthema, Läufe mit dieser Datei, alle Tagesspalten) – ``None``, wenn die Sequenz im Kurs fehlt."""


class LadderDialogs(Protocol):
    """Dialoge, die der Editor braucht (Tk-frei testbar)."""

    def ask_text(self, title: str, prompt: str, *, initial: str, validate: Callable[[str], str | None]) -> str | None:
        """Fragt einen Text ab; ``None`` bei Abbruch. *validate* hält den Dialog bei Fehlern offen."""
        ...

    def show_error(self, title: str, message: str) -> None:
        """Zeigt einen Fehler."""
        ...

    def show_info(self, title: str, message: str) -> None:
        """Zeigt einen Hinweis."""
        ...

    def choose(self, title: str, prompt: str, options: Sequence[tuple[str, str, str]]) -> str | None:
        """Eine von *options* ``(key, label, description)`` wählen; ``None`` bei Abbruch."""
        ...

    def confirm(self, title: str, message: str) -> bool:
        """Ja/Nein-Rückfrage."""
        ...


class TkLadderDialogs:
    """`LadderDialogs` über die bw-gui-Dialogdienste."""

    def __init__(self, parent: Any) -> None:
        """Bindet die Dialoge an ihr Elternfenster."""
        self._parent = parent

    def ask_text(self, title: str, prompt: str, *, initial: str, validate: Callable[[str], str | None]) -> str | None:
        """Textabfrage mit Validierung (bw-gui `askstring(validate=...)`)."""
        return simpledialog.askstring(title, prompt, initialvalue=initial, validate=validate, parent=self._parent)

    def show_error(self, title: str, message: str) -> None:
        """Fehlermeldung."""
        messagebox.showerror(title, message, parent=self._parent)

    def show_info(self, title: str, message: str) -> None:
        """Hinweis."""
        messagebox.showinfo(title, message, parent=self._parent)

    def choose(self, title: str, prompt: str, options: Sequence[tuple[str, str, str]]) -> str | None:
        """Auswahl als Knopf-Dialog (bw-gui `askchoice`, ein Knopf je Option)."""
        choices = [ChoiceOption(key, label, description) for key, label, description in options]
        return ChoiceDialogService().askchoice(title, prompt, choices, parent=self._parent)

    def confirm(self, title: str, message: str) -> bool:
        """Ja/Nein-Rückfrage (bw-gui `askyesno`)."""
        return bool(messagebox.askyesno(title, message, parent=self._parent))


class SequenceLadderController:
    """Zustand und Aktionen eines geöffneten Leiter-Editors."""

    def __init__(
        self,
        *,
        sequence_path: Path,
        load: LoadSequenceLadderUseCase,
        edit: EditSequenceLadderUseCase,
        context: Callable[[], LadderContext | None],
        dialogs: LadderDialogs,
        render: Callable[[SequenceLadderView, Cursor, str | None], None],
        after_write: Callable[[tuple[Path, ...]], None],
        assign: Callable[[int, LadderContext], EditSequenceLadderResult | None] | None = None,
    ) -> None:
        """Verdrahtet den Editor; `reload()` lädt die erste Ansicht.

        Args:
            sequence_path: Sequenzdatei (Identität der Sequenz).
            load: Lade-Use-Case.
            edit: Einziger Schreibweg.
            context: Liefert Oberthema, Läufe und Tagesspalten des geöffneten Kurses.
            dialogs: Dialog-Adapter.
            render: ``(view, cursor, banner)`` – Anzeige aktualisieren.
            after_write: Nach jedem Schreibvorgang mit den geschriebenen Dateien:
                Hauptfenster **gezielt** aktualisieren (nur Zeilen dieser Einheiten,
                `plan_partial_refresh`); lädt es dabei die Leiter neu, entfällt das
                eigene Neuladen.
            assign: Zuordnen-Ablauf für Ablage-Sprossen (`AssignRungFlow`); ``None`` = nicht verfügbar.
        """
        self.sequence_path = sequence_path
        self._load, self._edit, self._context = load, edit, context
        self._dialogs, self._render, self._after_write = dialogs, render, after_write
        self._assign = assign
        self._oberthema = sequence_path.stem
        self._missing = False
        self._reload_count = 0
        self.view: SequenceLadderView | None = None
        self.cursor: Cursor = None
        self.clipboard: str | None = None

    # -- Laden und Anzeige -----------------------------------------------------

    @property
    def ladder(self) -> SequenceLadder:
        """Aktuelle Leiter (leer, solange nichts geladen oder lesbar ist)."""
        return self.view.ladder if self.view is not None and self.view.ladder is not None else SequenceLadder()

    @property
    def read_only(self) -> bool:
        """Schreibgeschützt bei Formatfehler oder wenn die Sequenz im Kurs nicht mehr vorkommt."""
        return self.view is None or self.view.ladder is None or self._missing

    def reload(self, cursor: Cursor | None = None) -> None:
        """Liest Einheiten, Ablage und Termine neu und zeigt sie an; *cursor* ersetzt den bisherigen."""
        self._reload_count += 1
        context = self._context()
        self._missing = context is None
        if context is not None:
            self._oberthema = context[0]
        oberthema, runs, days = context if context is not None else (self._oberthema, (), ())
        self.view = self._load.execute(
            sequence_path=self.sequence_path, oberthema=oberthema, runs=runs, day_columns=days
        )
        if cursor is not None:
            self.cursor = cursor
        elif self.cursor is None:
            self.cursor = initial_cursor(self.ladder)
        self._show()

    def _show(self) -> None:
        """Zeigt die geladene Ansicht mit dem aktuellen Cursor (ohne neu zu lesen)."""
        if self.view is not None:
            self._render(self.view, self.cursor, self._banner())

    def _banner(self) -> str | None:
        if self.view is not None and self.view.error:
            return self.view.error
        if self._missing:
            return "Diese Sequenz kommt im geöffneten Kurs nicht (mehr) vor – die Leiter ist schreibgeschützt."
        hints = view_hints(self.view) if self.view is not None else ()
        return "\n".join(hints) or None

    def set_cursor(self, cursor: Cursor) -> None:
        """Übernimmt den Cursor nach einem Klick im Board."""
        self.cursor = cursor

    # -- Aktionen --------------------------------------------------------------

    def _writable_context(self) -> LadderContext | None:
        """Aktueller Kontext, wenn geschrieben werden darf; sonst Hinweis und ``None``."""
        context = self._context()
        if self.read_only or context is None:
            self._dialogs.show_info("Sequenzleiter", self._banner() or "Die Leiter ist schreibgeschützt.")
            return None
        return context

    def _run(self, op: LadderOperation, cursor_after: Cursor = None) -> EditSequenceLadderResult | None:
        context = self._writable_context()
        if context is None:
            return None
        _oberthema, runs, days = context
        result = self._edit.execute(sequence_path=self.sequence_path, runs=runs, day_columns=days, operation=op)
        return self._finish(result, cursor_after)

    def _finish(self, result: EditSequenceLadderResult, cursor_after: Cursor) -> EditSequenceLadderResult:
        if result.error:
            self._dialogs.show_error("Sequenzleiter", result.error)
        if result.notes:
            self._dialogs.show_info("Sequenzleiter", "\n".join(result.notes))
        if not result.applied:
            self.reload()
            return result
        self.cursor = card_key(result.focus) if result.focus is not None else cursor_after
        reloads_before = self._reload_count
        self._after_write(result.written)
        if self._reload_count == reloads_before:
            self.reload()
        return result

    def _locked(self, slot: LadderSlot) -> bool:
        """Gesperrte Sprosse: Hinweis statt Texteingabe (Regeltext aus der Domain)."""
        if self.ladder.is_locked(slot.rung):
            kind = (
                self.view.rungs[slot.rung].kind if self.view is not None and slot.rung < len(self.view.rungs) else None
            )
            reason = locked_reason(kind) if kind is not None else ""
            self._dialogs.show_info("Sequenzleiter", locked_message(slot.rung, reason))
            return True
        return False

    def _ask(self, title: str, slot: LadderSlot, initial: str = "", ignore: BlockRef | None = None) -> str | None:
        ladder = self.ladder
        text = self._dialogs.ask_text(
            title,
            "Beschreibung des Bausteins:",
            initial=initial,
            validate=lambda t: block_text_error(t, ladder, side=slot.side, rung=slot.rung, ignore=ignore),
        )
        return text.strip() if text is not None else None

    def _selected(self) -> tuple[BlockRef, LadderSlot, LadderBlock] | None:
        """Gewählter Baustein mit Position, ``None`` ohne Baustein-Auswahl."""
        if not isinstance(self.cursor, str):
            return None
        ref = block_ref(self.cursor)
        found = self.ladder.find(ref)
        return (ref, found[0], found[1]) if found is not None else None

    def _end_slot(self, cell: BoardCell) -> LadderSlot | None:
        """Position unter dem letzten Baustein einer Zelle; ``None`` für die Ideen-Spalte."""
        probe = cell_slot(cell, 0)
        if probe is None:
            return None
        return LadderSlot(probe.rung, probe.side, len(self.ladder.rung(probe.rung).blocks(probe.side)))

    def add(self, cell: BoardCell) -> None:
        """ "+" in einer Zelle: neuen eigenen Baustein unten in der Zelle anlegen."""
        slot = self._end_slot(cell)
        if slot is None or self.read_only or self._locked(slot):
            return
        text = self._ask("Neuer Baustein", slot)
        if text:
            self._run(AddBlock(slot, text))

    def copy(self) -> None:
        """Strg+C: den gewählten Baustein merken."""
        selected = self._selected()
        if selected is not None:
            self.clipboard = selected[2].text

    def paste(self) -> None:
        """Strg+V: Kopie über dem gewählten Baustein (oder in die gewählte Zelle) mit neuem Namen."""
        if self.clipboard is None:
            self._dialogs.show_info("Einfügen", "Erst einen Baustein mit Strg+C kopieren.")
            return
        slot = self._paste_slot()
        if slot is None:
            self._dialogs.show_info("Einfügen", "Erst einen Baustein oder eine Zelle der Leiter wählen.")
            return
        if self._locked(slot):
            return
        text = self._ask("Kopie benennen", slot, initial=self.clipboard)
        if text:
            self._run(AddBlock(slot, text, pasted=True))

    def _paste_slot(self) -> LadderSlot | None:
        if isinstance(self.cursor, str):
            selected = self._selected()
            return selected[1] if selected is not None else None
        if isinstance(self.cursor, BoardCell):
            return self._end_slot(self.cursor)
        return None

    def delete(self) -> None:
        """Entf: gewählten Baustein löschen; danach den Nachbarn in der Zelle wählen."""
        selected = self._selected()
        if selected is None:
            return
        ref, slot, _block = selected
        result = self._run(RemoveBlock(ref), self.cursor)
        if result is not None and result.applied:
            count = len(self.ladder.rung(slot.rung).blocks(slot.side))
            neighbor = self.ladder.ref_at(LadderSlot(slot.rung, slot.side, min(slot.index, count - 1)))
            self.cursor = card_key(neighbor) if neighbor is not None else board_cell(slot)
            self._show()  # Leiter ist nach `_finish` schon frisch; nur den Nachbar-Cursor zeigen

    def rename(self) -> None:
        """F2: eigenen Baustein umbenennen (Netz-Bausteine sind gesperrt)."""
        selected = self._selected()
        if selected is None or self.read_only:
            return
        ref, slot, block = selected
        if block.is_network:
            self._dialogs.show_info("Umbenennen", "Bausteine aus dem Kompetenznetz können nicht umbenannt werden.")
            return
        text = self._ask("Baustein umbenennen", slot, initial=block.text, ignore=ref)
        if text and text != block.text:
            self._run(RenameBlock(ref, text))

    def step(self, up: bool) -> None:
        """Strg+↑/↓: eine Position höher/tiefer (über Sprossengrenzen)."""
        selected = self._selected()
        if selected is not None:
            self._run(StepBlock(selected[0], up), self.cursor)

    def assign_rung(self, row_key: str) -> None:
        """Zuordnen-Knopf einer Ablage-Sprosse: Ablauf (`AssignRungFlow`) und Abschluss wie jede Aktion."""
        context = self._writable_context()
        if context is None or self._assign is None:
            return
        result = self._assign(rung_index(row_key), context)
        if result is not None:
            self._finish(result, self.cursor)

    def drop(self, key: str, slot: BoardSlot) -> None:
        """Drag & Drop: Baustein (Kartenschlüssel *key*) an die angezeigte Einfügelinie verschieben."""
        self._run(MoveBlock(block_ref(key), ladder_slot(slot)), key)

    def commit_ideas(self, cell: BoardCell, text: str) -> None:
        """Ideenfeld einer Sprosse übernehmen (ein Undo-Schritt)."""
        self._run(SetIdeas(rung_index(cell.row_key), tuple(text.splitlines())), cell)

    def import_competences(
        self,
        snapshot: KompetenzGraphSnapshot,
        kompetenz_ids: Iterable[str],
        kc_context: CourseKcContext = CourseKcContext(),
    ) -> None:
        """Markierte Netz-Kompetenzen übernehmen (ein Undo-Schritt; *kc_context* = Kurs der Sequenz)."""
        context = self._writable_context()
        if context is None:
            return
        _oberthema, runs, days = context
        result = self._edit.import_competences(
            sequence_path=self.sequence_path,
            runs=runs,
            day_columns=days,
            snapshot=snapshot,
            kompetenz_ids=kompetenz_ids,
            kc_context=kc_context,
        )
        self._finish(result, self.cursor)
