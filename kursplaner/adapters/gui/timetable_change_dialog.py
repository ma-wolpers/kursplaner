from __future__ import annotations

import copy
import dataclasses
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets
from bw_gui.theming import tinted_color

from kursplaner.adapters.gui.dialog_services import messagebox, simpledialog
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.adapters.gui.weekday_rhythm_picker import WeekdayRhythmPicker
from kursplaner.core.domain.course_rhythm import RHYTHM_YAML_KEY, WeekdayRhythm, parse_rhythm
from kursplaner.core.domain.plan_table import PlanTableData, extract_plan_oberthema, parse_plan_row_date
from kursplaner.core.domain.validators import ValidationError, normalize_day_rhythm
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.usecases.timetable_change_usecase import (
    DraftSlot,
    TimetableChangeUseCase,
    column_is_manual_ausfall,
    column_is_stattfindend,
)


class TimetableChangeDialog(ScrollablePopupWindow):
    """Splitansicht-Dialog für die Umverteilung eines Kursplans auf einen neuen Stundenplan.

    Linke Seite: Bisheriger Plan im gewählten Zeitraum (Lesemodus).
    Rechte Seite: Entwurf des neuen Plans, editierbar durch Slot-Aktionen und Strg+Z.
    Klick auf "Übernehmen" ruft ``on_accept`` mit den endgültigen Draft-Slots auf.
    """

    def __init__(
        self,
        master,
        *,
        table: PlanTableData,
        day_columns: list[dict[str, object]],
        calendar_dir: Path,
        timetable_change_uc: TimetableChangeUseCase,
        on_accept: Callable[[date, date, list[DraftSlot], tuple[WeekdayRhythm, ...]], None],
        theme_key: str | None = None,
    ) -> None:
        """Öffnet den Dialog und baut die UI auf.

        Args:
            master: Elternfenster.
            table: Geladene Planungstabelle (Quelldaten und Datumsbereich).
            day_columns: Aufbereitete Tagespalten der Hauptansicht (für Altplan-Filterung).
            calendar_dir: Pfad zum Kalenderordner für Ferien-/Feiertage.
            timetable_change_uc: Use Case für die Neuberechnung.
            on_accept: Callback, der nach Klick auf "Übernehmen" aufgerufen wird.
            theme_key: Optionaler Theme-Name.
        """
        super().__init__(
            master,
            title="Stundenplanänderung",
            geometry="1200x680",
            minsize=(900, 500),
            theme_key=theme_key,
        )
        self._table = table
        self._group_name = strip_wiki_link(str(table.metadata.get("Lerngruppe", "")))
        self._day_columns = day_columns
        self._calendar_dir = calendar_dir
        self._timetable_change_uc = timetable_change_uc
        self._on_accept = on_accept
        self._old_units: list[dict[str, object]] = []
        self._draft_slots: list[DraftSlot] = []
        self._undo_stack: list[list[DraftSlot]] = []
        self._date_from: date | None = None
        self._date_to: date | None = None
        self._rhythm_segment: tuple[WeekdayRhythm, ...] = ()
        self._rhythm_picker: WeekdayRhythmPicker | None = None
        self._build_ui()
        self.apply_theme()
        self._configure_tree_tags()
        self.bind_all("<Control-z>", self._on_undo)

    def _table_dates(self) -> list[date]:
        """Liefert alle gültigen Datumseinträge aus den Planzeilen."""
        result = []
        for row in self._table.rows:
            d = parse_plan_row_date(row[0] if row else "")
            if d is not None:
                result.append(d)
        return result

    def _build_ui(self) -> None:
        """Erstellt den gesamten Dialog-Inhalt (Header, Splitbereich, Footer)."""
        outer = widgets.Frame(self.content, padding=8)
        outer.pack(fill="both", expand=True)
        self._build_header(outer)
        self._build_split(outer)
        self._build_footer(outer)

    def _build_header(self, parent) -> None:
        """Baut den oberen Bereich mit Datumsauswahl, Stundenrhythmus und Berechnen-Button."""
        hf = widgets.Frame(parent)
        hf.pack(fill="x", pady=(0, 6))

        dates = self._table_dates()
        today = date.today()
        default_from = today
        default_to = max(dates) if dates else today

        widgets.Label(hf, text="Von:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self._von_var = ui.StringVar(value=default_from.strftime("%d.%m.%Y"))
        widgets.Entry(hf, textvariable=self._von_var, width=12).grid(row=0, column=1, sticky="w")
        widgets.Button(hf, text="Kursbeginn", command=self._set_von_kursbeginn).grid(
            row=0, column=2, padx=(4, 16)
        )

        widgets.Label(hf, text="Bis:").grid(row=0, column=3, sticky="w", padx=(0, 4))
        self._bis_var = ui.StringVar(value=default_to.strftime("%d.%m.%Y"))
        widgets.Entry(hf, textvariable=self._bis_var, width=12).grid(row=0, column=4, sticky="w")
        widgets.Button(hf, text="Kursende", command=self._set_bis_kursende).grid(
            row=0, column=5, padx=(4, 16)
        )

        rhythm_frame = widgets.Frame(hf)
        rhythm_frame.grid(row=0, column=6, sticky="w")
        self._rhythm_picker = WeekdayRhythmPicker(rhythm_frame)
        self._rhythm_picker.pack(side="left")
        existing_rhythm = parse_rhythm(self._table.metadata.get(RHYTHM_YAML_KEY, []))
        self._rhythm_picker.set_from_rhythm(existing_rhythm, on=today)

        widgets.Button(hf, text="Berechnen", command=self._on_berechnen).grid(
            row=0, column=7, padx=(8, 0)
        )

    def _build_split(self, parent) -> None:
        """Erstellt den PanedWindow mit linkem und rechtem Treeview."""
        pane = widgets.Panedwindow(parent, orient="horizontal")
        pane.pack(fill="both", expand=True)

        left_frame = widgets.Frame(pane)
        right_frame = widgets.Frame(pane)
        pane.add(left_frame, weight=1)
        pane.add(right_frame, weight=1)

        self._left_tree = self._make_tree(left_frame, "Alter Plan")
        self._right_tree = self._make_tree(right_frame, "Neuer Plan (Entwurf)")

    def _make_tree(self, parent, title: str) -> widgets.Treeview:
        """Erstellt einen beschrifteten Treeview mit Scrollleiste."""
        widgets.Label(parent, text=title, font=("Segoe UI", 9, "bold")).pack(
            anchor="w", padx=4, pady=(4, 2)
        )
        frame = widgets.Frame(parent)
        frame.pack(fill="both", expand=True)

        cols = ("datum", "art", "inhalt")
        tree = widgets.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        tree.heading("datum", text="Datum")
        tree.heading("art", text="Art")
        tree.heading("inhalt", text="Inhalt/Thema")
        tree.column("datum", width=90, stretch=False)
        tree.column("art", width=80, stretch=False)
        tree.column("inhalt", width=260, stretch=True)

        vsb = widgets.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        return tree

    def _build_footer(self, parent) -> None:
        """Erstellt den Footer mit Slot-Aktionsknöpfen und Abbrechen/Übernehmen."""
        ff = widgets.Frame(parent)
        ff.pack(fill="x", pady=(6, 0))

        widgets.Button(ff, text="Ausfall / Stattfinden", command=self._on_toggle_ausfall).pack(
            side="left", padx=(0, 4)
        )
        widgets.Button(ff, text="↑", command=lambda: self._on_swap(-1)).pack(side="left", padx=(0, 2))
        widgets.Button(ff, text="↓", command=lambda: self._on_swap(1)).pack(side="left", padx=(0, 8))
        widgets.Button(ff, text="Entfernen", command=self._on_remove).pack(side="left")

        widgets.Button(ff, text="Übernehmen", command=self._on_accept_click).pack(side="right")
        widgets.Button(ff, text="Abbrechen", command=self.destroy).pack(side="right", padx=(0, 6))

    def _configure_tree_tags(self) -> None:
        """Konfiguriert Farb-Tags beider Treeviews nach der Theme-Initialisierung."""
        cancel_bg = tinted_color("warning_soft", degree=0.72, base_token="panel_strong")
        recovered_bg = tinted_color("warning_soft", degree=0.35, base_token="panel_strong")
        for tree in (self._left_tree, self._right_tree):
            tree.tag_configure("cancel", background=cancel_bg)
        self._right_tree.tag_configure("recovered", background=recovered_bg)

    # ── Date entry helpers ──────────────────────────────────────────────────

    def _parse_date_entry(self, var: ui.StringVar) -> date | None:
        """Parst ein DD.MM.YYYY-Eingabefeld; None bei ungültigem Wert."""
        try:
            return datetime.strptime(str(var.get()).strip(), "%d.%m.%Y").date()
        except ValueError:
            return None

    def _set_von_kursbeginn(self) -> None:
        """Setzt Von-Feld auf den frühesten Datumseintrag des Kursplans."""
        dates = self._table_dates()
        if dates:
            self._von_var.set(min(dates).strftime("%d.%m.%Y"))

    def _set_bis_kursende(self) -> None:
        """Setzt Bis-Feld auf den spätesten Datumseintrag des Kursplans."""
        dates = self._table_dates()
        if dates:
            self._bis_var.set(max(dates).strftime("%d.%m.%Y"))

    def _collect_new_rhythm(self, *, valid_from: date) -> tuple[WeekdayRhythm, ...]:
        """Liest den neuen Rhythmus aus dem `WeekdayRhythmPicker`, gültig ab `valid_from`."""
        assert self._rhythm_picker is not None
        return normalize_day_rhythm(self._rhythm_picker.collect_raw(), valid_from=valid_from)

    # ── Berechnen ──────────────────────────────────────────────────────────

    def _on_berechnen(self) -> None:
        """Berechnet den neuen Planungsvorschlag und aktualisiert beide Treeviews."""
        date_from = self._parse_date_entry(self._von_var)
        date_to = self._parse_date_entry(self._bis_var)
        if date_from is None or date_to is None:
            messagebox.showerror("Stundenplanänderung", "Ungültiges Datumsformat (DD.MM.YYYY).", parent=self)
            return
        if date_from > date_to:
            messagebox.showerror("Stundenplanänderung", "Von-Datum muss vor Bis-Datum liegen.", parent=self)
            return
        try:
            new_rhythm = self._collect_new_rhythm(valid_from=date_from)
        except ValidationError as exc:
            messagebox.showerror("Stundenplanänderung", str(exc), parent=self)
            return
        try:
            result = self._timetable_change_uc.compute(
                day_columns=self._day_columns,
                date_from=date_from,
                date_to=date_to,
                new_rhythm=new_rhythm,
                calendar_dir=self._calendar_dir,
            )
        except Exception as exc:
            messagebox.showerror("Stundenplanänderung", str(exc), parent=self)
            return
        self._date_from = date_from
        self._date_to = date_to
        self._rhythm_segment = new_rhythm
        self._old_units = result.old_units
        self._draft_slots = result.draft_slots
        self._undo_stack.clear()
        self._refresh_left_tree()
        self._refresh_right_tree()

    # ── Tree rendering ─────────────────────────────────────────────────────

    def _refresh_left_tree(self) -> None:
        """Befüllt den linken Treeview mit den alten Planzeilen."""
        self._left_tree.delete(*self._left_tree.get_children())
        for day in self._old_units:
            datum_str = self._fmt_datum(str(day.get("datum", "")))
            if column_is_stattfindend(day):
                art = ""
            else:
                art = "Ausfall" if column_is_manual_ausfall(day) else "Ferien"
            inhalt = strip_wiki_link(str(day.get("inhalt", "")))
            tag = "cancel" if not column_is_stattfindend(day) else ""
            self._left_tree.insert("", "end", values=(datum_str, art, inhalt), tags=(tag,))

    def _refresh_right_tree(self) -> None:
        """Befüllt den rechten Treeview mit den aktuellen Draft-Slots."""
        sel_items = self._right_tree.selection()
        sel_idx = None
        if sel_items:
            children = self._right_tree.get_children()
            try:
                sel_idx = list(children).index(sel_items[0])
            except ValueError:
                pass

        self._right_tree.delete(*self._right_tree.get_children())
        for slot in self._draft_slots:
            datum_str = slot.datum.strftime("%d.%m.%Y")
            if slot.is_ferien:
                art, inhalt_text, tag = "Ferien", slot.ausfall_reason, "cancel"
            elif slot.is_user_ausfall:
                art, inhalt_text, tag = "Ausfall", slot.ausfall_reason, "cancel"
            else:
                art = ""
                if slot.content:
                    inhalt_text = strip_wiki_link(slot.content)
                elif slot.oberthema_cell:
                    oberthema_text = extract_plan_oberthema(slot.oberthema_cell, self._group_name)
                    inhalt_text = f"Oberthema: {oberthema_text}" if oberthema_text else strip_wiki_link(
                        slot.oberthema_cell
                    )
                else:
                    inhalt_text = ""
                tag = "recovered" if slot.was_recovered_week else ""
            self._right_tree.insert("", "end", values=(datum_str, art, inhalt_text), tags=(tag,))

        children = self._right_tree.get_children()
        if sel_idx is not None and sel_idx < len(children):
            item = children[sel_idx]
            self._right_tree.selection_set(item)
            self._right_tree.see(item)

    @staticmethod
    def _fmt_datum(raw: str) -> str:
        """Konvertiert DD-MM-YY zu DD.MM.YY für die Treeview-Anzeige."""
        try:
            return datetime.strptime(raw.strip(), "%d-%m-%y").strftime("%d.%m.%y")
        except ValueError:
            return raw

    # ── Internal undo ──────────────────────────────────────────────────────

    def _save_undo_snapshot(self) -> None:
        """Speichert eine Kopie der aktuellen Draft-Slots für Strg+Z."""
        self._undo_stack.append(copy.deepcopy(self._draft_slots))

    def _on_undo(self, _event=None) -> str:
        """Stellt den letzten gespeicherten Zustand der Draft-Slots wieder her."""
        if not self._undo_stack:
            return "break"
        self._draft_slots = self._undo_stack.pop()
        self._refresh_right_tree()
        return "break"

    # ── Slot actions ───────────────────────────────────────────────────────

    def _selected_right_index(self) -> int | None:
        """Liefert den Index des im rechten Treeview selektierten Slots."""
        sel = self._right_tree.selection()
        if not sel:
            return None
        children = self._right_tree.get_children()
        try:
            return list(children).index(sel[0])
        except ValueError:
            return None

    def _on_toggle_ausfall(self) -> None:
        """Wechselt den Status des gewählten Slots zwischen Stattfindend und Ausfall."""
        idx = self._selected_right_index()
        if idx is None or not self._draft_slots:
            return
        slot = self._draft_slots[idx]
        if slot.is_ferien:
            return

        self._save_undo_snapshot()

        if slot.is_user_ausfall:
            updated = dataclasses.replace(slot, is_user_ausfall=False, ausfall_reason="")
            self._draft_slots[idx] = updated
        else:
            reason = simpledialog.askstring("Ausfall", "Ausfallgrund (leer = ohne Angabe):", parent=self)
            if reason is None:
                self._undo_stack.pop()
                return
            displaced = slot.content
            updated = dataclasses.replace(slot, is_user_ausfall=True, ausfall_reason=reason.strip(), content="")
            self._draft_slots[idx] = updated
            if displaced:
                self._place_displaced_content(displaced, start_after=idx)

        self._refresh_right_tree()

    def _place_displaced_content(self, content: str, start_after: int) -> None:
        """Platziert verdrängten Inhalt im nächsten leeren Stattfindend-Slot."""
        for i in range(start_after + 1, len(self._draft_slots)):
            s = self._draft_slots[i]
            if not s.is_ferien and not s.is_user_ausfall and not s.content and not s.oberthema_cell:
                self._draft_slots[i] = dataclasses.replace(s, content=content)
                return
        messagebox.showwarning(
            "Ausfall",
            "Kein leerer Slot zum Verschieben des Inhalts vorhanden. Inhalt wurde entfernt.",
            parent=self,
        )

    def _on_swap(self, direction: int) -> None:
        """Tauscht den Inhalt des gewählten Slots mit dem nächsten Stattfindend-Slot."""
        idx = self._selected_right_index()
        if idx is None or not self._draft_slots:
            return
        slot = self._draft_slots[idx]
        if slot.is_ferien or slot.is_user_ausfall:
            return

        partner_idx = self._find_stattfindend_neighbor(idx, direction)
        if partner_idx is None:
            return

        self._save_undo_snapshot()
        a, b = self._draft_slots[idx], self._draft_slots[partner_idx]
        self._draft_slots[idx] = dataclasses.replace(a, content=b.content, oberthema_cell=b.oberthema_cell)
        self._draft_slots[partner_idx] = dataclasses.replace(b, content=a.content, oberthema_cell=a.oberthema_cell)
        self._refresh_right_tree()
        new_sel_idx = partner_idx
        children = self._right_tree.get_children()
        if 0 <= new_sel_idx < len(children):
            self._right_tree.selection_set(children[new_sel_idx])
            self._right_tree.see(children[new_sel_idx])

    def _find_stattfindend_neighbor(self, idx: int, direction: int) -> int | None:
        """Sucht den nächsten Stattfindend-Slot in der gegebenen Richtung."""
        step = direction
        i = idx + step
        while 0 <= i < len(self._draft_slots):
            s = self._draft_slots[i]
            if not s.is_ferien and not s.is_user_ausfall:
                return i
            i += step
        return None

    def _on_remove(self) -> None:
        """Leert den Inhalt des gewählten Draft-Slots (Einheit wird zur Schatteneinheit)."""
        idx = self._selected_right_index()
        if idx is None or not self._draft_slots:
            return
        slot = self._draft_slots[idx]
        if slot.is_ferien or (not slot.content and not slot.oberthema_cell):
            return
        self._save_undo_snapshot()
        self._draft_slots[idx] = dataclasses.replace(slot, content="", oberthema_cell="")
        self._refresh_right_tree()

    def _on_accept_click(self) -> None:
        """Übergibt den aktuellen Entwurf an die aufrufende Stelle und schließt den Dialog."""
        if not self._draft_slots or self._date_from is None or self._date_to is None:
            messagebox.showwarning("Übernehmen", "Bitte zuerst 'Berechnen' ausführen.", parent=self)
            return
        self._on_accept(self._date_from, self._date_to, list(self._draft_slots), self._rhythm_segment)
        self.destroy()
