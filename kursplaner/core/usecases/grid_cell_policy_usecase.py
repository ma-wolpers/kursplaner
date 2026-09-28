from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.content_markers import normalize_marker_text
from kursplaner.core.domain.day_column import DayColumn


class GridCellPolicyUseCase:
    """Kapselt fachliche Zellregeln für Grid-Anzeige und Editierbarkeit."""

    @staticmethod
    def format_list_entries(entries: list[str]) -> str:
        """Formatiert Listenwerte als durch Trennlinie separierten Mehrzeilentext."""
        if not entries:
            return ""
        return "\n—\n".join(entries)

    def field_value(self, day: DayColumn, field_key: str) -> str:
        """Ermittelt den darzustellenden Zellwert für ein Feld einer Tages-Spalte."""
        if field_key == "datum":
            return day.datum.strip()

        if field_key == "inhalt":
            marker = day.content_marker_text().strip()
            if marker:
                return marker
            return normalize_marker_text(day.inhalt)

        if field_key == "Stundenthema":
            if not day.is_valid_unterricht_file:
                return ""
            topic = str(day.yaml.get("Stundenthema", "")).strip()
            if topic:
                return topic
            return ""

        if field_key == "stunden":
            return str(day.stunden())
        if field_key == "startzeit":
            return day.startzeit()

        yaml_data = day.yaml
        if field_key == "Oberthema":
            # Anzeige inkl. Plantabellen-Fallback (Einheit noch ohne Datei),
            # mehrerer LZK-Themen (`` | ``) und Warnmarker bei ungültigem
            # Wert — zentral in `DayColumn.oberthema_display`.
            return day.oberthema_display()

        if field_key in {
            "Stundenziel",
            "Kompetenzhorizont",
            "Inhaltsübersicht",
            "Beobachtungsschwerpunkte",
        }:
            return str(yaml_data.get(field_key, "")).strip()

        if field_key in {
            "Kompetenzen",
            "Material",
            "Vertretungsmaterial",
            "Ressourcen",
            "Baustellen",
            "Professionalisierungsschritte",
            "Nutzbare Ressourcen",
        }:
            entries = yaml_data.get(field_key, [])
            if not isinstance(entries, list):
                return ""
            cleaned = [str(item).strip() for item in entries if str(item).strip()]
            return self.format_list_entries(cleaned)

        return ""

    def is_editable(self, field_key: str, day: DayColumn) -> bool:
        """Prüft, ob ein Feld fachlich editierbar ist (Status, Marker, Linklage)."""
        if field_key in {"datum", "stunden", "startzeit", "inhalt", "thema/ausfall"}:
            return False
        link_obj = day.link
        has_known_lesson = isinstance(link_obj, Path) and link_obj.exists() and link_obj.is_file()
        return has_known_lesson
