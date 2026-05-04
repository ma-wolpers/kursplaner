from __future__ import annotations

import logging
import pathlib
import re

from kursplaner.adapters.gui.dialog_services import filedialog, messagebox, simpledialog
from kursplaner.adapters.gui.lesson_builder_dialog import ask_lesson_builder
from kursplaner.adapters.gui.lzk_column_dialog import ask_lzk_column_dialog
from kursplaner.core.config.path_store import infer_workspace_root_from_path
from kursplaner.core.config.ui_preferences_store import load_lesson_builder_field_settings
from kursplaner.core.config.path_store import BAUKASTEN_DIR_KEY, FACHDIDAKTIK_DIR_KEY, FACHINHALTE_DIR_KEY
from kursplaner.core.domain.course_subject import normalize_course_subject
from kursplaner.core.flows.lzk_lesson_flow import LzkLessonFlowWriteRequest


class MainWindowLessonConversionController:
    """Handles lesson-type conversion actions for the main window.

    This controller owns conversion flows (regular lesson, absence, hospitation,
    LZK) and delegates all fachliche decisions to injected use cases/flows.
    """

    def __init__(self, app):
        self.app = app
        deps = getattr(app, "gui_dependencies", None)
        if deps is None:
            raise RuntimeError("GUI Dependencies not available on app")
        self.convert_to_ausfall = deps.convert_to_ausfall
        self.convert_to_hospitation = deps.convert_to_hospitation
        self.lesson_commands = deps.lesson_commands
        self.find_markdown_for_selected = deps.find_markdown_for_selected
        self.plan_regular_lesson = deps.plan_regular_lesson
        self.convert_to_lzk = deps.convert_to_lzk
        self.lzk_lesson_flow = deps.lzk_lesson_flow
        self.lesson_transfer = deps.lesson_transfer
        self.subject_sources = deps.subject_sources
        self._load_last_ub_insights_uc = deps.load_last_ub_insights_usecase
        self._tracked_write_uc = deps.tracked_write_usecase
        self._logger = logging.getLogger(__name__)
        self._last_ub_sections_error_hint = ""

    @staticmethod
    def _workspace_root_from_path(path: pathlib.Path) -> pathlib.Path:
        """Leitet den Workspace-Stamm robust aus einem Projektpfad ab."""
        return infer_workspace_root_from_path(path)

    def _lesson_builder_ub_sections(self) -> list[tuple[str, list[str]]]:
        """Liefert die zuletzt dokumentierten UB-Impulse für den Builder-Dialog."""
        table = self.app.current_table
        self._last_ub_sections_error_hint = ""
        if table is None:
            return []

        try:
            workspace_root = self._workspace_root_from_path(table.markdown_path)
            subject_name = self.subject_folder_name()
            insights = self._load_last_ub_insights_uc.execute(
                workspace_root=workspace_root,
                subject_name=subject_name,
            )
        except Exception as exc:
            self._logger.exception("lesson_builder.ub_sections_load_failed")
            self._last_ub_sections_error_hint = (
                f"Die letzten UB-Punkte konnten nicht geladen werden. Details: {type(exc).__name__}"
            )
            return []

        return [
            (f"{subject_name} - Professionalisierungsschritte", list(insights.subject_steps)),
            (f"{subject_name} - Nutzbare Ressourcen", list(insights.subject_resources)),
            ("Pädagogik - Professionalisierungsschritte", list(insights.paedagogik_steps)),
            ("Pädagogik - Nutzbare Ressourcen", list(insights.paedagogik_resources)),
        ]

    def subject_folder_name(self) -> str:
        if self.app.current_table is None:
            return "Informatik"

        raw = str(self.app.current_table.metadata.get("Kursfach", "")).strip()
        return normalize_course_subject(raw)

    @staticmethod
    def markdown_stems_from_folder(folder: pathlib.Path) -> list[str]:
        if not folder.exists() or not folder.is_dir():
            return []
        stems = [path.stem.strip() for path in folder.rglob("*.md") if path.is_file() and path.stem.strip()]
        return sorted(set(stems), key=lambda text: text.lower())

    @staticmethod
    def find_named_child(parent: pathlib.Path, keywords: tuple[str, ...]) -> pathlib.Path | None:
        if not parent.exists() or not parent.is_dir():
            return None

        normalized = [keyword.lower().replace(" ", "") for keyword in keywords]
        for child in parent.iterdir():
            if not child.is_dir():
                continue
            token = child.name.lower().replace(" ", "")
            if any(keyword in token for keyword in normalized):
                return child
        return None

    def resolve_subject_sources(self) -> tuple[list[str], list[str], str, str]:
        unterricht_dir = self.app.gui_dependencies.path_settings_usecase.resolve_unterricht_dir(self.app.path_values)
        fach = self.subject_folder_name()
        inhalte, methodik = self.subject_sources.resolve_subject_sources(unterricht_dir, fach)

        path_settings = self.app.gui_dependencies.path_settings_usecase
        baukasten_dir = path_settings.resolve_for_key(self.app.path_values, BAUKASTEN_DIR_KEY)
        fachinhalte_root = path_settings.resolve_for_key(self.app.path_values, FACHINHALTE_DIR_KEY)
        fachdidaktik_root = path_settings.resolve_for_key(self.app.path_values, FACHDIDAKTIK_DIR_KEY)
        inhalte_dir = (fachinhalte_root / fach) if fachinhalte_root is not None else None
        methodik_dir = (fachdidaktik_root / fach) if fachdidaktik_root is not None else None

        inhalte_hint = ""
        if not inhalte:
            if not baukasten_dir.exists():
                inhalte_hint = f"Ursache: Baukastenordner fehlt ({baukasten_dir})."
            elif fachinhalte_root is None:
                inhalte_hint = "Ursache: Fachinhalte-Root (34 Fachinhalte) nicht gefunden."
            elif inhalte_dir is None or not inhalte_dir.exists():
                inhalte_hint = f"Ursache: Fachordner für Inhalte fehlt ({fach})."
            else:
                inhalte_hint = f"Ursache: Keine Markdown-Quellen in {inhalte_dir}."

        methodik_hint = ""
        if not methodik:
            if not baukasten_dir.exists():
                methodik_hint = f"Ursache: Baukastenordner fehlt ({baukasten_dir})."
            elif fachdidaktik_root is None:
                methodik_hint = "Ursache: Fachdidaktik-Root (33 Fachdidaktik) nicht gefunden."
            elif methodik_dir is None or not methodik_dir.exists():
                methodik_hint = f"Ursache: Fachordner für Methodik fehlt ({fach})."
            else:
                methodik_hint = f"Ursache: Keine Markdown-Quellen in {methodik_dir}."

        return inhalte, methodik, inhalte_hint, methodik_hint

    def resolve_kompetenz_options(self) -> tuple[list[str], list[str], str]:
        if self.app.current_table is None:
            return [], [], "Ursache: Keine aktive Tabelle geladen."

        fach = str(self.app.current_table.metadata.get("Kursfach", "")).strip()
        if fach != "Informatik":
            return [], [], "Ursache: Kompetenzen aus KC sind aktuell nur für Informatik aktiviert."

        stufe_raw = str(self.app.current_table.metadata.get("Stufe", "")).strip()
        match = re.search(r"(\d{1,2})", stufe_raw)
        if match is None:
            return [], [], "Ursache: Stufe im Plan-Metadatenfeld konnte nicht gelesen werden."
        grade_level = int(match.group(1))

        options = self.app.new_lesson_form_usecase.get_informatik_competency_options(
            grade_level,
            resolve_missing_catalog=self._resolve_missing_catalog_file,
        )
        if not options.profile_ids:
            warning_text = " | ".join(options.warnings)
            if warning_text:
                return [], [], f"Ursache: Keine nutzbaren KC-Profile für Stufe {grade_level}. {warning_text}"
            return [], [], f"Ursache: Für Stufe {grade_level} ist kein Informatik-KC-Profil verfügbar."

        profile_id = options.profile_ids[0]
        return (
            list(options.process_display_lines_by_profile.get(profile_id, ())),
            list(options.content_display_lines_by_profile.get(profile_id, ())),
            "",
        )

    def _resolve_missing_catalog_file(self, profile_label: str, expected_path: pathlib.Path) -> pathlib.Path | None:
        decision = messagebox.askyesno(
            "Kompetenzdatei nicht verfügbar",
            "Die Kompetenzdatei für folgendes Profil fehlt oder ist ungültig:\n\n"
            f"{profile_label}\n{expected_path}\n\n"
            "Möchten Sie jetzt eine andere JSON-Datei auswählen?\n"
            "(Nein = ohne diese Datei fortfahren)",
            parent=self.app,
        )
        if not decision:
            return None
        selected = filedialog.askopenfilename(
            parent=self.app,
            title=f"Kompetenzdatei wählen: {profile_label}",
            initialdir=str(expected_path.parent) if expected_path.parent.exists() else str(pathlib.Path.home()),
            filetypes=[("JSON", "*.json"), ("Alle Dateien", "*.*")],
        )
        if not selected:
            return None
        return pathlib.Path(selected)

    def last_oberthema_before_row(self, row_index: int) -> str:
        if self.app.current_table is None:
            return ""
        return self.app.gui_dependencies.lesson_context_query.last_oberthema_before_row(
            self.app.current_table, row_index
        )

    def _run_tracked_write(
        self,
        *,
        label: str,
        action,
        extra_before: list[pathlib.Path] | None = None,
        extra_after: list[pathlib.Path] | None = None,
        extra_after_from_result=None,
    ):
        if self.app.current_table is None:
            return action()
        return self._tracked_write_uc.run_tracked_action(
            label=label,
            action=action,
            table=self.app.current_table,
            day_columns=self.app.day_columns,
            selected_day_indices=self.app.selected_day_indices,
            extra_before=extra_before,
            extra_after=extra_after,
            extra_after_from_result=extra_after_from_result,
        )

    def _refresh_after_write(self, *, selected_index: int | None = None) -> None:
        self.app._collect_day_columns()
        if isinstance(selected_index, int) and 0 <= selected_index < len(self.app.day_columns):
            self.app.selected_day_indices = {selected_index}
            self.app._update_selected_column_label()
        self.app._refresh_grid_content()
        self.app._update_selected_lesson_metrics()
        self.app.action_controller.update_action_controls()

    @staticmethod
    def _coerce_string_list(raw_value) -> list[str]:
        if isinstance(raw_value, list):
            return [str(item).strip() for item in raw_value if str(item).strip()]
        if isinstance(raw_value, tuple):
            return [str(item).strip() for item in raw_value if str(item).strip()]
        if isinstance(raw_value, str):
            return [item.strip() for item in raw_value.split("|") if item.strip()]
        return []

    @staticmethod
    def _extract_markdown_section_refs(lesson_path: pathlib.Path, heading: str) -> list[str]:
        if not (isinstance(lesson_path, pathlib.Path) and lesson_path.exists() and lesson_path.is_file()):
            return []
        try:
            raw_text = lesson_path.read_text(encoding="utf-8")
        except OSError:
            return []

        section_re = re.compile(
            rf"(?ms)^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)",
        )
        match = section_re.search(raw_text)
        if match is None:
            return []

        refs: list[str] = []
        for raw_line in match.group(1).splitlines():
            stripped = raw_line.strip()
            if not stripped.startswith("-"):
                continue
            item = stripped[1:].strip()
            link_match = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", item)
            if link_match:
                value = (link_match.group(2) or link_match.group(1) or "").strip()
            else:
                value = item.strip()
            if value:
                refs.append(value)
        return refs

    @staticmethod
    def _prefill_ausfall_reason_from_content(content: str) -> str:
        cleaned = re.sub(r"\[\[[^\]]+\]\]", "", str(content or "")).strip()
        if not cleaned:
            return ""
        lowered = cleaned.lower()
        if lowered == "x":
            return ""
        if lowered.startswith("x "):
            return cleaned[2:].strip(" :\t")
        if lowered.startswith("ausfall"):
            return cleaned[len("ausfall") :].strip(" :\t")
        return cleaned

    def _unterricht_prefill_values(self, *, day: dict[str, object], row_index: int) -> dict[str, object]:
        current_topic = str(self.app._field_value(day, "Stundenthema") or "").strip()
        title_initial = current_topic or "Unterrichtseinheit"
        topic_initial = current_topic or "Unterrichtseinheit"
        oberthema_initial = self.last_oberthema_before_row(row_index)
        stundenziel_initial = ""
        kompetenzen_initial: list[str] = []
        inhalte_initial: list[str] = []
        methodik_initial: list[str] = []

        existing_link = self.plan_regular_lesson.resolve_existing_link(self.app.current_table, row_index)
        if isinstance(existing_link, pathlib.Path) and existing_link.exists() and existing_link.is_file():
            title_initial = existing_link.stem
            try:
                lesson = self.lesson_commands.lesson_repo.load_lesson_yaml(existing_link)
                yaml_data = lesson.data if isinstance(lesson.data, dict) else {}
            except Exception:
                yaml_data = {}

            topic_initial = str(yaml_data.get("Stundenthema", "")).strip() or topic_initial
            oberthema_initial = str(yaml_data.get("Oberthema", "")).strip() or oberthema_initial
            stundenziel_initial = str(yaml_data.get("Stundenziel", "")).strip()
            kompetenzen_initial = self._coerce_string_list(yaml_data.get("Kompetenzen", []))
            inhalte_initial = self._extract_markdown_section_refs(existing_link, "Inhalte")
            methodik_initial = self._extract_markdown_section_refs(existing_link, "Methodik")

        return {
            "title_initial": title_initial,
            "topic_initial": topic_initial,
            "oberthema_initial": oberthema_initial,
            "stundenziel_initial": stundenziel_initial,
            "kompetenzen_initial": kompetenzen_initial,
            "inhalte_initial": inhalte_initial,
            "methodik_initial": methodik_initial,
        }

    def convert_selected_to_ausfall(self, *, from_column_shortcut: bool = False):
        if self.app.current_table is None:
            return
        selected_index = self.app._get_single_selected_or_warn()
        if selected_index is None:
            return
        day = self.app.day_columns[selected_index]
        row_index = self.app._to_int(day.get("row_index", 0), 0)

        link = self.lesson_transfer.resolve_existing_link(self.app.current_table, row_index)
        if isinstance(link, pathlib.Path) and link.exists():
            confirm = messagebox.askyesno(
                "In Ausfall umwandeln",
                f"Soll die verlinkte Stunden-Datei für {day.get('datum', '')} gelöscht werden?",
                parent=self.app,
            )
            if confirm:
                try:
                    self.lesson_transfer.delete_lesson_file(link)
                except Exception:
                    pass

        initial_reason = ""
        if from_column_shortcut:
            initial_reason = self._prefill_ausfall_reason_from_content(day.get("inhalt", ""))
        reason = simpledialog.askstring(
            "Fällt aus",
            "Grund für den Ausfall:",
            initialvalue=initial_reason,
            parent=self.app,
        )
        if reason is None:
            return

        self._run_tracked_write(
            label="Als Ausfall markieren",
            action=lambda: self.convert_to_ausfall.execute(self.app.current_table, row_index, reason),
            extra_before=[link] if isinstance(link, pathlib.Path) else None,
        )
        self._refresh_after_write(selected_index=selected_index)

    def convert_selected_to_unterricht(self, *, from_column_shortcut: bool = False):
        if self.app.current_table is None:
            return
        selected_index = self.app._get_single_selected_or_warn()
        if selected_index is None:
            return

        day = self.app.day_columns[selected_index]
        row_index = self.app._to_int(day.get("row_index", 0), 0)
        was_lzk = self.app._is_lzk_row(row_index)
        current_topic = str(self.app._field_value(day, "Stundenthema") or "").strip()
        content_before = str(day.get("inhalt", "")).strip()
        title = current_topic or "Unterrichtseinheit"
        topic = current_topic or "Unterrichtseinheit"
        oberthema_input = ""
        stundenziel_input = ""
        kompetenzen_refs: list[str] = []
        inhalte_refs: list[str] = []
        methodik_refs: list[str] = []

        existing_link = self.plan_regular_lesson.resolve_existing_link(self.app.current_table, row_index)
        should_open_builder = from_column_shortcut or not self.plan_regular_lesson.has_existing_link(existing_link)

        prefill_values = self._unterricht_prefill_values(day=day, row_index=row_index)
        title = str(prefill_values["title_initial"])
        topic = str(prefill_values["topic_initial"])
        oberthema_input = str(prefill_values["oberthema_initial"])
        stundenziel_input = str(prefill_values["stundenziel_initial"])
        kompetenzen_refs = list(prefill_values["kompetenzen_initial"])
        inhalte_refs = list(prefill_values["inhalte_initial"])
        methodik_refs = list(prefill_values["methodik_initial"])

        if should_open_builder:
            lesson_builder_field_settings = load_lesson_builder_field_settings()
            kompetenzen_options, stundenziel_options, kompetenzen_hint = self.resolve_kompetenz_options()
            inhalte_options, methodik_options, inhalte_hint, methodik_hint = self.resolve_subject_sources()
            ub_sections = self._lesson_builder_ub_sections()
            builder = ask_lesson_builder(
                parent=self.app,
                date_label=str(day.get("datum", "")).strip(),
                title_initial=title,
                topic_initial=topic,
                oberthema_initial=oberthema_input,
                kompetenzen_options=kompetenzen_options,
                stundenziel_options=stundenziel_options,
                inhalte_options=inhalte_options,
                methodik_options=methodik_options,
                kompetenzen_hint=kompetenzen_hint,
                stundenziel_hint=kompetenzen_hint,
                inhalte_hint=inhalte_hint,
                methodik_hint=methodik_hint,
                kompetenzen_initial=kompetenzen_refs,
                stundenziel_initial=stundenziel_input,
                inhalte_initial=inhalte_refs,
                methodik_initial=methodik_refs,
                ub_sections=ub_sections,
                ub_error_hint=self._last_ub_sections_error_hint,
                show_kompetenzen_field=lesson_builder_field_settings.show_kompetenzen,
                show_stundenziel_field=lesson_builder_field_settings.show_stundenziel,
                theme_key=self.app.theme_var.get(),
            )
            if builder is None:
                return
            title = builder.title
            topic = builder.topic
            oberthema_input = builder.oberthema
            stundenziel_input = builder.stundenziel
            kompetenzen_refs = builder.kompetenzen_refs
            inhalte_refs = builder.inhalte_refs
            methodik_refs = builder.methodik_refs
        else:
            topic_input = simpledialog.askstring(
                "In Unterricht umwandeln",
                f"Stundenthema für {day.get('datum', '')}:",
                initialvalue=topic,
                parent=self.app,
            )
            if topic_input is None or not topic_input.strip():
                return
            topic = topic_input.strip()

            title_input = simpledialog.askstring(
                "In Unterricht umwandeln",
                "Titel (Dateiname):",
                initialvalue=title,
                parent=self.app,
            )
            if title_input is None or not title_input.strip():
                return
            title = title_input.strip()

        write_result = self._run_tracked_write(
            label="Als Unterricht markieren",
            action=lambda: self.plan_regular_lesson.execute_write(
                table=self.app.current_table,
                row_index=row_index,
                title=title,
                topic=topic,
                stunden_raw=str(day.get("stunden", "")).strip(),
                oberthema_input=oberthema_input,
                stundenziel_input=stundenziel_input,
                was_lzk=was_lzk,
                content_before=content_before,
                kompetenzen_refs=kompetenzen_refs,
                inhalte_refs=inhalte_refs,
                methodik_refs=methodik_refs,
                allow_create_link=True,
                allow_yaml_save=True,
                allow_sections_save=should_open_builder,
                allow_rename=True,
                allow_plan_save=True,
            ),
            extra_after_from_result=lambda item: [item.lesson_path]
            if isinstance(getattr(item, "lesson_path", None), pathlib.Path)
            else [],
        )

        if not write_result.proceed:
            messagebox.showerror(
                "Plan konnte nicht gespeichert werden",
                write_result.error_message or "Unbekannter Fehler",
                parent=self.app,
            )
            return

        self._refresh_after_write(selected_index=selected_index)

    def convert_selected_to_lzk(self, *, from_column_shortcut: bool = False):
        if self.app.current_table is None:
            return
        selected_index = self.app._get_single_selected_or_warn()
        if selected_index is None:
            return

        next_no = self.app._next_lzk_number()

        day = self.app.day_columns[selected_index]
        row_index = self.app._to_int(day.get("row_index", 0), 0)
        title = self.convert_to_lzk.build_lzk_title(self.app.current_table, next_no)
        current_content = str(day.get("inhalt", "")).strip()
        existing_link = self.lesson_transfer.resolve_existing_link(self.app.current_table, row_index)
        default_hours = int(str(day.get("stunden", "")).strip()) if str(day.get("stunden", "")).strip().isdigit() else 2

        if from_column_shortcut:
            dialog_result = ask_lzk_column_dialog(
                self.app,
                date_label=str(day.get("datum", "")).strip(),
                suggested_title=title,
                theme_key=self.app.theme_var.get(),
            )
            if dialog_result is None:
                return
            if dialog_result.title_override:
                title = dialog_result.title_override

        decision = "move"
        allow_delete = False
        if current_content:
            choice = messagebox.askyesnocancel(
                "In LZK umwandeln",
                "Die Zielspalte enthält bereits Inhalt.\n\n"
                "Ja: bestehende Einheiten nach hinten verschieben\n"
                "Nein: bestehende Stunde als Schattenstunde behalten\n"
                "Abbrechen: optional löschen oder Vorgang abbrechen",
                parent=self.app,
            )
            if choice is True:
                decision = "move"
            elif choice is False:
                decision = "shadow"
            else:
                delete_existing = messagebox.askyesno(
                    "Bestehende Stunde löschen?",
                    "Soll die bestehende Ziel-Stunde gelöscht und durch die LZK ersetzt werden?",
                    parent=self.app,
                )
                if delete_existing:
                    decision = "delete"
                    allow_delete = True
                else:
                    return

        result = self._run_tracked_write(
            label="Als LZK markieren",
            action=lambda: self.lzk_lesson_flow.execute_write(
                LzkLessonFlowWriteRequest(
                    table=self.app.current_table,
                    row_index=row_index,
                    current_content=current_content,
                    decision=decision,
                    existing_link=existing_link,
                    title=title,
                    default_hours=default_hours,
                    allow_delete=allow_delete,
                )
            ),
            extra_after_from_result=lambda item: [item.link]
            if isinstance(getattr(item, "link", None), pathlib.Path)
            else [],
        )

        if not result.proceed:
            if result.error_message:
                messagebox.showerror("In LZK umwandeln", result.error_message, parent=self.app)
            return

        self._refresh_after_write(selected_index=selected_index)

    def convert_selected_to_hospitation(self, *, from_column_shortcut: bool = False):
        if self.app.current_table is None:
            return
        selected_index = self.app._get_single_selected_or_warn()
        if selected_index is None:
            return

        day = self.app.day_columns[selected_index]
        row_index = self.app._to_int(day.get("row_index", 0), 0)
        default_hours = int(str(day.get("stunden", "")).strip()) if str(day.get("stunden", "")).strip().isdigit() else 2
        focus_initial = ""
        if from_column_shortcut:
            existing_link = self.lesson_transfer.resolve_existing_link(self.app.current_table, row_index)
            if isinstance(existing_link, pathlib.Path) and existing_link.exists() and existing_link.is_file():
                try:
                    lesson = self.lesson_commands.lesson_repo.load_lesson_yaml(existing_link)
                    yaml_data = lesson.data if isinstance(lesson.data, dict) else {}
                    focus_initial = str(yaml_data.get("Beobachtungsschwerpunkte", "")).strip()
                except Exception:
                    focus_initial = ""

        focus_text = simpledialog.askstring(
            "Als Hospitation",
            "Beobachtungsschwerpunkt (optional):",
            initialvalue=focus_initial,
            parent=self.app,
        )
        if focus_text is None:
            return

        result = self._run_tracked_write(
            label="Als Hospitation markieren",
            action=lambda: self.convert_to_hospitation.execute_write(
                table=self.app.current_table,
                row_index=row_index,
                focus_text=focus_text,
                default_hours=default_hours,
                allow_create_link=True,
                allow_yaml_save=True,
                allow_plan_save=True,
            ),
            extra_after_from_result=lambda item: [item.lesson_path]
            if isinstance(getattr(item, "lesson_path", None), pathlib.Path)
            else [],
        )
        if not result.proceed:
            messagebox.showerror(
                "Als Hospitation", result.error_message or "Umwandlung fehlgeschlagen.", parent=self.app
            )
            return

        self._refresh_after_write(selected_index=selected_index)
