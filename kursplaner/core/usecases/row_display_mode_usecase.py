from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kursplaner.core.domain.day_column import DayColumn

RowDef = tuple[str, str]


@dataclass(frozen=True)
class RowDisplayModeDefinition:
    """Beschreibt die sichtbaren Grid-Zeilen eines Anzeige-Modus."""

    key: str
    label: str
    rows: tuple[RowDef, ...]


class RowDisplayModeUseCase:
    """Kapselt Feldsichtbarkeit und Typ-Ableitung für Grid-Anzeigemodi."""

    COMMON_ROWS: tuple[RowDef, ...] = (
        ("inhalt", "Inhalt"),
        ("startzeit", "Wann"),
        ("stunden", "Wie lange"),
    )

    UNTERRICHT_ROWS: tuple[RowDef, ...] = (
        ("Stundenthema", "Welches Stundenthema"),
        ("Oberthema", "Welches Oberthema"),
        ("Stundenziel", "Welches Stundenziel"),
        ("Teilziele", "Welche Teilziele"),
        ("Kompetenzen", "Welche Kompetenzen"),
        ("Material", "Welche Materialien"),
        ("Professionalisierungsschritte", "Welche Professionalisierungsschritte"),
        ("Nutzbare Ressourcen", "Welche nutzbaren Ressourcen"),
    )

    LZK_ROWS: tuple[RowDef, ...] = (
        ("Stundenthema", "Welche LZK"),
        ("Oberthema", "Welches Oberthema"),
        ("Kompetenzhorizont", "Welcher Kompetenzhorizont"),
        ("Inhaltsübersicht", "Welche Inhaltsübersicht"),
    )

    AUSFALL_ROWS: tuple[RowDef, ...] = (
        ("Ausfallgrund", "Ausfallgrund"),
        ("Vertretungsmaterial", "Welches Vertretungsmaterial"),
    )

    HOSPITATION_ROWS: tuple[RowDef, ...] = (
        ("Stundenthema", "Welches Stundenthema"),
        ("Oberthema", "Welches Oberthema"),
        ("Beobachtungsschwerpunkte", "Welche Beobachtungsschwerpunkte"),
        ("Ressourcen", "Welche Ressourcen"),
        ("Baustellen", "Welche Baustellen"),
    )

    MODE_UNTERRICHT = "unterricht"
    MODE_LZK = "lzk"
    MODE_AUSFALL = "ausfall"
    MODE_HOSPITATION = "hospitation"

    def __init__(self) -> None:
        """Initialisiert die statischen Modusdefinitionen."""
        self._definitions: dict[str, RowDisplayModeDefinition] = {
            self.MODE_UNTERRICHT: RowDisplayModeDefinition(
                key=self.MODE_UNTERRICHT,
                label="Unterricht",
                rows=self.COMMON_ROWS + self.UNTERRICHT_ROWS,
            ),
            self.MODE_LZK: RowDisplayModeDefinition(
                key=self.MODE_LZK,
                label="LZK",
                rows=self.COMMON_ROWS + self.LZK_ROWS,
            ),
            self.MODE_AUSFALL: RowDisplayModeDefinition(
                key=self.MODE_AUSFALL,
                label="Ausfall",
                rows=self.COMMON_ROWS + self.AUSFALL_ROWS,
            ),
            self.MODE_HOSPITATION: RowDisplayModeDefinition(
                key=self.MODE_HOSPITATION,
                label="Hospitation",
                rows=self.COMMON_ROWS + self.HOSPITATION_ROWS,
            ),
        }

    def available_modes(self) -> tuple[RowDisplayModeDefinition, ...]:
        """Liefert alle verfügbaren Anzeige-Modi in stabiler Reihenfolge."""
        return (
            self._definitions[self.MODE_UNTERRICHT],
            self._definitions[self.MODE_LZK],
            self._definitions[self.MODE_AUSFALL],
            self._definitions[self.MODE_HOSPITATION],
        )

    def normalize_mode(self, mode_key: str | None) -> str:
        """Normalisiert einen Modus-Schlüssel mit Fallback auf Unterricht."""
        key = str(mode_key or "").strip().lower()
        return key if key in self._definitions else self.MODE_UNTERRICHT

    def row_defs_for_mode(
        self, mode_key: str | None, settings: "RowFilterSettings | None" = None
    ) -> list[RowDef]:
        """Liefert die Grid-Zeilendefinitionen für einen Anzeige-Modus.

        Berücksichtigt ``settings.field_mode_overrides``, falls übergeben — ein Feld
        kann dadurch auch außerhalb seiner Standard-Modi auftauchen oder aus seinen
        Standard-Modi entfernt worden sein (siehe ``effective_modes_for_field``).
        """
        normalized = self.normalize_mode(mode_key)
        return [
            (field_key, label)
            for field_key, label, _modes_str in self.all_fields_ordered()
            if normalized in self.effective_modes_for_field(field_key, settings)
        ]

    def default_modes_for_field(self, field_key: str) -> frozenset[str]:
        """Liefert die fest hinterlegten Standard-Modi eines Feldes (ohne Overrides)."""
        return frozenset(
            mode_def.key for mode_def in self.available_modes() if any(k == field_key for k, _ in mode_def.rows)
        )

    def effective_modes_for_field(
        self, field_key: str, settings: "RowFilterSettings | None"
    ) -> frozenset[str]:
        """Liefert die tatsächlich wirksamen Modi eines Feldes.

        Ein in ``settings.field_mode_overrides`` hinterlegter Eintrag ersetzt die
        Standard-Moduszugehörigkeit vollständig; fehlt der Eintrag, gilt
        ``default_modes_for_field``.
        """
        if settings is not None and field_key in settings.field_mode_overrides:
            return settings.field_mode_overrides[field_key]
        return self.default_modes_for_field(field_key)

    @staticmethod
    def infer_day_mode(day: DayColumn | None) -> str:
        """Leitet den fachlich passenden Modus aus einer Tages-Spalte ab."""
        if not isinstance(day, DayColumn):
            return RowDisplayModeUseCase.MODE_UNTERRICHT
        if day.is_cancel():
            return RowDisplayModeUseCase.MODE_AUSFALL
        if day.is_hospitation():
            return RowDisplayModeUseCase.MODE_HOSPITATION
        if day.is_lzk():
            return RowDisplayModeUseCase.MODE_LZK
        return RowDisplayModeUseCase.MODE_UNTERRICHT

    def mode_for_selection(
        self,
        *,
        selected_day_indices: set[int],
        day_columns: list[DayColumn],
        fallback_mode: str | None,
    ) -> str:
        """Bestimmt den passenden Modus anhand der aktuellen Selektion."""
        selected = sorted(index for index in selected_day_indices if 0 <= index < len(day_columns))
        if len(selected) != 1:
            return self.normalize_mode(fallback_mode)
        return self.infer_day_mode(day_columns[selected[0]])

    @staticmethod
    def list_like_fields() -> set[str]:
        """Liefert YAML-Felder, die als Listen dargestellt/bearbeitet werden."""
        return {
            "Kompetenzen",
            "Teilziele",
            "Material",
            "Vertretungsmaterial",
            "Ressourcen",
            "Baustellen",
            "Professionalisierungsschritte",
            "Nutzbare Ressourcen",
        }

    def field_is_relevant_for_day(
        self, field_key: str, day: DayColumn, settings: "RowFilterSettings | None" = None
    ) -> bool:
        """Prüft, ob ein Feld zur fachlichen Art einer Spalte passt."""
        mode = self.infer_day_mode(day)
        if field_key in {"Professionalisierungsschritte", "Nutzbare Ressourcen"}:
            if mode != self.MODE_UNTERRICHT:
                return False
            ub_link = str(day.yaml.get("Unterrichtsbesuch", "")).strip()
            return bool(ub_link)
        return mode in self.effective_modes_for_field(field_key, settings)

    def all_fields_ordered(self) -> list[tuple[str, str, str]]:
        """Liefert alle Felder aller Modi als deduplizierte, geordnete Liste.

        Reihenfolge: COMMON → UNTERRICHT → LZK → AUSFALL → HOSPITATION.
        Felder, die in mehreren Modi vorkommen (z. B. ``Stundenthema`` in
        Unterricht, LZK und Hospitation), erscheinen nur einmal — beim ersten
        Auftreten.  Das Label stammt ebenfalls vom ersten Auftreten.

        Args:
            (none)

        Returns:
            Liste von ``(field_key, label, modes_str)``-Tupeln, wobei
            ``modes_str`` ein durch Leerzeichen getrennter String der
            Modusbuchstaben ist (z. B. ``"U L H"``).

        Example::

            use_case.all_fields_ordered()
            # → [("inhalt", "Inhalt", "U L A H"), ("Stundenthema", "Welches Stundenthema", "U L H"), …]
        """
        abbrevs = {
            self.MODE_UNTERRICHT: "U",
            self.MODE_LZK: "L",
            self.MODE_AUSFALL: "A",
            self.MODE_HOSPITATION: "H",
        }
        seen: dict[str, list] = {}
        order: list[str] = []
        for mode_def in self.available_modes():
            abbrev = abbrevs[mode_def.key]
            for field_key, label in mode_def.rows:
                if field_key not in seen:
                    seen[field_key] = [label, []]
                    order.append(field_key)
                seen[field_key][1].append(abbrev)
        return [(k, seen[k][0], " ".join(seen[k][1])) for k in order]

    @staticmethod
    def is_linked_day(day: DayColumn) -> bool:
        """Prüft, ob eine Spalte auf eine existierende, verlinkte Stunden-Datei zeigt.

        Einzige Quelle der Wahrheit für diese Prüfung; vorher unabhängig in
        `grid_renderer.py`, `is_editable()` und `save_cell_value_usecase.py`
        dupliziert, was u. a. dazu führte, dass "Inhalt" bei unverlinkten
        Tagen den Zeilenfilter umgehen konnte.
        """
        link_obj = day.link
        return isinstance(link_obj, Path) and link_obj.exists() and link_obj.is_file()

    def is_editable(self, field_key: str, day: DayColumn, settings: "RowFilterSettings | None" = None) -> bool:
        """Ermittelt fachlich, ob ein Feld für eine Spalte editierbar sein darf.

        Oberthema ist als einziges Feld auch ohne verlinkte Stunden-Datei
        editierbar: der Wert wird dann direkt in die `Thema/Ausfall`-Zelle
        der Plantabelle geschrieben (siehe `SaveCellValueUseCase.execute`).
        Ausfallgrund ist read-only: der Grund wird ausschließlich über "Als
        Ausfall markieren" gesetzt (Markertext in der `Thema/Ausfall`-Zelle).
        """
        if field_key in {"datum", "stunden", "startzeit", "inhalt", "thema/ausfall", "Ausfallgrund"}:
            return False
        if field_key == "Kompetenzhorizont" and day.is_lzk():
            return False
        if not self.field_is_relevant_for_day(field_key, day, settings):
            return False
        if self.is_linked_day(day):
            return True
        return field_key == "Oberthema"


@dataclass(frozen=True)
class RowFilterSettings:
    """Konfiguriert, in welchen Anzeige-Modi einzelne Zeilenfelder sichtbar sind.

    Default = leeres Dict → jedes Feld behält seine aus den Modus-Definitionen
    abgeleitete Standard-Moduszugehörigkeit (siehe ``RowDisplayModeUseCase.
    default_modes_for_field``). Ein Eintrag in ``field_mode_overrides`` ersetzt
    diese Standardzuordnung vollständig für das jeweilige Feld — dadurch lassen
    sich sowohl Standard-Modi abwählen als auch zusätzliche Modi hinzufügen.

    Args:
        field_mode_overrides: ``field_key`` → Menge der Modus-Schlüssel
            (``RowDisplayModeUseCase.MODE_*``), in denen das Feld sichtbar sein soll.

    Example::

        settings = RowFilterSettings(
            field_mode_overrides={"Oberthema": frozenset({"lzk", "ausfall"})}
        )
    """

    field_mode_overrides: dict[str, frozenset[str]] = field(default_factory=dict)
