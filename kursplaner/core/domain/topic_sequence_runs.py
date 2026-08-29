"""Fachliche Erkennung von Themen-Sequenzen (Ketten benachbarter Einheiten mit gleichem Oberthema).

Eine Sequenz im Sinne dieses Moduls ist eine ununterbrochene Kette chronologisch
benachbarter Unterrichts-, LZK- oder Hospitations-Einheiten, deren Oberthema-Feld
denselben, nicht-leeren Text trägt. Ausfall-Einheiten unterbrechen eine solche
Kette nicht, tragen selbst aber auch kein Oberthema und werden bei der Erkennung
übersprungen. Alle anderen Einheiten (leere/ungeplante Tage, oder Einheiten ohne
gesetztes Oberthema) beenden eine laufende Kette.

Die Berechnung arbeitet bewusst auf der vollständigen, chronologischen Tagesliste
(z. B. `app.raw_day_columns`) und nicht auf einer nach Sichtbarkeits-Einstellungen
gefilterten Projektion, damit das Ergebnis unabhängig von rein optischen
Anzeige-Einstellungen ist.
"""

from __future__ import annotations

from dataclasses import dataclass

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.export_date_formatting import format_day_date

ELIGIBLE_SEQUENCE_TYPES = frozenset({"Unterricht", "LZK", "Hospitation"})
"""Stundentypen, die selbst ein Oberthema tragen und Teil einer Sequenz sein können."""

SKIPPED_SEQUENCE_TYPES = frozenset({"Ausfall"})
"""Stundentypen, die eine laufende Sequenz weder fortsetzen noch unterbrechen."""

EXPORTABLE_LESSON_TYPES = frozenset({"Unterricht", "LZK"})
"""Stundentypen, die als eigene Zeile in der Sequenz-Export-Tabelle erscheinen."""

EXPORT_TABLE_HEADERS: tuple[str, ...] = ("Datum", "Std.", "Thema", "Stundenziel", "Kompetenzen")
"""Spaltenüberschriften der Sequenz-Export-Tabelle (manueller Export und Auto-Sync)."""


def row_lesson_type(day: DayColumn) -> str:
    """Liest den Stundentyp einer Tages-Spalte.

    Bevorzugt `day.stundentyp` (YAML-Typ der verlinkten Stundendatei).
    Ausfall-Tage haben jedoch nie eine verlinkte Datei und werden stattdessen
    über `day.is_cancel()` erkannt; Hospitation kann ebenso ohne Link
    vorkommen (`day.is_hospitation()`). Dieser Fallback spiegelt exakt die
    Ableitung aus `RowDisplayModeUseCase.infer_day_mode()`, damit beide
    Stellen für dieselbe Spalte immer denselben Typ ermitteln.

    Args:
        day: Eintrag aus einer Tagesliste (z. B. `raw_day_columns`), wie sie
            vom Grid und von Export-Use-Cases konsumiert wird.

    Returns:
        Der Stundentyp-Text (z. B. ``"Unterricht"``) oder ein leerer String,
        wenn die Spalte keinem bekannten Typ zugeordnet werden kann.
    """
    if day.is_cancel():
        return "Ausfall"
    if day.is_hospitation():
        return "Hospitation"
    if day.is_lzk():
        return "LZK"
    return day.stundentyp


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


def compute_topic_sequence_runs(raw_day_columns: list[DayColumn]) -> list[TopicSequenceRun]:
    """Berechnet alle Themen-Sequenz-Läufe innerhalb einer chronologischen Tagesliste.

    Iteriert einmal linear über `raw_day_columns` und verfolgt eine laufende Kette:
    Ausfall-Einheiten werden übersprungen (weder Fortsetzung noch Abbruch), Einheiten
    mit demselben, nicht-leeren Oberthema wie die laufende Kette setzen diese fort,
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

        lesson_type = row_lesson_type(day)
        if lesson_type in SKIPPED_SEQUENCE_TYPES:
            continue
        if lesson_type not in ELIGIBLE_SEQUENCE_TYPES:
            _flush()
            current_oberthema, current_members = None, []
            continue

        oberthema = row_oberthema(day)
        if not oberthema:
            _flush()
            current_oberthema, current_members = None, []
            continue

        if oberthema == current_oberthema:
            current_members.append(day.row_index)
            continue

        _flush()
        current_oberthema, current_members = oberthema, [day.row_index]

    _flush()
    return runs


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
    """Eine exportierte Tabellenzeile eines Sequenz-Laufs."""

    datum: str
    stunden: str
    thema: str
    stundenziel: str
    prozesskompetenzen: str


def _format_competencies_text(value: object) -> str:
    """Formatiert die Kompetenzen-Liste einer Einheit als Fließtext für den Export."""
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return "; ".join(cleaned)
    return str(value or "").strip()


def build_export_rows_for_run(day_columns: list[DayColumn], run: TopicSequenceRun) -> list[TopicUnitExportRow]:
    """Baut die Exportzeilen ausschließlich aus den Mitgliedern eines Sequenz-Laufs.

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
        run: Der Sequenz-Lauf, dessen Mitglieder exportiert werden sollen.

    Returns:
        Eine Exportzeile pro exportierbarem Kettenmitglied, in chronologischer
        Reihenfolge.
    """
    member_row_indices = set(run.member_row_indices)
    rows: list[TopicUnitExportRow] = []
    for day in day_columns:
        if not isinstance(day, DayColumn):
            continue
        if day.row_index not in member_row_indices:
            continue
        if row_lesson_type(day) not in EXPORTABLE_LESSON_TYPES:
            continue

        rows.append(
            TopicUnitExportRow(
                datum=format_day_date(day.datum),
                stunden=str(day.stunden()),
                thema=str(day.yaml.get("Stundenthema", "")).strip(),
                stundenziel=str(day.yaml.get("Stundenziel", "")).strip(),
                prozesskompetenzen=_format_competencies_text(day.yaml.get("Kompetenzen", [])),
            )
        )
    return rows
