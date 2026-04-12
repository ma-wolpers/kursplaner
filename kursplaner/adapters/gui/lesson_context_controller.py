from __future__ import annotations

import pathlib
import re
from datetime import datetime

from kursplaner.core.domain.content_markers import normalize_marker_text
from kursplaner.core.domain.lesson_naming import build_lesson_stem, parse_mmdd
from kursplaner.core.domain.plan_table import sanitize_hour_title
from kursplaner.core.domain.wiki_links import strip_wiki_link


class MainWindowLessonContextController:
    """Kapselt fachnahe Kontext- und Namenshilfen der Hauptansicht.

    Nutzt ausschließlich Use Cases/Flows aus `app.gui_dependencies` (keine direkten Repos).
    """

    def __init__(self, app):
        """Initialisiert den Controller mit den benötigten Read-/Rename-Use-Cases."""
        self.app = app
        deps = getattr(app, "gui_dependencies", None)
        if deps is None:
            raise RuntimeError("GUI Dependencies not available on app")
        self.lesson_context_query = deps.lesson_context_query
        self.lesson_transfer = deps.lesson_transfer
        self.rename_linked_file_for_row_usecase = getattr(deps, "rename_linked_file_for_row", None)

    def field_value(self, day: dict[str, object], field_key: str) -> str:
        """Projiziert den Zellwert eines Feldes aus `day_columns` in UI-Text."""
        if field_key == "inhalt":
            return self._display_content_text(day)

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
            "Inhaltsübersicht",
            "Beobachtungsschwerpunkte",
        }:
            return str(yaml_data.get(field_key, "")).strip()
        if field_key == "Kompetenzhorizont":
            if bool(day.get("is_lzk", False)):
                return self._expected_horizon_status_text(day, yaml_data)
            return str(yaml_data.get(field_key, "")).strip()

        if field_key in {
            "Kompetenzen",
            "Teilziele",
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
            if field_key in {"Professionalisierungsschritte", "Nutzbare Ressourcen"}:
                return "\n".join(cleaned)
            return self.format_list_entries(cleaned)

        return ""

    @staticmethod
    def _extract_wiki_stem(value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if text.startswith("[[") and text.endswith("]]"):
            text = text[2:-2].strip()
        if "|" in text:
            text = text.split("|", 1)[0].strip()
        if text.lower().endswith(".md"):
            text = text[:-3].strip()
        text = text.replace("\\", "/")
        if "/" in text:
            text = text.split("/")[-1].strip()
        return text

    @staticmethod
    def _parse_iso_datetime(value: object) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            if text.endswith("Z"):
                text = f"{text[:-1]}+00:00"
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    @staticmethod
    def _format_status_datetime(value: datetime) -> str:
        return value.astimezone().strftime("%d.%m.%y um %H:%M")

    def _expected_horizon_status_text(self, day: dict[str, object], yaml_data: dict[str, object]) -> str:
        stem = self._extract_wiki_stem(yaml_data.get("Kompetenzhorizont", ""))
        if not stem:
            return "leer"

        lesson_path = day.get("link")
        if not isinstance(lesson_path, pathlib.Path):
            return "leer"

        course_dir = lesson_path.resolve().parent.parent
        markdown_path = (course_dir / f"{stem}.md").resolve()
        if not markdown_path.exists() or not markdown_path.is_file():
            return "leer"

        created_at = self._parse_iso_datetime(yaml_data.get("created_at", ""))
        if created_at is None:
            created_at = datetime.fromtimestamp(markdown_path.stat().st_mtime).astimezone()
        return f"erstellt am {self._format_status_datetime(created_at)}"

    def _display_content_text(self, day: dict[str, object]) -> str:
        """Bereinigt Inhaltsanzeige um Linksyntax sowie Lerngruppe/Datum-Präfix."""
        text = normalize_marker_text(str(day.get("inhalt", "")))
        text = text.replace("[", "").replace("]", "").strip()
        text = re.sub(r"\s+", " ", text)
        if not text:
            return ""

        group = self.parse_group_token()
        mmdd = parse_mmdd(str(day.get("datum", "")).strip())
        prefix = f"{group} {mmdd} "
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix) :].strip()
        return text

    def estimate_visual_lines(self, text: str) -> int:
        """Schätzt die benötigten Anzeigezeilen für umbrochenen Zelltext."""
        if not text:
            return 1
        # Intentionally conservative to avoid underestimating long prose fields
        # (e.g. Stundenziel/Kompetenzen), otherwise expand controls stay hidden.
        chars_per_line = max(10, self.app.day_column_width // 12)
        estimated = 0
        for paragraph in text.splitlines() or [text]:
            length = len(paragraph.strip())
            if length <= 0:
                estimated += 1
            else:
                estimated += max(1, (length + chars_per_line - 1) // chars_per_line)
        return max(1, estimated)

    @staticmethod
    def format_list_entries(entries: list[str]) -> str:
        """Formatiert Listenwerte für die mehrzeilige Grid-Darstellung."""
        if not entries:
            return ""
        return "\n—\n".join(entries)

    @staticmethod
    def parse_list_entries(text: str) -> list[str]:
        """Parst UI-Mehrzeilentext zurück in normalisierte Listeneinträge."""
        parts = re.split(r"\n\s*[—\-]{1,}\s*\n", text.strip()) if text.strip() else []
        result: list[str] = []
        if not parts:
            return result

        for part in parts:
            chunk = part.strip()
            if not chunk:
                continue
            lines = [line.strip() for line in chunk.splitlines() if line.strip()]
            if not lines:
                continue
            joined = " ".join(lines)
            joined = re.sub(r"^\[(\d+)\]\s*", "", joined)
            joined = re.sub(r"^(\d+)[\).:]\s*", "", joined)
            if joined:
                result.append(joined)
        return result

    @staticmethod
    def keyword_match(text: str, keywords: list[str]) -> bool:
        """Prüft case-insensitiv auf Keywords im Text."""
        lowered = text.lower()
        return any(key in lowered for key in keywords)

    @staticmethod
    def contains_markdown_link(text: str) -> bool:
        """Prüft, ob der Text eine Obsidian/Wiki-Link-Syntax enthält."""
        stripped = text.strip()
        return "[[" in stripped and "]]" in stripped

    def parse_halfyear_token(self) -> str:
        """Liest das Halbjahrstoken aus dem aktuellen Plan-Dateinamen."""
        if self.app.current_table is None:
            return "??-?"
        text = self.app.current_table.markdown_path.stem
        match = re.search(r"\b(\d{2}-[12])\b", text)
        return match.group(1) if match else "??-?"

    def parse_group_token(self) -> str:
        """Liest und normalisiert den Lerngruppen-Token aus Plan-Metadaten."""
        if self.app.current_table is None:
            return "gruppe"
        group = strip_wiki_link(str(self.app.current_table.metadata.get("Lerngruppe", "gruppe")))
        return sanitize_hour_title(group) or "gruppe"

    def parse_subject_token(self) -> str:
        """Liest und normalisiert das Fachkürzel aus Plan-Metadaten."""
        if self.app.current_table is None:
            return "Fach"
        return sanitize_hour_title(str(self.app.current_table.metadata.get("Kursfach", "Fach"))) or "Fach"

    def parse_grade_token(self) -> str:
        """Liest und normalisiert die Stufenangabe aus Plan-Metadaten."""
        if self.app.current_table is None:
            return "?"
        return sanitize_hour_title(str(self.app.current_table.metadata.get("Stufe", "?"))) or "?"

    def build_regular_stem(self, topic: str, date_label: str = "") -> str:
        """Erzeugt den Standard-Dateistamm für reguläre Stunden."""
        gruppe = self.parse_group_token()
        return build_lesson_stem(gruppe, parse_mmdd(date_label), sanitize_hour_title(topic))

    def is_lzk_row(self, row_index: int) -> bool:
        """Ermittelt, ob eine Tabellenzeile fachlich als LZK zu behandeln ist."""
        if self.app.current_table is None:
            return False
        if not (0 <= row_index < len(self.app.current_table.rows)):
            return False

        row = self.app.current_table.rows[row_index]
        content = row[2] if len(row) > 2 else ""
        if self.keyword_match(content, ["lzk"]):
            return True

        link = self.lesson_transfer.resolve_existing_link(self.app.current_table, row_index)
        if isinstance(link, pathlib.Path) and link.exists():
            yaml_data = self.lesson_transfer.load_lesson_yaml_data(link)
            topic = str(yaml_data.get("Stundenthema", ""))
            if self.keyword_match(topic, ["lzk"]):
                return True

        return False

    def next_lzk_number(self) -> int:
        """Delegiert die nächste LZK-Nummer an den fachlichen Query-Use-Case."""
        if self.app.current_table is None:
            return 1
        return self.lesson_context_query.next_lzk_number(self.app.current_table)

    def replace_plan_link(self, row_index: int, new_stem: str):
        """Ersetzt oder ergänzt den ersten Wiki-Link einer Planzeile."""
        if self.app.current_table is None:
            return
        self.lesson_transfer.replace_or_append_first_link(self.app.current_table, row_index, new_stem)

    def rename_linked_file_for_row(self, row_index: int, desired_stem: str) -> pathlib.Path | None:
        """Benennt die verlinkte Datei einer Zeile über den dedizierten Use Case um."""
        if self.app.current_table is None:
            return None
        if self.rename_linked_file_for_row_usecase is None:
            return None

        result = self.rename_linked_file_for_row_usecase.execute(
            table=self.app.current_table,
            row_index=row_index,
            desired_stem=desired_stem,
            allow_rename=True,
            allow_plan_save=True,
        )

        if not result.proceed:
            return None

        return result.target_path
