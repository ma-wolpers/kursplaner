from __future__ import annotations

import re
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData, sanitize_hour_title
from kursplaner.core.domain.wiki_links import build_dataview_lesson_link
from kursplaner.core.ports.repositories import LessonFileRepository, LessonRepository

_DATAVIEW_QUERY_RE = re.compile(r"`=[^`]*`")
"""Erkennt eine bereits vorhandene Dataview-Inline-Query in einer Inhalt-Zelle."""


class LessonTransferUseCase:
    """Orchestriert den fachlichen Ablauf für Lesson Transfer Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(self, lesson_repo: LessonRepository, lesson_file_repo: LessonFileRepository):
        """Initialisiert den Transfer-Use-Case mit Port-basierten Abhängigkeiten.

        Args:
            lesson_repo: Repository für Stunden-YAML und Link-Auflösung.
            lesson_file_repo: Repository für Dateioperationen auf Stunden-Dateien.
        """
        self.lesson_repo = lesson_repo
        self.lesson_file_repo = lesson_file_repo

    def validate_lesson_markdown(self, source: Path) -> None:
        """Validiert, dass eine Quelle eine lesbare Stunden-Markdown-Datei ist."""
        if not self.lesson_file_repo.is_existing_markdown(source):
            raise RuntimeError(f"Ungültige Markdown-Datei:\n{source}")
        self.lesson_repo.load_lesson_yaml(source)

    def lesson_dir_for_table(self, table: PlanTableData) -> Path:
        """Liefert das standardisierte Zielverzeichnis ``Einheiten`` für eine Planung."""
        return table.markdown_path.parent / "Einheiten"

    def ensure_directory(self, path: Path) -> None:
        """Stellt sicher, dass ein Verzeichnis über den Datei-Port existiert."""
        self.lesson_file_repo.ensure_directory(path)

    def find_markdown_target(self, table: PlanTableData, source: Path) -> Path:
        """Ermittelt den Zielpfad einer zu verschiebenden Stunden-Markdown-Datei."""
        return self.lesson_dir_for_table(table) / source.name

    def move_markdown(self, source: Path, target: Path) -> Path:
        """Verschiebt eine Stunden-Markdown-Datei auf den Zielpfad."""
        return self.lesson_file_repo.move_file(source, target)

    def relink_row_to_stem(
        self, table: PlanTableData, row_index: int, stem: str, *, preserve_alias: bool = True
    ) -> None:
        """Setzt die `Inhalt`-Zelle einer Tabellenzeile auf einen Dataview-Link zum Dateistem.

        Baut die Zelle über `build_dataview_lesson_link` (siehe `wiki_links.py`)
        statt eines rohen Wiki-Links — der Anzeigetext kommt dadurch live aus
        dem `Stundenthema`-YAML-Feld der verlinkten Einheit.

        `preserve_alias` bleibt ausschließlich aus Aufrufer-Kompatibilität auf
        der Signatur (`action_controller.py` und `lesson_context_controller.py`
        rufen diese Methode mit unterschiedlichem Wert auf) und hat **keine
        funktionale Wirkung mehr**: das Dataview-Format kennt keinen
        statischen Alias — die Anzeige leitet sich immer live aus
        `Stundenthema` ab. Vor der Umstellung wurde hier ein evtl. in der
        Zelle vorhandener Alt-Alias (`[[stem|Alias]]`) erkannt und in den neu
        gebauten Link übernommen; das entfällt bewusst (Root-Cause-Cleanup),
        nicht als übriggelassenes totes Duplikat.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.
            stem: Dateistem der zu verlinkenden Einheit.
            preserve_alias: Ohne Wirkung (siehe oben), nur für API-Stabilität.
        """
        if not (0 <= row_index < len(table.rows)):
            raise RuntimeError("Ungültige Zeile für Link-Update.")
        table.set_inhalt(row_index, build_dataview_lesson_link(stem))

    def replace_or_append_first_link(self, table: PlanTableData, row_index: int, stem: str) -> None:
        """Ersetzt den bestehenden Einheiten-Link in der `Inhalt`-Zelle oder hängt ihn an.

        Der Stem kommt im Dataview-Format zweimal in der Zelle vor
        (``link("stem", ...)`` und ``[[stem]]``) — ein reiner Teilstring-Ersatz
        des alten `[[...]]`-Musters würde dabei inkonsistente Reste
        hinterlassen. Erkennungsreihenfolge: (1) vorhandene Dataview-Query
        komplett ersetzen; (2) sonst einen noch nicht migrierten Alt-Format-
        Link `[[...]]` ersetzen (Rückwärtskompatibilität für Zeilen, die seit
        der Formatumstellung noch nicht neu geschrieben wurden — kein
        Migrationsskript angefordert, das ist der normale In-Place-Upgrade-
        Pfad); (3) sonst den Link an vorhandenen Text anhängen.
        """
        if not (0 <= row_index < len(table.rows)):
            raise RuntimeError("Ungültige Zeile für Link-Update.")

        link = build_dataview_lesson_link(stem)
        current = table.inhalt(row_index)

        if _DATAVIEW_QUERY_RE.search(current):
            table.set_inhalt(row_index, _DATAVIEW_QUERY_RE.sub(link, current, count=1))
            return

        if "[[" in current and "]]" in current:
            table.set_inhalt(row_index, re.sub(r"\[\[[^\]]+\]\]", link, current, count=1))
            return

        prefix = current.strip()
        table.set_inhalt(row_index, f"{prefix} {link}".strip() if prefix else link)

    def next_unique_stem_path(self, target_dir: Path, preferred_stem: str) -> Path:
        """Erzeugt einen kollisionsfreien Zielpfad aus einem bevorzugten Titelstem."""
        stem_base = sanitize_hour_title(preferred_stem) or "Stunde"
        return self.lesson_file_repo.unique_markdown_path(target_dir, stem_base)

    def write_pasted_lesson(
        self,
        target_path: Path,
        content: str,
        source_stem: str,
        *,
        clear_ub_link: bool = True,
    ) -> Path:
        """Schreibt eingefügte Stundeninhalte und synchronisiert ggf. das Stundenthema."""
        self.lesson_file_repo.write_file_content(target_path, content)

        pasted_lesson = self.lesson_repo.load_lesson_yaml(target_path)
        lesson_data = pasted_lesson.data if isinstance(pasted_lesson.data, dict) else {}
        should_save_yaml = False

        if clear_ub_link and str(lesson_data.get("Unterrichtsbesuch", "")).strip():
            lesson_data["Unterrichtsbesuch"] = ""
            should_save_yaml = True

        if target_path.stem != source_stem:
            topic_before = str(lesson_data.get("Stundenthema", "")).strip()
            suffix_match = re.search(r"\s(\d+)$", target_path.stem)
            if suffix_match and topic_before:
                suffix = suffix_match.group(1)
                lesson_data["Stundenthema"] = re.sub(r"\s\d+$", "", topic_before).strip() + f" {suffix}"
            else:
                lesson_data["Stundenthema"] = target_path.stem
            should_save_yaml = True

        if should_save_yaml:
            pasted_lesson.data = lesson_data
            self.lesson_repo.save_lesson_yaml(pasted_lesson)

        return target_path

    def resolve_existing_link(self, table: PlanTableData, row_index: int) -> Path | None:
        """Löst den aktuell verlinkten Stundenpfad einer Tabellenzeile auf."""
        return self.lesson_repo.resolve_row_link_path(table, row_index)

    def compute_rename_target(self, link: Path, desired_stem: str) -> Path:
        """Berechnet ein kollisionsfreies Rename-Ziel für eine bestehende Stunden-Datei."""
        target_stem = sanitize_hour_title(desired_stem)
        if not target_stem:
            return link

        stunden_dir = link.parent
        return self.lesson_file_repo.unique_markdown_path(stunden_dir, target_stem, current_path=link)

    def rename_lesson_file(self, link: Path, target: Path) -> Path:
        """Benennt eine Stunden-Datei um und liefert den finalen Pfad zurück."""
        return self.lesson_file_repo.rename_file(link, target)

    def delete_lesson_file(self, path: Path) -> None:
        """Löscht eine Stunden-Datei über den Datei-Port."""
        self.lesson_file_repo.delete_file(path)

    def read_lesson_content(self, path: Path) -> str:
        """Liest den Rohinhalt einer Stunden-Datei über den Datei-Port."""
        return self.lesson_file_repo.read_file_content(path)

    def load_lesson_yaml_data(self, path: Path) -> dict[str, object]:
        """Lädt strukturierte YAML-Daten einer Stunden-Datei über den Lesson-Port."""
        lesson = self.lesson_repo.load_lesson_yaml(path)
        return lesson.data if isinstance(lesson.data, dict) else {}
