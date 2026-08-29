from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.content_markers import normalize_marker_text
from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.plan_table import read_yaml_oberthema


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
            # Solange keine verlinkte Stunden-Datei existiert, hat `yaml` kein
            # eigenes "Oberthema"-Feld; die Plantabelle (Thema/Ausfall-Spalte)
            # kann das Oberthema aber schon vorab tragen (siehe
            # `extract_plan_oberthema`/`build_day_columns`). Das YAML-Feld darf
            # bewusst als Wiki-Link gespeichert sein; `read_yaml_oberthema`
            # liefert dafür einheitlich den entschlüsselten Anzeigetext.
            oberthema = read_yaml_oberthema(yaml_data, day.group_name)
            if oberthema:
                return oberthema
            return day.plan_oberthema().strip()

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
