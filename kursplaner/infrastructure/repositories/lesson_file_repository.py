from __future__ import annotations

import shutil
from pathlib import Path


class FileSystemLessonFileRepository:
    """Dateibasierte Stunden-Dateioperationen für das Dateisystem."""

    def is_existing_markdown(self, path: Path) -> bool:
        """Prüft, ob ein Pfad auf eine existierende Markdown-Datei zeigt."""
        return path.suffix.lower() == ".md" and path.exists() and path.is_file()

    def ensure_directory(self, path: Path) -> None:
        """Stellt sicher, dass ein Verzeichnis rekursiv existiert."""
        path.mkdir(parents=True, exist_ok=True)

    def move_file(self, source: Path, target: Path) -> Path:
        """Verschiebt eine Datei und legt Zielordner bei Bedarf an."""
        self.ensure_directory(target.parent)
        if source.resolve() != target.resolve():
            shutil.move(str(source), str(target))
        return target

    def read_file_content(self, path: Path) -> str:
        """Liest den UTF-8-Inhalt einer Datei."""
        return path.read_text(encoding="utf-8")

    def write_file_content(self, path: Path, content: str) -> None:
        """Schreibt UTF-8-Inhalt in eine Datei und erstellt den Zielordner."""
        self.ensure_directory(path.parent)
        path.write_text(content, encoding="utf-8")

    def rename_file(self, source: Path, target: Path) -> Path:
        """Benennt eine Datei um, sofern Quelle und Ziel nicht identisch sind."""
        if source.resolve() != target.resolve():
            source.rename(target)
        return target

    def delete_file(self, path: Path) -> None:
        """Löscht eine Datei tolerant, falls sie nicht existiert."""
        path.unlink(missing_ok=True)

    def unique_markdown_path(self, target_dir: Path, stem_base: str, current_path: Path | None = None) -> Path:
        """Ermittelt einen kollisionsfreien Markdown-Pfad mit numerischem Suffix."""
        candidate = target_dir / f"{stem_base}.md"
        number = 2
        while candidate.exists() and (current_path is None or candidate.resolve() != current_path.resolve()):
            candidate = target_dir / f"{stem_base} {number}.md"
            number += 1
        return candidate
