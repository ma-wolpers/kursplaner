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

ELIGIBLE_SEQUENCE_TYPES = frozenset({"Unterricht", "LZK", "Hospitation"})
"""Stundentypen, die selbst ein Oberthema tragen und Teil einer Sequenz sein können."""

SKIPPED_SEQUENCE_TYPES = frozenset({"Ausfall"})
"""Stundentypen, die eine laufende Sequenz weder fortsetzen noch unterbrechen."""


def row_lesson_type(day: dict[str, object]) -> str:
    """Liest den Stundentyp einer Tages-Spalte.

    Bevorzugt den `Stundentyp` aus den YAML-Daten der verlinkten Stundendatei.
    Ausfall-Tage haben jedoch nie eine verlinkte Datei (`yaml` bleibt `{}`) und
    werden stattdessen über das Marker-Flag `is_cancel` erkannt; Hospitation
    kann ebenso ohne Link vorkommen (`is_hospitation`-Marker). Dieser Fallback
    spiegelt exakt die Ableitung aus `RowDisplayModeUseCase.infer_day_mode()`,
    damit beide Stellen für dieselbe Spalte immer denselben Typ ermitteln.

    Args:
        day: Eintrag aus einer Tagesliste (z. B. `raw_day_columns`), wie sie
            vom Grid und von Export-Use-Cases konsumiert wird.

    Returns:
        Der Stundentyp-Text (z. B. ``"Unterricht"``) oder ein leerer String,
        wenn die Spalte keinem bekannten Typ zugeordnet werden kann.
    """
    yaml_data = day.get("yaml")
    if isinstance(yaml_data, dict):
        lesson_type = str(yaml_data.get("Stundentyp", "")).strip()
        if lesson_type:
            return lesson_type
    if bool(day.get("is_cancel", False)):
        return "Ausfall"
    if bool(day.get("is_hospitation", False)):
        return "Hospitation"
    if bool(day.get("is_lzk", False)):
        return "LZK"
    return str(day.get("Stundentyp", "")).strip()


def row_oberthema(day: dict[str, object]) -> str:
    """Liest das Oberthema einer Tages-Spalte.

    Bevorzugt das YAML-Feld `Oberthema` der verlinkten Stunden-Datei. Existiert
    noch keine verlinkte Datei (leere/ungeplante Einheit), fällt die Erkennung
    auf `day["plan_oberthema"]` zurück — das aus der rohen `Thema/Ausfall`-Spalte
    der Plantabelle geparste Oberthema (siehe
    `load_plan_detail_usecase.build_day_columns`/`plan_table.extract_plan_oberthema`).
    Damit zählen auch noch nicht angelegte Einheiten, die in der Plantabelle
    bereits einem Oberthema zugeordnet sind, als Kettenmitglied.

    Args:
        day: Eintrag aus einer Tagesliste (z. B. `raw_day_columns`).

    Returns:
        Der getrimmte Oberthema-Text oder ein leerer String, wenn keines
        gesetzt ist.
    """
    yaml_data = day.get("yaml")
    if isinstance(yaml_data, dict):
        oberthema = str(yaml_data.get("Oberthema", "")).strip()
        if oberthema:
            return oberthema
    return str(day.get("plan_oberthema", "")).strip()


def _row_index(day: dict[str, object]) -> int:
    """Liest den stabilen, absoluten Zeilenindex einer Tages-Spalte."""
    try:
        return int(day.get("row_index", 0))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class TopicSequenceRun:
    """Eine erkannte Kette benachbarter Einheiten mit gemeinsamem Oberthema.

    `member_row_indices` referenziert die stabilen, absoluten Zeilenindizes
    (`day["row_index"]`) der Kettenmitglieder in chronologischer Reihenfolge.
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


def compute_topic_sequence_runs(raw_day_columns: list[dict[str, object]]) -> list[TopicSequenceRun]:
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
        if not isinstance(day, dict):
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
            current_members.append(_row_index(day))
            continue

        _flush()
        current_oberthema, current_members = oberthema, [_row_index(day)]

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
