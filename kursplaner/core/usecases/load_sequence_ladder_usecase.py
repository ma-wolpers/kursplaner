"""Use Case: Sequenzleiter einer Sequenz samt Sprossen-Terminen laden.

Die Leiter ist eine Sicht auf die Einheiten (`sequence_ladder_homes`): Sprossen
mit Termin zeigen Ziele, Kompetenzen und Ideen ihrer Einheit, Sprossen jenseits
der Termine die Ablage der Sequenzdatei. Die Termine kommen aus der Sequenz:
pro Lauf alle Planzeilen vom ersten bis zum letzten Mitglied (Unterricht, LZK,
Hospitation und dazwischenliegende Ausfälle), vereinigt über alle Läufe, die
dieselbe Datei teilen. Zeilen fremder Themen zwischen zwei Läufen werden nie
Sprossen. Jenseits der Termine tragen Sprossen ``??``. Siehe §37.

Zu jedem Netz-Baustein liefert die Ansicht die Formulierung aus dem
Kompetenznetz (`SequenceLadderView.originals`, je ID eine `CompetenceWording`;
das Original einer Seite liefert `for_side`), nachgeschlagen über den Port
`CompetenceOriginals` – ein Puffer, kein Dateizugriff pro Neuladen.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from kursplaner.core.domain.competence_wording import CompetenceWording
from kursplaner.core.domain.day_column import DayColumn, days_by_row
from kursplaner.core.domain.sequence_ladder import BlockRef, LadderSide, SequenceLadder
from kursplaner.core.domain.sequence_ladder_codec import LadderFormatError
from kursplaner.core.domain.sequence_ladder_homes import RungKind, rung_kind
from kursplaner.core.domain.topic_sequence_runs import TopicSequence
from kursplaner.core.usecases.day_label_format import short_day_label
from kursplaner.core.usecases.sequence_ladder_source import SequenceLadderSource

UNKNOWN_DATE_LABEL = "??"
"""Beschriftung von Sprossen ohne zugeordneten Termin."""

__all__ = [
    "UNKNOWN_DATE_LABEL",
    "CompetenceOriginals",
    "LoadSequenceLadderUseCase",
    "RungInfo",
    "RungKind",
    "SequenceLadderView",
    "rung_info",
    "rung_infos",
    "sequence_term_days",
]


@dataclass(frozen=True)
class RungInfo:
    """Termin einer Sprosse: Kurzdatum (oder ``??``), Terminart und Plan-Zeile.

    ``row_index`` ist die stabile Plan-Zeile des Termins (``None`` für „??“-Sprossen) –
    einzige Verbindung Sprosse ↔ Grid-Spalte (Auswahl-Sync der Leiter-Ansicht).
    """

    date_label: str
    kind: RungKind
    row_index: int | None = None


@dataclass(frozen=True)
class SequenceLadderView:
    """Alles, was der Leiter-Editor anzeigt.

    Attributes:
        sequence_path: Sequenzdatei (Identität der Sequenz).
        oberthema: Name der Sequenz.
        ladder: Zusammengesetzte Leiter; ``None`` bei Lesefehler (dann schreibgeschützt).
        rungs: Termin je angezeigter Sprosse (unten → oben), inkl. einer Reserve-Sprosse.
        error: Nutzerlesbarer Fehler (Formatfehler, Datei fehlt) oder ``None``.
        notes: Hinweise zu einzelnen Sprossen (gesperrt, nicht lesbar, gekürzt).
        duplicates: Gruppen von Bausteinen, die schon vor der Eindeutigkeitsregel doppelt standen.
        originals: Formulierung je Kompetenz-ID der Leiter (nur IDs, die im
            Kompetenznetz bekannt sind); Grundlage für die Anzeige unter Bausteinen
            mit Alias, für das Zurücksetzen per leerer Eingabe und für das Kopieren
            über Seiten (`CompetenceWording`).
    """

    sequence_path: Path
    oberthema: str
    ladder: SequenceLadder | None
    rungs: tuple[RungInfo, ...]
    error: str | None = None
    notes: tuple[str, ...] = ()
    duplicates: tuple[tuple[BlockRef, ...], ...] = ()
    originals: Mapping[str, CompetenceWording] = field(default_factory=dict)


class CompetenceOriginals(Protocol):
    """Port: Formulierung einer Kompetenz aus dem Netz (umgesetzt von `CompetenceOriginalsBuffer`)."""

    def original(self, kompetenz_id: str) -> CompetenceWording | None:
        """Beide Varianten der Kompetenz oder ``None``, wenn sie unbekannt ist."""
        ...


def _originals(ladder: SequenceLadder, source: CompetenceOriginals | None) -> dict[str, CompetenceWording]:
    """Formulierungen aller Kompetenz-IDs der Leiter, soweit *source* sie kennt."""
    if source is None:
        return {}
    ids = {block.kompetenz_id for rung in ladder.rungs for side in LadderSide for block in rung.blocks(side)}
    found = {kid: source.original(kid) for kid in ids if kid is not None}
    return {kid: wording for kid, wording in found.items() if wording is not None}


def sequence_term_days(day_columns: Sequence[DayColumn], sequence: TopicSequence) -> list[DayColumn]:
    """Termine der Sequenz chronologisch (einzige Termin-Regel der Leiter).

    Termine sind alle Einheiten der Sequenz (eigene Läufe und geteilte Mehrthemen-LZKs,
    `TopicSequence.member_row_indices`) sowie Ausfälle innerhalb eines eigenen Laufs.

    Args:
        day_columns: Alle Tagesspalten des Plans (unprojiziert, `raw_day_columns`).
        sequence: Die Sequenz (leer, wenn sie im Kurs nicht mehr vorkommt).
    """
    by_row = days_by_row(day_columns)
    members = set(sequence.member_row_indices)
    rows = {
        index
        for index, day in by_row.items()
        if index in members or (day.is_cancel() and sequence.covers_in_block(index))
    }
    return [by_row[index] for index in sorted(rows)]


def rung_info(day: DayColumn) -> RungInfo:
    """Kurzdatum und Terminart einer Tagesspalte (auch für die Zielauswahl beim Zuordnen)."""
    return RungInfo(short_day_label(day.datum), rung_kind(day), day.row_index)


def rung_infos(days: Sequence[DayColumn], rung_count: int) -> tuple[RungInfo, ...]:
    """Termin je Sprosse (Index 0 = unten); ohne Termin ``??``/`OFFEN`."""
    return tuple(
        rung_info(days[i]) if i < len(days) else RungInfo(UNKNOWN_DATE_LABEL, RungKind.OFFEN) for i in range(rung_count)
    )


class LoadSequenceLadderUseCase:
    """Liest die Leiter aus Einheiten und Ablage und berechnet die Sprossen-Termine."""

    def __init__(self, source: SequenceLadderSource, originals: CompetenceOriginals | None = None) -> None:
        """Initialisiert den Use Case.

        Args:
            source: Gemeinsame Lesequelle von Einheiten und Ablage.
            originals: Originaltitel-Puffer; ``None`` = keine Originale (z. B. Tests, ohne PyYAML).
        """
        self._source = source
        self._originals = originals

    def execute(
        self,
        *,
        sequence_path: Path,
        sequence: TopicSequence,
        day_columns: Sequence[DayColumn],
    ) -> SequenceLadderView:
        """Lädt die Leiter; ein Lesefehler liefert eine schreibgeschützte Ansicht mit Fehlertext.

        Args:
            sequence_path: Sequenzdatei.
            sequence: Die Sequenz (Oberthema = Anzeigename; ohne Läufe, wenn sie im Kurs fehlt).
            day_columns: Alle Tagesspalten des geöffneten Plans.
        """
        oberthema = sequence.oberthema
        days = sequence_term_days(day_columns, sequence)
        try:
            snapshot = self._source.read(sequence_path, days)
        except LadderFormatError as exc:
            error = f"{exc} – die Leiter ist schreibgeschützt, bis die Datei korrigiert ist."
            return SequenceLadderView(sequence_path, oberthema, None, rung_infos(days, len(days) + 1), error)
        except OSError as exc:
            error = f"Sequenzdatei nicht lesbar: {exc}"
            return SequenceLadderView(sequence_path, oberthema, None, rung_infos(days, len(days) + 1), error)
        ladder = snapshot.ladder
        count = max(len(days), len(ladder.rungs)) + 1
        return SequenceLadderView(
            sequence_path,
            oberthema,
            ladder,
            rung_infos(days, count),
            notes=snapshot.notes,
            duplicates=ladder.duplicate_groups(),
            originals=_originals(ladder, self._originals),
        )
