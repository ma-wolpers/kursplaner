from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets

from kursplaner.adapters.gui.conflict_decision_dialog import ask_conflict_decision
from kursplaner.adapters.gui.dialog_services import messagebox
from kursplaner.adapters.gui.grade_group_selector import GradeGroupSelector
from kursplaner.adapters.gui.help_catalog import SCHOOL_WIDE_CANCELLATION_HELP
from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.core.domain.school_wide_cancellation import SchoolWideCancellationEntry
from kursplaner.core.flows.school_wide_cancellation_flow import SchoolWideCancellationFlow
from kursplaner.core.ports.repositories import ConflictContext, ConflictResolution
from kursplaner.core.usecases.bulk_cancellation_coordinator import BulkOperationResult, CourseOperationOutcome
from kursplaner.core.usecases.school_wide_cancellation_diagnostics_usecase import (
    SchoolWideCancellationDiagnosticsUseCase,
)


_DAY_MONTH_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.?$")


def parse_flexible_date(text: str, *, today: date | None = None) -> date | None:
    """Parst ein Datumsfeld des Dialogs. Jahr ist optional (`DD.MM.`/`DD.MM`) - dann gilt `today`s Jahr.

    Reine Funktion (kein `ui.StringVar`), damit sie ohne Tk-Kontext testbar ist.
    Der Tag/Monat-Fall parst bewusst per Regex statt über ein jahrloses
    `strptime` (dessen implizites Default-Jahr nicht schaltjahrfähig ist und
    z. B. "29.02." unabhängig vom tatsächlichen Zieljahr ablehnen würde).
    """
    stripped = text.strip()
    if not stripped:
        return None
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(stripped, fmt).date()
        except ValueError:
            continue
    match = _DAY_MONTH_RE.match(stripped)
    if match is None:
        return None
    day, month = int(match.group(1)), int(match.group(2))
    reference_year = (today or date.today()).year
    try:
        return date(reference_year, month, day)
    except ValueError:
        return None


def resolve_date_range(von_text: str, bis_text: str, *, today: date | None = None) -> tuple[date, date] | None:
    """Liest Von/Bis. Leeres Bis gilt als eintägiger Ausfall (= Von); Bis vor Von ist ungültig (-> `None`)."""
    date_from = parse_flexible_date(von_text, today=today)
    if date_from is None:
        return None
    stripped_bis = bis_text.strip()
    if not stripped_bis:
        return date_from, date_from
    date_to = parse_flexible_date(bis_text, today=today)
    if date_to is None or date_to < date_from:
        return None
    return date_from, date_to


class SchoolWideCancellationDialog(ScrollablePopupWindow):
    """Popup zur Verwaltung schulweiter Ausfaelle: Liste bestehender Eintraege + Formular mit Live-Vorschau.

    Enthaelt keine Fachlogik - reine Uebersetzung UI-Zustand <-> Flow-Aufruf.
    Betroffene Kurse, Identitaetsaufloesung, Fehler-/Konfliktentscheidungen
    und Persistenz leben vollstaendig in `SchoolWideCancellationFlow` und den
    darunterliegenden Usecases.
    """

    def __init__(
        self,
        master,
        *,
        flow: SchoolWideCancellationFlow,
        diagnostics_uc: SchoolWideCancellationDiagnosticsUseCase,
        base_dir: Path,
        theme_key: str | None = None,
    ) -> None:
        """Oeffnet den Dialog, laedt bestehende Eintraege und fuehrt den Konsistenzcheck aus."""
        super().__init__(
            master,
            title="Schulweite Ausfälle",
            geometry="1100x640",
            minsize=(900, 520),
            theme_key=theme_key,
        )
        self._flow = flow
        self._diagnostics_uc = diagnostics_uc
        self._base_dir = base_dir
        self._entries: list[SchoolWideCancellationEntry] = []
        self._selected_entry_id: str | None = None
        self._tooltips: list[HoverTooltip] = []

        self._build_ui()
        self.apply_theme()
        self._reload_entries()
        self._run_diagnostics()

    # ── UI-Aufbau ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = widgets.Frame(self.content, padding=8)
        outer.pack(fill="both", expand=True)

        self._diagnostics_var = ui.StringVar(value="")
        diagnostics_label = widgets.Label(
            outer, textvariable=self._diagnostics_var, wraplength=1050, justify="left", foreground="#B04A4A"
        )
        diagnostics_label.pack(fill="x", pady=(0, 6))
        self._tooltips.append(HoverTooltip(diagnostics_label, SCHOOL_WIDE_CANCELLATION_HELP["diagnostics"]))

        pane = widgets.Panedwindow(outer, orient="horizontal")
        pane.pack(fill="both", expand=True)

        left_frame = widgets.Frame(pane)
        right_frame = widgets.Frame(pane)
        pane.add(left_frame, weight=1)
        pane.add(right_frame, weight=2)

        self._build_entry_list(left_frame)
        self._build_form(right_frame)
        self._build_footer(outer)

    def _build_entry_list(self, parent) -> None:
        widgets.Label(parent, text="Bestehende Ausfälle", font=("Segoe UI", 9, "bold")).pack(
            anchor="w", padx=4, pady=(4, 2)
        )
        frame = widgets.Frame(parent)
        frame.pack(fill="both", expand=True)

        cols = ("reason", "range", "grades")
        self._entry_tree = widgets.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        self._entry_tree.heading("reason", text="Grund")
        self._entry_tree.heading("range", text="Zeitraum")
        self._entry_tree.heading("grades", text="Stufen")
        self._entry_tree.column("reason", width=140, stretch=True)
        self._entry_tree.column("range", width=140, stretch=False)
        self._entry_tree.column("grades", width=100, stretch=False)
        vsb = widgets.Scrollbar(frame, orient="vertical", command=self._entry_tree.yview)
        self._entry_tree.configure(yscrollcommand=vsb.set)
        self._entry_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._entry_tree.bind("<<TreeviewSelect>>", self._on_entry_selected)
        self._tooltips.append(HoverTooltip(self._entry_tree, SCHOOL_WIDE_CANCELLATION_HELP["entry_list"]))

    def _build_form(self, parent) -> None:
        form = widgets.Frame(parent, padding=(10, 4))
        form.pack(fill="both", expand=True)
        form.grid_columnconfigure(1, weight=1)
        form.grid_rowconfigure(5, weight=1)

        widgets.Label(form, text="Was:").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self._reason_var = ui.StringVar(value="")
        reason_entry = widgets.Entry(form, textvariable=self._reason_var, width=40)
        reason_entry.grid(row=0, column=1, columnspan=3, sticky="we", pady=(0, 4))
        self._tooltips.append(HoverTooltip(reason_entry, SCHOOL_WIDE_CANCELLATION_HELP["reason"]))

        widgets.Label(form, text="Von:").grid(row=1, column=0, sticky="w", pady=(0, 4))
        self._von_var = ui.StringVar(value=date.today().strftime("%d.%m.%Y"))
        von_entry = widgets.Entry(form, textvariable=self._von_var, width=12)
        von_entry.grid(row=1, column=1, sticky="w", pady=(0, 4))
        self._tooltips.append(HoverTooltip(von_entry, SCHOOL_WIDE_CANCELLATION_HELP["date_from"]))

        widgets.Label(form, text="Bis:").grid(row=1, column=2, sticky="w", pady=(0, 4))
        self._bis_var = ui.StringVar(value="")
        bis_entry = widgets.Entry(form, textvariable=self._bis_var, width=12)
        bis_entry.grid(row=1, column=3, sticky="w", pady=(0, 4))
        self._tooltips.append(HoverTooltip(bis_entry, SCHOOL_WIDE_CANCELLATION_HELP["date_to"]))

        for var in (self._reason_var, self._von_var, self._bis_var):
            var.trace_add("write", lambda *_args: self._refresh_preview())

        grades_label = widgets.Label(form, text="Betroffene Jahrgangsstufen:")
        grades_label.grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 2))
        self._tooltips.append(HoverTooltip(grades_label, SCHOOL_WIDE_CANCELLATION_HELP["grade_groups"]))
        self._grade_selector = GradeGroupSelector(form, on_change=self._refresh_preview)
        self._grade_selector.grid(row=3, column=0, columnspan=4, sticky="we", pady=(0, 8))

        preview_label = widgets.Label(form, text="Live-Vorschau betroffener Einheiten:")
        preview_label.grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 2))
        self._tooltips.append(HoverTooltip(preview_label, SCHOOL_WIDE_CANCELLATION_HELP["preview"]))

        self._build_preview_tree(form)

    def _build_preview_tree(self, form) -> None:
        preview_frame = widgets.Frame(form)
        preview_frame.grid(row=5, column=0, columnspan=4, sticky="nsew")

        preview_cols = ("course", "date", "content", "status")
        self._preview_tree = widgets.Treeview(preview_frame, columns=preview_cols, show="headings", selectmode="none")
        self._preview_tree.heading("course", text="Kurs")
        self._preview_tree.heading("date", text="Datum")
        self._preview_tree.heading("content", text="Inhalt")
        self._preview_tree.heading("status", text="Status")
        self._preview_tree.column("course", width=140, stretch=True)
        self._preview_tree.column("date", width=80, stretch=False)
        self._preview_tree.column("content", width=200, stretch=True)
        self._preview_tree.column("status", width=150, stretch=False)
        preview_vsb = widgets.Scrollbar(preview_frame, orient="vertical", command=self._preview_tree.yview)
        self._preview_tree.configure(yscrollcommand=preview_vsb.set)
        self._preview_tree.pack(side="left", fill="both", expand=True)
        preview_vsb.pack(side="right", fill="y")
        self._preview_tree.tag_configure("claimed", foreground="#B04A4A")

    def _build_footer(self, parent) -> None:
        footer = widgets.Frame(parent)
        footer.pack(fill="x", pady=(8, 0))
        widgets.Button(footer, text="Neu", command=self._on_new).pack(side="left")
        widgets.Button(footer, text="Löschen", command=self._on_delete).pack(side="left", padx=(8, 0))
        widgets.Button(footer, text="Schließen", command=self.destroy).pack(side="right")
        widgets.Button(footer, text="Speichern", command=self._on_save).pack(side="right", padx=(0, 8))

    # ── Daten laden / Vorschau ───────────────────────────────────────────

    def _reload_entries(self) -> None:
        self._entries = self._flow.list_entries()
        self._entry_tree.delete(*self._entry_tree.get_children())
        for entry in self._entries:
            range_text = f"{entry.date_from.strftime('%d.%m.%y')}–{entry.date_to.strftime('%d.%m.%y')}"
            grades_text = ", ".join(str(g) for g in sorted(entry.grade_levels))
            self._entry_tree.insert("", "end", iid=entry.entry_id, values=(entry.reason, range_text, grades_text))

    def _run_diagnostics(self) -> None:
        issues = self._diagnostics_uc.diagnose(self._entries)
        if not issues:
            self._diagnostics_var.set("")
            return
        summary = "; ".join(f"{issue.course_label}: {issue.description}" for issue in issues[:5])
        more = f" (+{len(issues) - 5} weitere)" if len(issues) > 5 else ""
        self._diagnostics_var.set(f"⚠ {len(issues)} Abweichung(en) erkannt: {summary}{more}")

    def _on_entry_selected(self, _event=None) -> None:
        selection = self._entry_tree.selection()
        if not selection:
            return
        entry = next((e for e in self._entries if e.entry_id == selection[0]), None)
        if entry is None:
            return
        self._selected_entry_id = entry.entry_id
        self._reason_var.set(entry.reason)
        self._von_var.set(entry.date_from.strftime("%d.%m.%Y"))
        self._bis_var.set(entry.date_to.strftime("%d.%m.%Y"))
        self._grade_selector.set_selected_grades(entry.grade_levels)
        self._refresh_preview()

    def _on_new(self) -> None:
        self._selected_entry_id = None
        for item in self._entry_tree.selection():
            self._entry_tree.selection_remove(item)
        self._reason_var.set("")
        self._von_var.set(date.today().strftime("%d.%m.%Y"))
        self._bis_var.set("")
        self._grade_selector.set_selected_grades(frozenset())
        self._refresh_preview()

    @staticmethod
    def _parse_date(var: ui.StringVar) -> date | None:
        """Parst ein Datumsfeld. Jahr ist optional (`DD.MM.` / `DD.MM`) - dann gilt das aktuelle Jahr."""
        return parse_flexible_date(str(var.get()))

    def _resolve_date_range(self) -> tuple[date, date] | None:
        """Liest Von/Bis. Leeres Bis gilt als eintägiger Ausfall (= Von); Bis vor Von ist ungültig."""
        return resolve_date_range(str(self._von_var.get()), str(self._bis_var.get()))

    def _date_range_error_message(self) -> str:
        """Erklärt, warum der letzte `_resolve_date_range()`-Aufruf gescheitert ist (nur für Fehlermeldungen)."""
        if self._parse_date(self._von_var) is None:
            return "Ungültiges Von-Datum (DD.MM.YYYY oder DD.MM. für das aktuelle Jahr)."
        bis_text = str(self._bis_var.get()).strip()
        if bis_text and self._parse_date(self._bis_var) is None:
            return "Ungültiges Bis-Datum (DD.MM.YYYY oder DD.MM. für das aktuelle Jahr)."
        return "Bis-Datum darf nicht vor dem Von-Datum liegen."

    def _refresh_preview(self, *_args) -> None:
        self._preview_tree.delete(*self._preview_tree.get_children())
        date_range = self._resolve_date_range()
        grades = self._grade_selector.get_selected_grades()
        if date_range is None or not grades:
            return
        date_from, date_to = date_range

        result = self._flow.preview(
            base_dir=self._base_dir,
            date_from=date_from,
            date_to=date_to,
            grade_levels=grades,
            exclude_entry_id=self._selected_entry_id,
        )
        for unit in result.affected_units:
            status = f"belegt durch: {unit.claimed_by_reason}" if unit.claimed_by_reason else ""
            tag = "claimed" if unit.claimed_by_reason else ""
            self._preview_tree.insert(
                "",
                "end",
                values=(unit.course_label, unit.datum.strftime("%d.%m.%y"), unit.content_preview, status),
                tags=(tag,),
            )

    # ── Speichern / Löschen ──────────────────────────────────────────────

    def _decide(self, context: ConflictContext) -> ConflictResolution:
        return ask_conflict_decision(self, context=context, theme_key=self.theme_key)

    def _on_save(self) -> None:
        reason = self._reason_var.get().strip()
        if not reason:
            messagebox.showerror("Schulweite Ausfälle", "Bitte einen Grund angeben.", parent=self)
            return

        date_range = self._resolve_date_range()
        if date_range is None:
            messagebox.showerror("Schulweite Ausfälle", self._date_range_error_message(), parent=self)
            return
        date_from, date_to = date_range

        grades = self._grade_selector.get_selected_grades()
        if not grades:
            messagebox.showerror("Schulweite Ausfälle", "Bitte mindestens eine Jahrgangsstufe auswählen.", parent=self)
            return

        if self._selected_entry_id is None:
            mutation = self._flow.create(
                base_dir=self._base_dir,
                date_from=date_from,
                date_to=date_to,
                grade_levels=grades,
                reason=reason,
                decide=self._decide,
            )
        else:
            mutation = self._flow.edit(
                entry_id=self._selected_entry_id,
                base_dir=self._base_dir,
                date_from=date_from,
                date_to=date_to,
                grade_levels=grades,
                reason=reason,
                decide=self._decide,
            )
        self._after_mutation(mutation.bulk_result, selected_entry_id=mutation.entry.entry_id if mutation.entry else None)

    def _on_delete(self) -> None:
        if self._selected_entry_id is None:
            return
        if not messagebox.askyesno(
            "Schulweite Ausfälle",
            "Diesen Ausfall wirklich löschen und alle Verschiebungen zurücknehmen?",
            parent=self,
        ):
            return
        bulk_result = self._flow.delete(entry_id=self._selected_entry_id, decide=self._decide)
        self._after_mutation(bulk_result, selected_entry_id=None)

    def _after_mutation(self, bulk_result: BulkOperationResult, *, selected_entry_id: str | None) -> None:
        skipped = [r for r in bulk_result.course_results if r.outcome is CourseOperationOutcome.SKIPPED]
        self._reload_entries()
        self._run_diagnostics()
        self._selected_entry_id = selected_entry_id
        if selected_entry_id is not None:
            self._entry_tree.selection_set(selected_entry_id)
        self._refresh_preview()

        if bulk_result.aborted:
            messagebox.showinfo("Schulweite Ausfälle", "Der Vorgang wurde vollständig zurückgerollt.", parent=self)
        elif skipped:
            names = ", ".join(sorted({r.markdown_path.parent.name for r in skipped}))
            messagebox.showwarning(
                "Schulweite Ausfälle",
                f"{len(skipped)} Kurs(e) wurden übersprungen und sind nicht (vollständig) abgedeckt: {names}",
                parent=self,
            )
