"""Ports rund um den Kompetenzhorizont-Export (von der Infrastruktur implementiert)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from kursplaner.core.domain.expected_horizon_reconciliation import ExistingHorizonRow


class ExistingExpectedHorizonReaderPort(Protocol):
    """Liest die Zeilen einer bestehenden KH-Datei als Merge-Quelle.

    Der Use Case bestimmt, *welche* Datei Merge-Quelle ist (gleicher Pfad,
    bisher verlinkte Datei, …); der Port liefert nur deren Zeilen für die
    fachliche Reconciliation (`expected_horizon_reconciliation.reconcile`).
    """

    def read_existing_rows(self, path: Path) -> list[ExistingHorizonRow]:
        """Liefert alle Tabellenzeilen der Datei mit zugehöriger Section.

        Args:
            path: Pfad der bestehenden KH-Markdown-Datei.

        Returns:
            Die Zeilen in Dateireihenfolge; ``[]``, wenn die Datei fehlt,
            unlesbar ist oder keine KH-Tabelle enthält.
        """
        ...
