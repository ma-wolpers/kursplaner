from __future__ import annotations

import pathlib

from kursplaner.adapters.gui.dialog_services import messagebox
from kursplaner.adapters.gui.lesson_builder_dialog import (
    ask_lesson_kompetenzen_selection,
    ask_lesson_stundenziel_selection,
)


class MainWindowEditorController:
    """Kapselt Grid-Cell-Write-Pfade für die Hauptansicht.

    Delegiert alle Persistenz- und Erzeugungsoperationen an Use Cases aus
    `app.gui_dependencies` (z. B. `lesson_commands`, `save_cell_value`).
    """

    def __init__(self, app):
        """Initialisiert den Controller mit den benötigten Write-Use-Cases."""
        self.app = app
        deps = getattr(app, "gui_dependencies", None)
        if deps is None:
            raise RuntimeError("GUI Dependencies not available on app")
        self.lesson_commands = deps.lesson_commands
        self.save_cell_value = deps.save_cell_value
        self._tracked_write_uc = deps.tracked_write_usecase

    def _run_tracked_write(
        self,
        *,
        label: str,
        day_index: int,
        action,
        extra_before: list[pathlib.Path] | None = None,
        extra_after_from_result=None,
    ):
        if self.app.current_table is None:
            return action()

        selected_day_indices = set(self.app.selected_day_indices)
        selected_day_indices.add(day_index)
        return self._tracked_write_uc.run_tracked_action(
            label=label,
            action=action,
            table=self.app.current_table,
            day_columns=self.app.day_columns,
            selected_day_indices=selected_day_indices,
            extra_before=extra_before,
            extra_after_from_result=extra_after_from_result,
        )

    def handle_editor_focus_in(self, field_key: str, day_index: int) -> bool:
        """Oeffnet bei passenden Feldern den Auswahldialog statt Freitextbearbeitung."""
        if field_key not in {"Stundenziel", "Kompetenzen"}:
            return False
        if self.app.current_table is None:
            return False
        if not (0 <= day_index < len(self.app.day_columns)):
            return False

        day = self.app.day_columns[day_index]
        if not self.app.row_display_mode_usecase.is_editable(field_key, day):
            return False

        kompetenzen_options, stundenziel_options, kompetenzen_hint = (
            self.app.lesson_conversion_controller.resolve_kompetenz_options()
        )

        kompetenzen_initial = self.app.lesson_context_controller.parse_list_entries(
            self.app._field_value(day, "Kompetenzen")
        )
        stundenziel_initial = self.app._field_value(day, "Stundenziel")

        date_label = str(day.get("datum", "")).strip()
        if field_key == "Stundenziel":
            selection = ask_lesson_stundenziel_selection(
                parent=self.app,
                date_label=date_label,
                stundenziel_options=stundenziel_options,
                stundenziel_initial=stundenziel_initial,
                stundenziel_hint=kompetenzen_hint,
                theme_key=self.app.theme_var.get(),
            )
        else:
            selection = ask_lesson_kompetenzen_selection(
                parent=self.app,
                date_label=date_label,
                kompetenzen_options=kompetenzen_options,
                kompetenzen_initial=kompetenzen_initial,
                kompetenzen_hint=kompetenzen_hint,
                theme_key=self.app.theme_var.get(),
            )
        self.app.grid_canvas.focus_set()
        if selection is None:
            return True

        try:
            if field_key == "Stundenziel":
                self.apply_value("Stundenziel", day_index, selection)
            else:
                kompetenzen_value = " | ".join(selection.kompetenzen_refs)
                self.apply_value("Kompetenzen", day_index, kompetenzen_value)
        except Exception as exc:
            messagebox.showerror("Speichern fehlgeschlagen", str(exc), parent=self.app)
            return True

        self.app._collect_day_columns()
        self.app._update_grid_column(day_index)
        self.app._update_selected_lesson_metrics()
        self.app.action_controller.update_action_controls()
        return True

    def ensure_link_for_day(self, day_index: int, preferred_topic: str = "") -> pathlib.Path | None:
        """Stellt sicher, dass die Zielzeile auf eine Stunden-Datei verlinkt ist."""
        if self.app.current_table is None:
            return None

        day = self.app.day_columns[day_index]
        existing = day.get("link")
        if isinstance(existing, pathlib.Path) and existing.exists():
            return existing

        row_index = self.app._to_int(day.get("row_index", 0), 0)
        stunden_raw = str(day.get("stunden", "")).strip()
        default_hours = int(stunden_raw) if stunden_raw.isdigit() else 2

        topic = preferred_topic.strip() or "Unterrichtseinheit"

        # Use the lesson_commands use case to create and link a new lesson file.
        new_path = self.lesson_commands.create_regular_lesson_link(
            self.app.current_table, row_index, topic, default_hours
        )
        return new_path

    def save_cell(self, field_key: str, day_index: int) -> bool:
        """Persistiert eine bearbeitete Grid-Zelle inklusive UI-Refresh."""
        if self.app._is_rebuilding_grid or self.app.current_table is None:
            return False

        cell = self.app.cell_widgets.get((field_key, day_index))
        if cell is None:
            return False

        if not (0 <= day_index < len(self.app.day_columns)):
            return False

        day = self.app.day_columns[day_index]
        if not self.app.row_display_mode_usecase.is_editable(field_key, day):
            return False

        value = cell.get("1.0", "end-1c").strip()
        current_value = self.app._field_value(day, field_key).strip()
        if value == current_value:
            return True

        try:
            self.apply_value(field_key, day_index, value)
        except Exception as exc:
            messagebox.showerror("Speichern fehlgeschlagen", str(exc), parent=self.app)
            return False

        self.app._collect_day_columns()
        self.app._update_grid_column(day_index)
        self.app._update_selected_lesson_metrics()
        self.app.action_controller.update_action_controls()
        return True

    def apply_value(self, field_key: str, day_index: int, value: str):
        """Wendet einen Zellwert über den `SaveCellValueUseCase` an.

        Enthält ausschließlich Adapter-Orchestrierung (Runtime-Kontext,
        Confirmation-Plan, Fehlerweitergabe), keine eigene Fachvalidierung.
        """
        if self.app.current_table is None:
            return

        day = self.app.day_columns[day_index]
        row_index = self.app._to_int(day.get("row_index", 0), 0)

        header_map = {name.lower(): idx for idx, name in enumerate(self.app.current_table.headers)}
        idx_stunden = header_map.get("stunden")
        idx_inhalt = header_map.get("inhalt")

        if idx_stunden is None or idx_inhalt is None:
            raise RuntimeError("Plan-Tabelle muss Datum, Stunden und Inhalt enthalten.")

        # Delegate full save flow to SaveCellValueUseCase which encapsulates
        # validation, YAML-updates, renaming and plan persistence.
        day = self.app.day_columns[day_index]
        link_obj = day.get("link")
        lesson_path = link_obj if isinstance(link_obj, pathlib.Path) else None

        edit_plan = self.save_cell_value.build_edit_plan(
            table=self.app.current_table,
            row_index=row_index,
            field_key=field_key,
            value=value,
            lesson_path=lesson_path or pathlib.Path("."),
        )
        runtime = self.save_cell_value.build_runtime_context(field_key=field_key, day=day)
        if not runtime.proceed or runtime.row_index is None:
            raise RuntimeError(runtime.message_text or "Zelle kann nicht gespeichert werden.")
        if field_key != "inhalt" and runtime.lesson_path is None:
            raise RuntimeError(runtime.message_text or "Zelle kann nicht gespeichert werden.")

        # For UI-driven flow we allow all confirmations here (adapter already confirmed earlier if needed).
        def _action():
            return self.save_cell_value.execute(
                table=self.app.current_table,
                row_index=runtime.row_index,
                field_key=field_key,
                value=value,
                lesson_path=runtime.lesson_path,
                list_entries=edit_plan.list_entries,
                should_rename_topic=edit_plan.should_rename_topic,
                desired_stem=edit_plan.desired_stem,
                allow_plan_hours_save=True,
                allow_yaml_save=True,
                allow_duration_save=True,
                allow_rename=True,
                allow_plan_save_for_rename=True,
            )

        extra_before: list[pathlib.Path] = []
        if isinstance(runtime.lesson_path, pathlib.Path):
            extra_before.append(runtime.lesson_path)

        result = self._run_tracked_write(
            label="Zelle bearbeiten",
            day_index=day_index,
            action=_action,
            extra_before=extra_before,
            extra_after_from_result=(
                lambda item: [item.lesson_path] if isinstance(getattr(item, "lesson_path", None), pathlib.Path) else []
            ),
        )

        if not result.proceed:
            raise RuntimeError(result.error_message or "Speichern fehlgeschlagen")
