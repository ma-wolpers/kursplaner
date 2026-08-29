"""Fachliche Repräsentation eines Kurstags (einer Planzeile) im Grid.

`DayColumn` ersetzt das frühere lose `day: dict[str, object]` — ein rohes Dict
suggerierte, dass Felder wie `stunden`/`is_cancel` gespeicherte Zellwerte
seien, obwohl sie tatsächlich bei jedem Zugriff aus wenigen rohen Feldern neu
abgeleitet werden. `DayColumn` macht diesen Unterschied explizit: rohe Felder
sind Attribute (kommen 1:1 aus Tabellenzeile/Repo-Auflösung), alles fachlich
Hergeleitete ist eine parameterlose Methode ohne Setter — mit zwei
Ausnahmen (`is_valid_unterricht_file`, `stundentyp`), die als
`functools.cached_property` implementiert sind (Perf-Fix 2026-08-29, siehe
DEVELOPMENT_LOG): ohne `()` aufgerufen, aber ansonsten mit derselben
Zusicherung eines reinen, seiteneffektfreien Werts.

Konstruktion bleibt Aufgabe der Usecase-Schicht (siehe
`core.usecases.load_plan_detail_usecase.LoadPlanDetailUseCase.build_day_columns`):
diese lädt YAML-Dateien und löst Links auf (I/O), bevor sie ein `DayColumn`
mit bereits vollständig geladenen Rohdaten baut. Alle Methoden/Properties auf
`DayColumn` selbst sind reine, IO-freie Ableitungen dieser Rohdaten —
inklusive `is_valid_unterricht_file`, deren `Path.exists()`-Prüfung zwar
technisch Dateisystemzugriff ist, aber ein reiner, unveränderlicher
Zustandscheck ohne Seiteneffekt (kein Schreiben, kein YAML-Laden) — und
genau deshalb sicher cachebar innerhalb einer Instanz: `self.yaml`/`self.link`
werden nirgends im Codebestand nach der Konstruktion in-place mutiert.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from functools import cached_property
from pathlib import Path

from kursplaner.core.domain.content_markers import (
    is_ausfall_marker,
    is_ferien_marker,
    is_hospitation_marker,
    is_unterricht_marker,
    normalize_marker_text,
)
from kursplaner.core.domain.course_rhythm import WeekdayRhythm, hours_for_date, start_time_for_date
from kursplaner.core.domain.lesson_directory import is_valid_unterricht_link
from kursplaner.core.domain.lesson_yaml_policy import infer_stundentyp
from kursplaner.core.domain.plan_table import extract_plan_oberthema, parse_plan_row_date, read_yaml_oberthema


@dataclass(frozen=True)
class DayColumn:
    """Ein Kurstag (eine Planzeile) mit rohen Feldern + fachlichen Ableitungsmethoden.

    Rohe Felder (kommen 1:1 aus Tabellenzeile/Repo-Auflösung, kein Setter
    nötig, da Instanzen bei jeder Datenänderung neu gebaut werden — siehe
    `build_day_columns`):

    Args:
        row_index: Nullbasierter Index der Planzeile.
        datum: Roher `Datum`-Zellwert (``DD-MM-YY``).
        inhalt: Roher `Inhalt`-Zellwert.
        thema_ausfall: Roher `Thema/Ausfall`-Zellwert.
        link: Aufgelöster Pfad der verlinkten Stunden-Datei, oder ``None``.
        yaml: Bereits geladenes/kanonisiertes YAML-Dict der verlinkten Datei
            (leer, falls kein gültiger Link).
        group_name: Lerngruppen-Bezeichnung des Kurses (Wiki-Link entfernt).
        rhythm: Alle Rhythmus-Einträge des Kurses (``Rhythmus``-YAML-Feld,
            geparst über `course_rhythm.parse_rhythm`).
        hidden_kinds_before: Nur für die sichtbarkeits-projizierte Kopie
            (siehe `column_visibility_projection_usecase.py`) — welche
            Feldarten vor dieser Spalte bereits ausgeblendet wurden.
    """

    row_index: int
    datum: str
    inhalt: str
    thema_ausfall: str
    link: Path | None
    yaml: dict[str, object]
    group_name: str
    rhythm: tuple[WeekdayRhythm, ...]
    hidden_kinds_before: tuple[str, ...] = ()

    def with_hidden_kinds_before(self, hidden_kinds: tuple[str, ...]) -> DayColumn:
        """Liefert eine Kopie mit gesetztem `hidden_kinds_before` (einzige Mutation im System)."""
        return replace(self, hidden_kinds_before=hidden_kinds)

    def _row_date(self) -> date | None:
        return parse_plan_row_date(self.datum)

    def is_ferien(self) -> bool:
        """Ferien-/Feiertagszeile (abschließendes `X`-Token, siehe `content_markers.is_ferien_marker`)."""
        return is_ferien_marker(self.thema_ausfall)

    def is_dateless(self) -> bool:
        """Einheit ohne Datum (angehängter Platzhalter, z. B. bei fehlendem freien Plan-Slot).

        Nur eine Zeile mit tatsächlichem Inhalt gilt als datumslose Einheit -
        eine leere Zeile ohne Datum ist keine Einheit, sondern wird von
        `plan_row_placement.strip_empty_dateless_rows` entfernt.
        """
        return self._row_date() is None and bool(self.inhalt.strip())

    def stunden(self) -> int:
        """Stundenzahl dieses Kurstags, live aus `rhythm` + `datum` abgeleitet.

        ``0`` für Ferien, für Wochentage ohne Rhythmus-Eintrag und für ein
        nicht parsbares Zeilendatum (kein gesonderter Fehlerzustand mehr —
        anders als das frühere String-Feld, das für diesen Fall einen leeren
        String statt ``"0"`` trug).
        """
        row_date = self._row_date()
        if row_date is None or self.is_ferien():
            return 0
        return hours_for_date(self.rhythm, row_date)

    def startzeit(self) -> str:
        """Startzeit dieses Kurstags, live aus `rhythm` + `datum` abgeleitet. Leer, falls kein Unterrichtstag."""
        row_date = self._row_date()
        if row_date is None or self.is_ferien():
            return ""
        return start_time_for_date(self.rhythm, row_date)

    def content_marker_text(self) -> str:
        """Normalisierter `Inhalt`-Text (Wiki-Klammern entfernt) für Marker-Interpretation."""
        return normalize_marker_text(self.inhalt)

    @cached_property
    def is_valid_unterricht_file(self) -> bool:
        """Prüft, ob `link` auf eine verwaltete Stunden-Datei zeigt (``Einheiten/``/``Alteinheiten/``).

        `@cached_property` statt Methode: `DayColumn` ist per Konvention ein
        unveränderlicher Daten-Snapshot, der bei jeder Datenänderung neu
        gebaut wird (siehe Klassendocstring) — der bei jedem Aufruf erneute
        `Path.exists()`/`is_file()`-Check von `is_valid_unterricht_link()`
        (wird transitiv auch von `stundentyp()` gebraucht, das wiederum von
        `is_lzk()`/`is_hospitation()`/`is_unterricht()` gelesen wird, teils
        mehrfach pro Grid-Zelle) ist innerhalb ein und derselben Instanz
        immer dasselbe Ergebnis. Vor der Umsetzung im Code verifiziert statt
        nur angenommen: `self.yaml`/`self.link` werden nirgends im
        Codebestand nach der Konstruktion in-place mutiert (nur gelesen oder
        über neue Instanzen ersetzt), die Cache-Sicherheit ist also nicht
        nur eine Annahme.
        """
        return is_valid_unterricht_link(self.link)

    @cached_property
    def stundentyp(self) -> str:
        """Stundentyp aus der verlinkten YAML (`infer_stundentyp`), ``"Unterricht"`` ohne gültigen Link.

        `@cached_property` aus demselben Grund wie `is_valid_unterricht_file`
        (siehe dort) — zusätzlich cacht dies implizit auch `infer_stundentyp()`,
        das ohne Cache bei jedem der (teils mehrfachen) Aufrufe erneut über
        `self.yaml` gelaufen wäre.
        """
        if self.is_valid_unterricht_file and isinstance(self.link, Path):
            return infer_stundentyp(self.yaml)
        return "Unterricht"

    def is_lzk(self) -> bool:
        """``True``, wenn die verlinkte YAML `Stundentyp: LZK` trägt."""
        return self.stundentyp == "LZK"

    def is_hospitation(self) -> bool:
        """Hospitation über YAML-Typ ODER Textmarker (`HO <Gruppe> ...`) erkannt."""
        if self.stundentyp == "Hospitation":
            return True
        return is_hospitation_marker(self.content_marker_text(), self.group_name)

    def is_unterricht(self) -> bool:
        """Regulärer Unterricht über YAML-Typ ODER Gruppentoken-Marker erkannt."""
        if self.stundentyp == "Unterricht":
            return True
        return is_unterricht_marker(self.content_marker_text(), self.group_name)

    def is_ub(self) -> bool:
        """``True``, wenn die verlinkte YAML einen Unterrichtsbesuch-Verweis trägt."""
        return bool(str(self.yaml.get("Unterrichtsbesuch", "")).strip())

    def is_cancel(self) -> bool:
        """Vollständiger Ausfall-Status: Textmarker in `thema_ausfall` ODER YAML `Stundentyp: Ausfall`."""
        if is_ausfall_marker(self.thema_ausfall):
            return True
        return str(self.yaml.get("Stundentyp", "")).strip() == "Ausfall"

    def _has_link_ref(self) -> bool:
        stripped = self.inhalt.strip()
        return "[[" in stripped and "]]" in stripped

    def is_link_header(self) -> bool:
        """``True``, wenn `inhalt` eine Wiki-Link-Syntax enthält."""
        return self._has_link_ref()

    def is_unresolved_link(self) -> bool:
        """``True``, wenn `inhalt` wie ein Link aussieht, aber `link` nicht aufgelöst werden konnte."""
        return bool(self.inhalt.strip() and self._has_link_ref() and self.link is None)

    def plan_oberthema(self) -> str:
        """Aus der rohen `thema_ausfall`-Zelle geparstes Oberthema (siehe `extract_plan_oberthema`).

        Einzige Oberthema-Quelle für Einheiten ohne verlinkte Stunden-Datei
        (noch kein `yaml["Oberthema"]` vorhanden).
        """
        return extract_plan_oberthema(self.thema_ausfall, self.group_name)

    def oberthema(self) -> str:
        """Das fachlich anzuzeigende/vergleichbare Oberthema dieses Kurstags.

        Bevorzugt das (ggf. als Wiki-Link gespeicherte, siehe
        `plan_table.read_yaml_oberthema`) YAML-Feld der verlinkten Datei,
        fällt sonst auf `plan_oberthema()` zurück.
        """
        return read_yaml_oberthema(self.yaml, self.group_name) or self.plan_oberthema()

    def header_content(self) -> str:
        """Anzeigetext für die Spalten-Kopfzeile (bevorzugt `Stundenthema`, sonst Ausfallgrund/Marker)."""
        stundenthema = str(self.yaml.get("Stundenthema", "")).strip()
        if stundenthema:
            return stundenthema
        thema_text = self.thema_ausfall.strip()
        if self.is_cancel():
            reason = thema_text[2:].strip() if thema_text.upper().startswith("X ") else thema_text
            return reason or "Ausfall"
        return self.content_marker_text() or ""
