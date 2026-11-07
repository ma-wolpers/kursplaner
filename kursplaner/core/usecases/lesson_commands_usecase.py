from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.markdown_lists import markdown_bullet_lines
from kursplaner.core.domain.markdown_sections import extract_bullet_items
from kursplaner.core.domain.oberthema_values import OBERTHEMA_KEY, distinct_raw_entries, read_oberthema_state
from kursplaner.core.domain.plan_table import PlanTableData, sanitize_hour_title
from kursplaner.core.domain.wiki_links import build_wiki_link, first_wiki_link_label
from kursplaner.core.ports.repositories import LessonRepository

INHALTE_HEADING = "Inhalte"
"""``##``-Abschnitt einer Einheit mit Verweisen auf Fachinhalte."""
METHODIK_HEADING = "Methodik"
"""``##``-Abschnitt einer Einheit mit Verweisen auf Methoden."""


class LessonCommandsUseCase:
    """Orchestriert den fachlichen Ablauf für Lesson Commands Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(self, lesson_repo: LessonRepository):
        """Initialisiert Kommandos zum Erzeugen und Ändern von Stunden-Dateien.

        Args:
            lesson_repo: Repository mit CRUD-Operationen für Stunden.
        """
        self.lesson_repo = lesson_repo

    def create_lzk_lesson(
        self,
        table: PlanTableData,
        row_index: int,
        title: str,
        default_hours: int,
    ) -> Path:
        """Erzeugt eine LZK-Stunde, verlinkt sie und synchronisiert das Thema.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.
            title: Titel für die anzulegende Stunde.
            default_hours: Initiale Stundenanzahl.

        Returns:
            Pfad der angelegten Stunden-Datei.
        """
        link = self.lesson_repo.create_linked_lesson_file(table, row_index, title, default_hours)
        lesson = self.lesson_repo.load_lesson_yaml(link)
        lesson.data["Stundentyp"] = "LZK"
        lesson.data["Stundenthema"] = sanitize_hour_title(title) or "LZK"
        lesson.data.setdefault(OBERTHEMA_KEY, [])
        self.lesson_repo.save_lesson_yaml(lesson)
        return link

    def create_regular_lesson_link(
        self,
        table: PlanTableData,
        row_index: int,
        topic: str,
        default_hours: int,
    ) -> Path:
        """Erzeugt und verlinkt eine reguläre Stunden-Datei.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.
            topic: Thema der neuen Stunde.
            default_hours: Initiale Stundenanzahl.

        Returns:
            Pfad der angelegten Stunden-Datei.
        """
        return self.lesson_repo.create_linked_lesson_file(table, row_index, topic, default_hours)

    def update_regular_lesson_content(
        self,
        lesson_path: Path,
        topic: str,
        oberthema_input: str,
        *,
        was_lzk: bool,
        content_before: str,
        group_name: str = "",
    ) -> None:
        """Aktualisiert Kernfelder einer regulären Stunde in der YAML-Struktur.

        Args:
            lesson_path: Pfad zur Stunden-Datei.
            topic: Neues Stundenthema.
            oberthema_input: Optionaler Oberthemawert.
            was_lzk: Kennzeichen, ob die Stunde vorher als LZK geführt wurde.
            content_before: Vorheriger Tabelleninhalt für Fallbacks.
            group_name: Lerngruppe des Kurses (zum Entschlüsseln des bisherigen Werts).

        Ein eingegebenes Oberthema ist eine ausdrückliche Korrektur und darf
        auch einen ungültigen Plattenwert ersetzen. Ohne Eingabe wird eine
        vorherige Mehrthemen-LZK auf ihr Haupt-Oberthema reduziert, da eine
        Unterrichtseinheit höchstens ein Oberthema trägt.
        """
        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        lesson.data["Stundentyp"] = "Unterricht"
        lesson.data["Stundenthema"] = sanitize_hour_title(topic)
        repair = False
        if oberthema_input:
            lesson.data[OBERTHEMA_KEY] = oberthema_input
            repair = True
        elif not read_oberthema_state(lesson.data, group_name).is_invalid:
            entries = distinct_raw_entries(lesson.data.get(OBERTHEMA_KEY))
            if len(entries) > 1:
                # Vorherige Mehrthemen-LZK: Einzelwert = Haupt-Oberthema (erster Eintrag).
                lesson.data[OBERTHEMA_KEY] = entries[0]
        self.lesson_repo.save_lesson_yaml(lesson, repair_oberthema=repair)

    def update_lesson_sections(self, lesson_path: Path, inhalte_refs: list[str], methodik_refs: list[str]) -> None:
        """Setzt ``## Inhalte``/``## Methodik`` auf genau diese Verweise (je ein Wiki-Link pro Zeile).

        Ersetzt vorhandene Abschnitte (statt sie erneut anzuhängen); eine leere
        Liste entfernt den Abschnitt. Geschrieben wird über den gemeinsamen
        Body-Abschnittsweg, das Frontmatter bleibt byte-genau (auch ``.ebw``).

        Args:
            lesson_path: Pfad zur Stunden-Datei.
            inhalte_refs: Einträge für den Abschnitt ``Inhalte``.
            methodik_refs: Einträge für den Abschnitt ``Methodik``.
        """
        for heading, refs in ((INHALTE_HEADING, inhalte_refs), (METHODIK_HEADING, methodik_refs)):
            lines = markdown_bullet_lines([build_wiki_link(ref) for ref in refs])
            self.lesson_repo.write_lesson_section(lesson_path, heading, lines)

    def read_lesson_sections(self, lesson_path: Path) -> tuple[list[str], list[str]]:
        """``(Inhalte, Methodik)``-Verweise einer Einheit (Alias bevorzugt, sonst Linkziel, sonst Freitext).

        Gegenstück zu `update_lesson_sections`; ``([], [])`` bei nicht lesbarer Datei.
        """
        return self._section_refs(lesson_path, INHALTE_HEADING), self._section_refs(lesson_path, METHODIK_HEADING)

    def _section_refs(self, lesson_path: Path, heading: str) -> list[str]:
        try:
            lines = self.lesson_repo.read_lesson_section(lesson_path, heading)
        except OSError:
            return []
        refs = [first_wiki_link_label(item) or item.strip() for item in extract_bullet_items("\n".join(lines))]
        return [ref for ref in refs if ref]

    def update_lesson_competencies(self, lesson_path: Path, kompetenzen_refs: list[str], stundenziel: str = "") -> None:
        """Schreibt Kompetenzlisten in die Stunden-YAML-Datei."""
        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        lesson.data["Kompetenzen"] = list(kompetenzen_refs)
        if stundenziel.strip():
            lesson.data["Stundenziel"] = stundenziel.strip()
        self.lesson_repo.save_lesson_yaml(lesson)
