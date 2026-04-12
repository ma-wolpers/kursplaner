from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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

    AUSFALL_ROWS: tuple[RowDef, ...] = (("Vertretungsmaterial", "Welches Vertretungsmaterial"),)

    HOSPITATION_ROWS: tuple[RowDef, ...] = (
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

    def row_defs_for_mode(self, mode_key: str | None) -> list[RowDef]:
        """Liefert die Grid-Zeilendefinitionen für einen Anzeige-Modus."""
        normalized = self.normalize_mode(mode_key)
        return list(self._definitions[normalized].rows)

    @staticmethod
    def infer_day_mode(day: dict[str, object] | None) -> str:
        """Leitet den fachlich passenden Modus aus einer Tages-Spalte ab."""
        if not isinstance(day, dict):
            return RowDisplayModeUseCase.MODE_UNTERRICHT
        if bool(day.get("is_cancel", False)):
            return RowDisplayModeUseCase.MODE_AUSFALL
        if bool(day.get("is_hospitation", False)):
            return RowDisplayModeUseCase.MODE_HOSPITATION
        if bool(day.get("is_lzk", False)):
            return RowDisplayModeUseCase.MODE_LZK
        return RowDisplayModeUseCase.MODE_UNTERRICHT

    def mode_for_selection(
        self,
        *,
        selected_day_indices: set[int],
        day_columns: list[dict[str, object]],
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

    def field_is_relevant_for_day(self, field_key: str, day: dict[str, object]) -> bool:
        """Prüft, ob ein Feld zur fachlichen Art einer Spalte passt."""
        mode = self.infer_day_mode(day)
        if field_key in {"Professionalisierungsschritte", "Nutzbare Ressourcen"}:
            if mode != self.MODE_UNTERRICHT:
                return False
            yaml_obj = day.get("yaml") if isinstance(day, dict) else None
            yaml_data = yaml_obj if isinstance(yaml_obj, dict) else {}
            ub_link = str(yaml_data.get("Unterrichtsbesuch", "")).strip()
            return bool(ub_link)
        fields = {field for field, _ in self.row_defs_for_mode(mode)}
        return field_key in fields

    def is_editable(self, field_key: str, day: dict[str, object]) -> bool:
        """Ermittelt fachlich, ob ein Feld für eine Spalte editierbar sein darf."""
        if field_key in {"datum", "stunden", "inhalt"}:
            return False
        if field_key == "Kompetenzhorizont" and bool(day.get("is_lzk", False)):
            return False
        if not self.field_is_relevant_for_day(field_key, day):
            return False
        link_obj = day.get("link") if isinstance(day, dict) else None
        return isinstance(link_obj, Path) and link_obj.exists() and link_obj.is_file()
