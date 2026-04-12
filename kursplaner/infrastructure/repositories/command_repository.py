from __future__ import annotations

from pathlib import Path


class FileSystemCommandRepository:
    """Repository for reading/writing file contents used by command/undo stacks."""

    def read_file_content(self, path: Path) -> str | None:
        """Liest Dateiinhalte für Undo/Redo-Snapshots oder `None` bei fehlender Datei."""
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")
        return None

    def write_file_content(self, path: Path, content: str | None) -> None:
        """Schreibt Snapshot-Inhalt oder entfernt die Datei bei `content=None`."""
        if content is None:
            if path.exists() and path.is_file():
                path.unlink(missing_ok=True)
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
