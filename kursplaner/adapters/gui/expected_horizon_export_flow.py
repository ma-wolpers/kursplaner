"""GUI-Ablauf der beiden Kompetenzhorizont-Exporte (LZK-Button und "Exportieren als…").

Orchestriert nur: Daten holen → Themendialog → Speichern-Dialog → Use Case →
Meldung. Alle fachlichen Regeln (Stichtag, Reihenfolge, Identität,
Default-Name, Link-Form, Merge-Quelle) liegen in den Use Cases
(`ExportLzkExpectedHorizonUseCase`, `ExpectedHorizonTopicQueryUseCase`,
`ExportExpectedHorizonUseCase`). Ausgelagert aus `action_controller.py`, damit
dieser nicht weiter wächst.

Beide Wege arbeiten mit `raw_day_columns` und dem stabilen ``row_index`` der
gewählten Spalte, damit ausgeblendete Spalten nicht im KH fehlen.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Callable

from kursplaner.adapters.gui.dialog_services import filedialog, messagebox
from kursplaner.adapters.gui.expected_horizon_topic_dialog import ask_expected_horizon_topics

_LZK_TITLE = "LZK-Kompetenzhorizont"
_ADHOC_TITLE = "Exportieren als..."
_REPORTLAB_MISSING = "PDF-Export benötigt das Paket 'reportlab', das in dieser Umgebung nicht installiert ist."


class ExpectedHorizonExportFlow:
    """Führt die Dialogfolge der KH-Exporte aus und delegiert an die Use Cases."""

    def __init__(
        self,
        app,
        *,
        lzk_usecase,
        markdown_usecase,
        pdf_usecase,
        topic_query,
        run_tracked_write: Callable,
        refresh_after_write: Callable,
    ) -> None:
        """Initialisiert den Ablauf.

        Args:
            app: Hauptfenster (liefert Tabelle, `raw_day_columns`, Theme, Elternfenster).
            lzk_usecase: `ExportLzkExpectedHorizonUseCase` oder ``None`` ohne reportlab.
            markdown_usecase: Markdown-`ExportExpectedHorizonUseCase` (mit Leser).
            pdf_usecase: PDF-`ExportExpectedHorizonUseCase` oder ``None`` ohne reportlab.
            topic_query: `ExpectedHorizonTopicQueryUseCase`.
            run_tracked_write: Undo-fähiger Schreibwrapper des Action-Controllers.
            refresh_after_write: Aktualisiert Grid/Auswahl nach dem Schreiben.
        """
        self._app = app
        self._lzk_usecase = lzk_usecase
        self._markdown_usecase = markdown_usecase
        self._pdf_usecase = pdf_usecase
        self._topic_query = topic_query
        self._run_tracked_write = run_tracked_write
        self._refresh_after_write = refresh_after_write

    def _ask_topics(self, options, *, with_pdf_layout: bool):
        """Öffnet den Themendialog; bei PDF-Ausgabe zusätzlich mit den PDF-Layout-Optionen."""
        return ask_expected_horizon_topics(
            self._app, options, theme_key=self._app.theme_var.get(), with_pdf_layout=with_pdf_layout
        )

    def _ask_path(self, *, title: str, default: Path, extension: str, label: str) -> Path | None:
        selected = filedialog.asksaveasfilename(
            parent=self._app,
            title=title,
            initialdir=str(default.parent),
            initialfile=default.name,
            defaultextension=extension,
            filetypes=[(label, f"*{extension}")],
        )
        return Path(selected).expanduser().resolve() if selected else None

    def export_lzk(self, *, anchor_row_index: int, selected_index: int) -> None:
        """LZK-Button: Themen wählen, Speicherort wählen, Markdown+PDF schreiben, LZK aktualisieren."""
        if self._lzk_usecase is None:
            messagebox.showerror(_LZK_TITLE, _REPORTLAB_MISSING, parent=self._app)
            return
        table = self._app.current_table
        raw_days = list(self._app.raw_day_columns)
        try:
            proposal = self._lzk_usecase.build_proposal(
                table=table, raw_day_columns=raw_days, anchor_row_index=anchor_row_index
            )
        except RuntimeError as exc:
            messagebox.showerror(_LZK_TITLE, str(exc), parent=self._app)
            return

        choice = self._ask_topics(proposal.options, with_pdf_layout=True)
        if choice is None or not choice.topics:
            return
        selection = choice.topics
        default = proposal.default_markdown_path(selection, now=datetime.now())
        markdown_path = self._ask_path(title=_LZK_TITLE, default=default, extension=".md", label="Markdown")
        if markdown_path is None:
            return

        try:
            result = self._run_tracked_write(
                label="LZK-Kompetenzhorizont exportieren",
                action=lambda: self._lzk_usecase.execute(
                    table=table,
                    raw_day_columns=raw_days,
                    proposal=proposal,
                    selection=selection,
                    markdown_path=markdown_path,
                    export_date=date.today(),
                    pdf_layout=choice.pdf_layout,
                ),
                # History capture is text-based; tracking binary PDFs would crash UTF-8 decoding.
                extra_before=[markdown_path],
                extra_after=[markdown_path],
            )
        except Exception as exc:
            messagebox.showerror(_LZK_TITLE, str(exc), parent=self._app)
            return

        self._refresh_after_write(selected_index=selected_index)
        self._show_lzk_result(result)

    def _show_lzk_result(self, result) -> None:
        lines = [
            "Kompetenzhorizont erfolgreich exportiert:",
            f"Markdown: {result.markdown_path}",
            f"PDF: {result.pdf_path}",
            "",
            f"Oberthemen: {', '.join(result.oberthemen)}",
            f"Zeilen: {result.row_count}",
        ]
        notes: list[str] = []
        if result.removed_unavailable:
            notes.append(f"Nicht mehr verfügbare Themen aus der LZK entfernt: {', '.join(result.removed_unavailable)}")
        if not result.link_written:
            notes.append("Die Datei liegt außerhalb des Obsidian-Vaults; die LZK verlinkt sie deshalb nicht.")
        if notes:
            messagebox.showwarning(
                _LZK_TITLE, "\n".join(lines + ["", "Hinweis:"] + [f"- {n}" for n in notes]), parent=self._app
            )
        else:
            messagebox.showinfo(_LZK_TITLE, "\n".join(lines), parent=self._app)

    def export_adhoc(self, *, anchor_row_index: int, output_format: str) -> None:
        """ "Exportieren als… → Kompetenzhorizont": Ad-hoc-Export ohne Änderung an einer LZK."""
        is_pdf = output_format == "pdf"
        usecase = self._pdf_usecase if is_pdf else self._markdown_usecase
        if usecase is None:
            messagebox.showerror(_ADHOC_TITLE, _REPORTLAB_MISSING, parent=self._app)
            return
        table = self._app.current_table
        raw_days = list(self._app.raw_day_columns)
        try:
            options = self._topic_query.query(raw_day_columns=raw_days, anchor_row_index=anchor_row_index)
        except RuntimeError as exc:
            messagebox.showerror(_ADHOC_TITLE, str(exc), parent=self._app)
            return

        choice = self._ask_topics(options, with_pdf_layout=is_pdf)
        if choice is None or not choice.topics:
            return
        selection = choice.topics
        extension = ".pdf" if is_pdf else ".md"
        topics = options.ordered_selection(selection)
        default = usecase.default_adhoc_output_path(
            table, topics=topics, cutoff=options.cutoff, now=datetime.now(), extension=extension
        )
        output_path = self._ask_path(
            title=_ADHOC_TITLE, default=default, extension=extension, label="PDF" if is_pdf else "Markdown"
        )
        if output_path is None:
            return

        try:
            result = usecase.execute(
                table=table,
                raw_day_columns=raw_days,
                oberthemen=topics,
                cutoff=options.cutoff,
                output_path=output_path,
                export_date=date.today(),
                # Eine bereits existierende Zieldatei ist Merge-Quelle (der Leser liefert sonst []).
                merge_source=output_path,
                layout=choice.pdf_layout,
            )
        except Exception as exc:
            messagebox.showerror(_ADHOC_TITLE, str(exc), parent=self._app)
            return
        messagebox.showinfo(
            _ADHOC_TITLE,
            f"{'PDF' if is_pdf else 'Markdown'} erfolgreich exportiert:\n{result.output_path}\n\n"
            f"Oberthemen: {', '.join(result.oberthemen)}\nZeilen: {result.row_count}",
            parent=self._app,
        )
