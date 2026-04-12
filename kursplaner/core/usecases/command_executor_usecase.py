from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.ports.repositories import CommandRepository


@dataclass(frozen=True)
class FileDelta:
    """Beschreibt die Datenstruktur für File Delta.

    Die Instanz transportiert strukturierte Fachdaten zwischen Schichten und Verarbeitungsschritten.
    """

    path: Path
    before: str | None
    after: str | None


@dataclass(frozen=True)
class CommandEntry:
    """Beschreibt die Datenstruktur für Command Entry.

    Die Instanz transportiert strukturierte Fachdaten zwischen Schichten und Verarbeitungsschritten.
    """

    label: str
    deltas: list[FileDelta]


class CommandExecutorUseCase:
    """Orchestriert den fachlichen Ablauf für Command Executor Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(self, command_repo: CommandRepository):
        """Initialisiert den Command-Executor mit einem Port für Dateizugriffe.

        Args:
            command_repo: Port für das Lesen/Schreiben von Dateiinhalten.
        """
        self.command_repo = command_repo

    def capture(self, paths: list[Path]) -> dict[Path, str | None]:
        """Erfasst den aktuellen Inhalt aller relevanten Dateien für Undo/Redo.

        Args:
            paths: Zu sichernde Dateipfade.

        Returns:
            Mapping aus Dateipfad auf Dateiinhalt oder ``None`` bei nicht vorhandener Datei.
        """
        snapshot: dict[Path, str | None] = {}
        unique = sorted({path.expanduser().resolve() for path in paths}, key=lambda item: str(item).lower())
        for path in unique:
            snapshot[path] = self.command_repo.read_file_content(path)
        return snapshot

    @staticmethod
    def _merge_keys(*states: dict[Path, str | None]) -> list[Path]:
        """Vereinigt Pfadschlüssel aus mehreren Zustands-Snapshots.

        Args:
            states: Beliebig viele Snapshot-Mappings.

        Returns:
            Sortierte Liste aller enthaltenen Dateipfade.
        """
        keys: set[Path] = set()
        for state in states:
            keys.update(state.keys())
        return sorted(keys, key=lambda item: str(item).lower())

    def build_entry(
        self,
        label: str,
        before: dict[Path, str | None],
        after: dict[Path, str | None],
    ) -> CommandEntry | None:
        """Erzeugt einen History-Eintrag aus Vorher-/Nachher-Zustand.

        Args:
            label: Sichtbarer Aktionsname im Undo/Redo-Verlauf.
            before: Dateizustand vor der Aktion.
            after: Dateizustand nach der Aktion.

        Returns:
            ``CommandEntry`` mit allen geänderten Deltas oder ``None`` ohne Änderungen.
        """
        deltas: list[FileDelta] = []
        for path in self._merge_keys(before, after):
            before_content = before.get(path)
            after_content = after.get(path)
            if before_content == after_content:
                continue
            deltas.append(FileDelta(path=path, before=before_content, after=after_content))

        if not deltas:
            return None
        return CommandEntry(label=label, deltas=deltas)

    def apply_deltas(self, deltas: list[FileDelta], *, use_before: bool) -> None:
        """Wendet Deltas auf das Dateisystem an (Undo oder Redo).

        Args:
            deltas: Zu schreibende oder zu löschende Dateideltas.
            use_before: ``True`` für Undo (vorheriger Inhalt), sonst Redo.
        """
        for delta in deltas:
            content = delta.before if use_before else delta.after
            self.command_repo.write_file_content(delta.path, content)
