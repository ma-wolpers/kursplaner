from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.content_markers import normalize_marker_text


class GridCellPolicyUseCase:
    """Kapselt fachliche Zellregeln für Grid-Anzeige und Editierbarkeit."""

    @staticmethod
    def format_list_entries(entries: list[str]) -> str:
        """Formatiert Listenwerte als durch Trennlinie separierten Mehrzeilentext."""
        if not entries:
            return ""
        return "\n—\n".join(entries)

    def field_value(self, day: dict[str, object], field_key: str) -> str:
        """Ermittelt den darzustellenden Zellwert für ein Feld einer Tages-Spalte."""
        if field_key == "datum":
            return str(day.get("datum", "")).strip()

        if field_key == "inhalt":
            marker = str(day.get("content_marker_text", "")).strip()
            if marker:
                return marker
            return normalize_marker_text(str(day.get("inhalt", "")))

        if field_key == "Stundenthema":
            if not bool(day.get("is_valid_unterricht_file", False)):
                return ""
            yaml_data_obj = day.get("yaml")
            yaml_data: dict[str, object] = yaml_data_obj if isinstance(yaml_data_obj, dict) else {}
            topic = str(yaml_data.get("Stundenthema", "")).strip()
            if topic:
                return topic
            return ""

        if field_key == "stunden":
            return str(day.get("stunden", ""))

        yaml_data_obj = day.get("yaml")
        yaml_data: dict[str, object] = yaml_data_obj if isinstance(yaml_data_obj, dict) else {}
        if field_key in {
            "Oberthema",
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

    def is_editable(self, field_key: str, day: dict[str, object]) -> bool:
        """Prüft, ob ein Feld fachlich editierbar ist (Status, Marker, Linklage)."""
        if field_key in {"datum", "stunden", "inhalt"}:
            return False
        link_obj = day.get("link")
        has_known_lesson = isinstance(link_obj, Path) and link_obj.exists() and link_obj.is_file()
        return has_known_lesson
