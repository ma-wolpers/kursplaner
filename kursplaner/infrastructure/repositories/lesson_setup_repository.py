from __future__ import annotations

import shutil
from pathlib import Path


class FileSystemLessonSetupRepository:
    """Setup operations for creating a new lesson folder and plan file."""

    def validate_required_paths(self, base_dir: Path, calendar_dir: Path) -> None:
        """Validiert Pflichtpfade für Neueinrichtung und wirft bei Problemen Fehler."""
        missing: list[str] = []

        if not base_dir.exists():
            missing.append(f"Unterrichtsordner fehlt: {base_dir}")
        elif not base_dir.is_dir():
            missing.append(f"Unterrichtsordner ist kein Verzeichnis: {base_dir}")

        if not calendar_dir.exists():
            missing.append(f"Kalenderordner fehlt: {calendar_dir}")
        elif not calendar_dir.is_dir():
            missing.append(f"Kalenderordner ist kein Verzeichnis: {calendar_dir}")

        if missing:
            raise FileNotFoundError("\n".join(missing))

    def create_lesson_folder(self, base_dir: Path, folder_name: str) -> Path:
        """Legt einen neuen Unterrichtsordner an und verhindert Überschreiben."""
        target_dir = base_dir / folder_name
        if target_dir.exists():
            raise FileExistsError(f"Zielordner existiert bereits: {target_dir}")
        target_dir.mkdir(parents=True, exist_ok=False)
        return target_dir

    def create_plan_markdown(self, lesson_dir: Path, folder_name: str) -> Path:
        """Erzeugt die initiale, leere Plan-Markdown-Datei im Zielordner."""
        target_path = lesson_dir / f"{folder_name}.md"
        if target_path.exists():
            raise FileExistsError(f"Zieldatei existiert bereits: {target_path}")
        target_path.write_text("", encoding="utf-8")
        return target_path

    def rollback_lesson_folder(self, lesson_dir: Path) -> None:
        """Entfernt einen zuvor angelegten Ordner rekursiv bei Rollback."""
        if lesson_dir.exists() and lesson_dir.is_dir():
            shutil.rmtree(lesson_dir)
