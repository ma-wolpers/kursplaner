import tkinter as tk

from kursplaner.adapters.gui.dialog_services import filedialog, messagebox
from kursplaner.adapters.gui.window_identity import apply_window_icon
from kursplaner.core.usecases.path_settings_usecase import PathSettingsUseCase


def ensure_paths_interactive(path_settings_usecase: PathSettingsUseCase) -> bool:
    """Führt eine interaktive Pfadprüfung vor dem App-Start durch."""
    values = path_settings_usecase.load_values()
    changed = False

    root = tk.Tk()
    apply_window_icon(root)
    root.withdraw()

    try:
        while True:
            issue = path_settings_usecase.first_issue(values)
            if issue is None:
                if changed:
                    path_settings_usecase.save_values(values)
                return True

            messagebox.showwarning("Pfadprüfung", issue.message, parent=root)

            initial_dir = path_settings_usecase.suggest_initial_dir(issue.path)
            field = path_settings_usecase.path_field_by_key(issue.key)
            if field is not None and field.kind == "file":
                selected = filedialog.askopenfilename(
                    parent=root,
                    title=issue.pick_title,
                    initialdir=initial_dir,
                    filetypes=[("JSON", "*.json"), ("Alle Dateien", "*.*")],
                )
            else:
                selected = filedialog.askdirectory(
                    parent=root,
                    title=issue.pick_title,
                    initialdir=initial_dir,
                )

            if not selected:
                again = messagebox.askretrycancel(
                    "Pfadprüfung",
                    "Ohne gültige Pfade kann das Programm nicht starten.",
                    parent=root,
                )
                if not again:
                    return False
                continue

            values, issue_changed = path_settings_usecase.apply_selected_path(values, issue.key, selected)
            if issue_changed:
                changed = True
    finally:
        root.destroy()
