"""Fachliche Zielstruktur eines Kompetenzhorizonts (KH): Zielzeilen, gruppiert nach Oberthema.

Ein KH besteht aus *Sections* — eine je gewähltem Oberthema, in
chronologischer Reihenfolge. Jede Section enthält die Zielzeilen ihrer
Unterrichtsstunden. Überschriften sind damit Struktur, keine Pseudo-Zielzeilen:
`GoalKind` klassifiziert ausschließlich echte Ziele (Stunden-, Teil-,
Sonderziel), und die Zuordnung Zeile → Thema ist strukturell eindeutig.

Das Render-DTO mit Titel/Untertitel/Exportdatum (`ExpectedHorizonDocument`)
liegt bewusst im Use-Case-Modul; dieses Modul enthält nur, was auch die
fachliche Reconciliation (`expected_horizon_reconciliation`) braucht.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GoalKind(Enum):
    """Art eines Ziels im Kompetenzhorizont (steuert Fett-/Kursiv-Darstellung)."""

    STUNDENZIEL = "stundenziel"
    TEILZIEL = "teilziel"
    SONDERZIEL = "sonderziel"


@dataclass(frozen=True)
class ExpectedHorizonLine:
    """Eine Zielzeile im Kompetenzhorizont.

    Args:
        datum: Formatiertes Datum (nur in der ersten Zeile einer Stunde gesetzt).
        ich_kann: Zieltext ("... <Ziel>").
        kind: Art des Ziels.
    """

    datum: str
    ich_kann: str
    kind: GoalKind


@dataclass(frozen=True)
class ExpectedHorizonSection:
    """Alle Zielzeilen eines Oberthemas.

    Args:
        oberthema: Entschlüsselter Thementext (Section-Überschrift bei mehreren Sections).
        rows: Zielzeilen der zugehörigen Unterrichtsstunden in chronologischer Reihenfolge.
    """

    oberthema: str
    rows: tuple[ExpectedHorizonLine, ...]
