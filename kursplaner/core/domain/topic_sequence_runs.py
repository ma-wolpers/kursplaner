"""Fachliche Erkennung von Themen-Sequenzen.

Zwei Ebenen:

- **Lauf** (`TopicSequenceRun`): eine ununterbrochene Kette chronologisch
  benachbarter Unterrichts-, LZK- oder Hospitations-Einheiten mit demselben,
  nicht-leeren Oberthema. Ausfall-Einheiten unterbrechen eine Kette nicht, tragen
  selbst aber kein Oberthema und werden übersprungen. Alle anderen Einheiten
  (leere/ungeplante Tage, Einheiten ohne oder mit anderem Oberthema) beenden einen
  Lauf. Läufe sind die Blöcke, über die das Grid die Sequenzfelder spannt.
- **Sequenz** (`TopicSequence`): **alle** Läufe mit demselben Oberthema, auch wenn
  anderes dazwischen liegt (`group_into_sequences`), sobald sie zusammen
  mindestens `MIN_SEQUENCE_MEMBER_COUNT` Einheiten haben. Eine LZK mit mehreren
  Oberthemen steht in genau einem Lauf, gehört aber zu jeder Sequenz, deren Thema
  sie nennt (`TopicSequence.shared_rows`). Einstieg: `compute_topic_sequences`.

Die Berechnung arbeitet bewusst auf der vollständigen, chronologischen Tagesliste
(z. B. `app.raw_day_columns`) und nicht auf einer nach Sichtbarkeits-Einstellungen
gefilterten Projektion, damit das Ergebnis unabhängig von rein optischen
Anzeige-Einstellungen ist.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.export_date_formatting import parse_day_date
from kursplaner.core.domain.lesson_yaml_policy import lesson_list_entries

ELIGIBLE_SEQUENCE_TYPES = frozenset({"Unterricht", "LZK", "Hospitation"})
"""Stundentypen, die selbst ein Oberthema tragen und Teil einer Sequenz sein können."""

SKIPPED_SEQUENCE_TYPES = frozenset({"Ausfall"})
"""Stundentypen, die eine laufende Sequenz weder fortsetzen noch unterbrechen."""

EXPORTABLE_LESSON_TYPES = frozenset({"Unterricht", "LZK"})
"""Stundentypen, die als eigene Zeile in der Sequenz-Export-Tabelle erscheinen."""


def row_oberthema(day: DayColumn) -> str:
    """Liest das Oberthema einer Tages-Spalte (siehe `DayColumn.oberthema`).

    Args:
        day: Eintrag aus einer Tagesliste (z. B. `raw_day_columns`).

    Returns:
        Der getrimmte, entschlüsselte Oberthema-Text oder ein leerer String,
        wenn keines gesetzt ist.
    """
    return day.oberthema()


@dataclass(frozen=True)
class TopicSequenceRun:
    """Eine erkannte Kette benachbarter Einheiten mit gemeinsamem Oberthema.

    `member_row_indices` referenziert die stabilen, absoluten Zeilenindizes
    (`day.row_index`) der Kettenmitglieder in chronologischer Reihenfolge.
    Diese Indizes sind unabhängig von aktuellen Sichtbarkeits-Projektionen des
    Grids und bleiben über Spalten-Ein-/Ausblenden hinweg stabil.
    """

    oberthema: str
    member_row_indices: tuple[int, ...]

    @property
    def member_count(self) -> int:
        """Anzahl der Einheiten, die dieser Sequenz-Lauf umfasst."""
        return len(self.member_row_indices)

    @property
    def first_row_index(self) -> int:
        """Zeilenindex der ersten (chronologisch frühesten) Einheit des Laufs."""
        return self.member_row_indices[0]

    @property
    def last_row_index(self) -> int:
        """Zeilenindex der letzten (chronologisch spätesten) Einheit des Laufs."""
        return self.member_row_indices[-1]

    def covers(self, row_index: int) -> bool:
        """Liegt die Plan-Zeile in der Spanne des Laufs (erste bis letzte Einheit, inkl. Lücken)?

        Einzige Spannen-Regel: dieselbe Spanne zeichnet das Grid für die Sequenzfelder
        (`first_row_index` … `last_row_index`); Leiter-Termine und „Sequenz der markierten
        Spalte“ nutzen sie ebenfalls.
        """
        return bool(self.member_row_indices) and self.first_row_index <= row_index <= self.last_row_index


def compute_topic_sequence_runs(raw_day_columns: list[DayColumn]) -> list[TopicSequenceRun]:
    """Berechnet alle Themen-Sequenz-Läufe innerhalb einer chronologischen Tagesliste.

    Iteriert einmal linear über `raw_day_columns` und verfolgt eine laufende Kette:
    Ausfall-Einheiten werden übersprungen (weder Fortsetzung noch Abbruch), Einheiten
    mit demselben, nicht-leeren Oberthema wie die laufende Kette setzen diese fort
    (bei einer Mehrthemen-LZK genügt es, dass das Thema der Kette unter ihren
    `oberthemen()` ist; sonst startet sie eine Kette mit ihrem Haupt-Oberthema),
    alle anderen Fälle (kein Oberthema, anderer Stundentyp, anderes Oberthema, leere
    Tage) beenden die laufende Kette. Läufe der Länge 1 werden ebenfalls geliefert;
    die Entscheidung, ab welcher Länge ein Lauf fachlich als "Sequenz" gilt (z. B.
    für die automatische Dateierzeugung), trifft der jeweilige Aufrufer.

    Args:
        raw_day_columns: Vollständige, unprojizierte Tagesliste in chronologischer
            Reihenfolge (z. B. `app.raw_day_columns`).

    Returns:
        Liste aller erkannten Läufe in der Reihenfolge ihres Auftretens.
    """
    runs: list[TopicSequenceRun] = []
    current_oberthema: str | None = None
    current_members: list[int] = []

    def _flush() -> None:
        if current_oberthema and current_members:
            runs.append(TopicSequenceRun(oberthema=current_oberthema, member_row_indices=tuple(current_members)))

    for day in raw_day_columns:
        if not isinstance(day, DayColumn):
            _flush()
            current_oberthema, current_members = None, []
            continue

        lesson_type = day.lesson_type()
        if lesson_type in SKIPPED_SEQUENCE_TYPES:
            continue
        if lesson_type not in ELIGIBLE_SEQUENCE_TYPES:
            _flush()
            current_oberthema, current_members = None, []
            continue

        oberthemen = day.oberthemen()
        if not oberthemen:
            _flush()
            current_oberthema, current_members = None, []
            continue

        # Nur eine LZK trägt mehrere Themen: Sie setzt die *laufende* Kette
        # fort, wenn deren Thema unter ihren Themen ist, sonst startet sie eine
        # neue Kette mit ihrem Haupt-Oberthema. Eine Einheit gehört so nie zu
        # mehreren Läufen, und eine früher beendete Kette wird nicht wieder
        # aufgegriffen.
        if current_oberthema is not None and current_oberthema in oberthemen:
            current_members.append(day.row_index)
            continue

        _flush()
        current_oberthema, current_members = oberthemen[0], [day.row_index]

    _flush()
    return runs


MIN_SEQUENCE_MEMBER_COUNT = 2
"""Mindestanzahl an Einheiten (über alle Läufe eines Oberthemas), ab der eine Sequenz entsteht."""


@dataclass(frozen=True)
class TopicSequence:
    """Eine Sequenz: alle Läufe mit demselben Oberthema – auch wenn anderes dazwischen liegt.

    Die Läufe bleiben zusammenhängende Blöcke (das Grid zeichnet je Lauf eine
    Spannzelle; Blöcke überlappen nie). Die Sequenz selbst ist ihre Vereinigung.

    ``shared_rows``: LZKs, die dieses Thema unter ihren Oberthemen nennen, aber im
    Lauf einer anderen Sequenz stehen (eine Einheit gehört zu genau einem Lauf).
    Sie zählen zur Sequenz (Leiter-Termine, Export, Auswahl), nicht aber zu den
    Grid-Blöcken und nicht zur Mindestgröße (`own_member_count`).
    """

    oberthema: str
    runs: tuple[TopicSequenceRun, ...]
    shared_rows: tuple[int, ...] = ()

    @property
    def own_row_indices(self) -> tuple[int, ...]:
        """Einheiten der eigenen Läufe chronologisch."""
        return tuple(sorted(row for run in self.runs for row in run.member_row_indices))

    @property
    def member_row_indices(self) -> tuple[int, ...]:
        """Alle Einheiten der Sequenz chronologisch (eigene Läufe + geteilte LZKs)."""
        return tuple(sorted(self.own_row_indices + self.shared_rows))

    @property
    def own_member_count(self) -> int:
        """Anzahl der Einheiten der eigenen Läufe (Maß für `MIN_SEQUENCE_MEMBER_COUNT`)."""
        return sum(run.member_count for run in self.runs)

    def covers_in_block(self, row_index: int) -> bool:
        """Liegt die Zeile in der Spanne eines eigenen Laufs (Grid-Block, inkl. Lücken wie Ausfall)?"""
        return any(run.covers(row_index) for run in self.runs)


def group_into_sequences(
    runs: list[TopicSequenceRun], min_members: int = MIN_SEQUENCE_MEMBER_COUNT
) -> list[TopicSequence]:
    """Fasst Läufe mit gleichem Oberthema zu Sequenzen zusammen (einzige Gruppierungsregel).

    Eine Gruppe ist eine Sequenz, sobald sie zusammen mindestens
    `MIN_SEQUENCE_MEMBER_COUNT` Einheiten hat – dann zählt auch ein Lauf mit
    nur einer Einheit dazu. Reihenfolge: nach dem ersten Auftreten.

    Args:
        runs: Läufe aus `compute_topic_sequence_runs`.
        min_members: Mindestgröße einer Gruppe; ``1`` liefert jedes Oberthema
            (Export einer einzelnen Einheit).

    Returns:
        Die qualifizierten Sequenzen.
    """
    grouped: dict[str, list[TopicSequenceRun]] = {}
    for run in runs:
        grouped.setdefault(run.oberthema, []).append(run)
    sequences = [TopicSequence(oberthema, tuple(members)) for oberthema, members in grouped.items()]
    return [sequence for sequence in sequences if sequence.own_member_count >= min_members]


def compute_topic_sequences(
    day_columns: list[DayColumn], min_members: int = MIN_SEQUENCE_MEMBER_COUNT
) -> list[TopicSequence]:
    """Einziger Weg zu den Sequenzen eines Plans: Läufe, Gruppierung, geteilte Mehrthemen-LZKs.

    Args:
        day_columns: Vollständige, unprojizierte Tagesliste (`app.raw_day_columns`).
        min_members: Siehe `group_into_sequences`.
    """
    sequences = group_into_sequences(compute_topic_sequence_runs(day_columns), min_members)
    lzk_topics = [
        (day.row_index, day.oberthemen())
        for day in day_columns
        if isinstance(day, DayColumn) and day.lesson_type() == "LZK"
    ]
    return [
        replace(
            sequence,
            shared_rows=tuple(
                row
                for row, topics in lzk_topics
                if sequence.oberthema in topics and row not in sequence.own_row_indices
            ),
        )
        for sequence in sequences
    ]


def find_sequence_for_row_index(sequences: Sequence[TopicSequence], row_index: int) -> TopicSequence | None:
    """Sequenz einer Zeile: die, in deren Block sie liegt; sonst eine, die sie als LZK teilt.

    Einzige Regel „Zeile → Sequenz“ (Export, „Sequenz der markierten Spalte“). Blöcke
    überlappen nie, daher ist der erste Treffer eindeutig.
    """
    in_block = next((sequence for sequence in sequences if sequence.covers_in_block(row_index)), None)
    return in_block or next((sequence for sequence in sequences if row_index in sequence.shared_rows), None)


def find_run_for_row_index(runs: list[TopicSequenceRun], row_index: int) -> TopicSequenceRun | None:
    """Sucht den Sequenz-Lauf, der eine bestimmte Einheit als Mitglied enthält.

    Args:
        runs: Zuvor berechnete Läufe (siehe `compute_topic_sequence_runs`).
        row_index: Stabiler, absoluter Zeilenindex der gesuchten Einheit.

    Returns:
        Den passenden Lauf oder ``None``, wenn die Einheit in keinem Lauf enthalten ist.
    """
    for run in runs:
        if row_index in run.member_row_indices:
            return run
    return None


@dataclass(frozen=True)
class TopicUnitExportRow:
    """Fachdaten einer Einheit für den Sequenzplan-Export (Export-DTO, typisiert).

    Reines Export-DTO: wird nur von `build_export_rows` erzeugt und nur
    von den beiden Exportpfaden (manueller Sequenzplan-Export, Sequenzdatei-
    Sync) konsumiert. Es trägt bewusst **keine** vorformatierten Strings —
    Wochentag, ``Std.``-Suffix, Zeilenaufteilung und Material-Anzeigenamen sind
    Darstellungsregeln und liegen in der Anwendungsschicht
    (`core/usecases/sequence_export_table.py`).

    Attributes:
        datum: Geparstes Datum der Einheit oder ``None``, wenn nicht parsebar.
        datum_raw: Roher Datumswert der Planzeile (Fallback-Anzeige).
        startzeit: Startzeit laut Rhythmus (``"HH:MM"``) oder ``""``.
        stunden: Stundenzahl laut Rhythmus (``0`` = unbekannt).
        stundenthema: Stundenthema der Einheit.
        stundenziel: Stundenziel der Einheit.
        kompetenzen: Einträge des Listenfelds ``Kompetenzen``.
        material: Einträge des Listenfelds ``Material`` (bei LZK leer).
    """

    datum: date | None
    datum_raw: str
    startzeit: str
    stunden: int
    stundenthema: str
    stundenziel: str
    kompetenzen: tuple[str, ...]
    material: tuple[str, ...]


def build_export_rows(day_columns: list[DayColumn], member_row_indices: Sequence[int]) -> list[TopicUnitExportRow]:
    """Baut die Exportzeilen ausschließlich aus den Mitgliedern einer Sequenz (alle ihre Läufe).

    Hospitations-Einheiten zählen als Kettenmitglied (siehe
    `compute_topic_sequence_runs`), erscheinen aber wie bisher nicht als eigene
    Tabellenzeile, da `EXPORTABLE_LESSON_TYPES` nur Unterricht/LZK umfasst.
    Gemeinsam genutzt vom manuellen Sequenzplan-Export
    (`ExportTopicUnitsPdfUseCase`) und dem automatischen Sequenzdatei-Sync
    (`SyncTopicSequencePlansUseCase`), damit beide exakt dieselbe Tabelle
    erzeugen und nicht unabhängig voneinander auseinanderdriften können.

    Args:
        day_columns: Vollständige, unprojizierte Tagesliste in chronologischer
            Reihenfolge (z. B. `app.raw_day_columns`).
        member_row_indices: Zeilen der Einheiten, die exportiert werden sollen
            (`TopicSequence.member_row_indices`).

    Returns:
        Eine Exportzeile pro exportierbarem Kettenmitglied, in chronologischer
        Reihenfolge.
    """
    members = set(member_row_indices)
    rows: list[TopicUnitExportRow] = []
    for day in day_columns:
        if not isinstance(day, DayColumn):
            continue
        if day.row_index not in members:
            continue
        if day.lesson_type() not in EXPORTABLE_LESSON_TYPES:
            continue

        rows.append(
            TopicUnitExportRow(
                datum=parse_day_date(day.datum),
                datum_raw=str(day.datum or "").strip(),
                startzeit=day.startzeit(),
                stunden=day.stunden(),
                stundenthema=str(day.yaml.get("Stundenthema", "")).strip(),
                stundenziel=str(day.yaml.get("Stundenziel", "")).strip(),
                kompetenzen=lesson_list_entries(day.yaml, "Kompetenzen"),
                material=lesson_list_entries(day.yaml, "Material"),
            )
        )
    return rows
