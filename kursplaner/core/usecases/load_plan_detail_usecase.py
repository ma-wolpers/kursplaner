from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.content_markers import (
    is_ausfall_marker,
    is_hospitation_marker,
    is_unterricht_marker,
    normalize_marker_text,
)
from kursplaner.core.domain.lesson_yaml_policy import canonicalize_lesson_yaml, infer_stundentyp
from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.ports.repositories import LessonRepository, PlanRepository, UbRepository
from kursplaner.core.usecases.ub_markdown_sections import parse_list_section


@dataclass(frozen=True)
class PlanDetailResult:
    """Ergebnis eines Detail-Ladevorgangs für eine Planungsdatei."""

    table: PlanTableData
    day_columns: list[dict[str, object]]


class MissingLessonYamlFrontmatterError(RuntimeError):
    """Signalisiert fehlendes YAML-Frontmatter in einer verlinkten Stunden-Datei."""

    def __init__(self, lesson_path: Path, details: str):
        """Initialisiert den Fehler mit betroffenem Pfad und Originaldetails."""
        self.lesson_path = lesson_path
        super().__init__(details)


class LoadPlanDetailUseCase:
    """Lädt Planungstabelle und bereitet UI-unabhängige Tages-Spalten auf.

    Der Use Case ist read-only: fehlende YAML-Felder werden nur in-memory ergänzt,
    ohne persistente Schreibnebenwirkung im Ladepfad.
    """

    def __init__(
        self,
        plan_repo: PlanRepository,
        lesson_repo: LessonRepository,
        ub_repo: UbRepository | None = None,
    ):
        """Initialisiert den Use Case mit Plan- und Lesson-Repository-Port."""
        self.plan_repo = plan_repo
        self.lesson_repo = lesson_repo
        self.ub_repo = ub_repo

    def _load_ub_development_lists(self, *, workspace_root: Path, ub_link_stem: str) -> tuple[list[str], list[str]]:
        """Lädt UB-Listenfelder aus der UB-Markdown-Datei, falls vorhanden."""
        if self.ub_repo is None:
            return [], []
        stem = strip_wiki_link(str(ub_link_stem).strip())
        if not stem:
            return [], []
        ub_path = self.ub_repo.ensure_ub_root(workspace_root) / f"{stem}.md"
        if not ub_path.exists() or not ub_path.is_file():
            return [], []
        try:
            _, body = self.ub_repo.load_ub_markdown(ub_path)
        except Exception:
            return [], []
        return (
            parse_list_section(body, "Professionalisierungsschritte"),
            parse_list_section(body, "Nutzbare Ressourcen"),
        )

    @staticmethod
    def _workspace_root_from_table(table: PlanTableData) -> Path:
        resolved = table.markdown_path.expanduser().resolve()
        for parent in (resolved, *resolved.parents):
            if parent.name == "7thCloud":
                return parent
        return resolved.parent

    @staticmethod
    def _contains_markdown_link(text: str) -> bool:
        """Erkennt grob Obsidian-Linksyntax `[[...]]` im Inhaltstext."""
        stripped = text.strip()
        return "[[" in stripped and "]]" in stripped

    @staticmethod
    def _extract_primary_link_target(text: str) -> str:
        """Extrahiert aus `[[...]]` den primären Zieldateinamen ohne Pfad/Endung."""
        match = re.search(r"\[\[([^\]]+)\]\]", text)
        if not match:
            return ""
        raw = match.group(1).strip()
        if "|" in raw:
            raw = raw.split("|", 1)[0].strip()
        if raw.lower().endswith(".md"):
            raw = raw[:-3].strip()
        if "/" in raw or "\\" in raw:
            raw = raw.replace("\\", "/").split("/")[-1].strip()
        return raw

    @staticmethod
    def _extract_markdown_link_target(text: str) -> str:
        """Extrahiert das sichtbare Linkziel (Alias bevorzugt) aus `[[...]]`."""
        match = re.search(r"\[\[([^\]]+)\]\]", text)
        if not match:
            return ""
        target = match.group(1).strip()
        if "|" in target:
            left, right = target.split("|", 1)
            return right.strip() or left.strip()
        return target

    @classmethod
    def _header_content_label(cls, inhalt: str) -> tuple[str, bool]:
        """Leitet Headertext ab und kennzeichnet, ob er aus einem Link stammt."""
        raw = str(inhalt).strip()
        if not raw:
            return "—", False
        link_target = cls._extract_markdown_link_target(raw)
        if link_target:
            return link_target, True
        return raw, False

    @staticmethod
    def _is_valid_unterricht_link(*, link: Path | None, link_target: str, group_name: str) -> bool:
        """Validiert, ob ein Link auf eine verwaltete Stunden-Datei zeigt."""
        if not (isinstance(link, Path) and link.exists() and link.is_file()):
            return False
        if link.parent.name.lower() != "einheiten":
            return False
        return True

    def _ensure_valid_lesson_yaml(self, lesson_path: Path, topic: str) -> LessonYamlData:
        """Lädt und validiert YAML einer Stunden-Datei und ergänzt fehlende Keys.

        Bei komplett fehlendem Frontmatter wird kein stilles Auto-Fix ausgeführt,
        sondern ein gezielter `MissingLessonYamlFrontmatterError` ausgelöst,
        damit die GUI eine Nutzerentscheidung zur Art-Auswahl anbieten kann.

        Für vorhandenes Frontmatter ergänzt der Use Case fehlende Schlüssel nur
        in-memory und gibt ein normiertes `LessonYamlData` zurück.
        """
        try:
            lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        except Exception as exc:
            error_text = str(exc)
            if "Fehlendes YAML-Frontmatter" in error_text:
                raise MissingLessonYamlFrontmatterError(lesson_path, error_text) from exc
            raise

        merged_data = canonicalize_lesson_yaml(
            lesson.data if isinstance(lesson.data, dict) else {},
            topic_hint=topic,
        )

        topic_now = str(merged_data.get("Stundenthema", "")).strip()
        if not topic_now and topic.strip():
            merged_data["Stundenthema"] = topic.strip()

        return LessonYamlData(lesson_path=lesson.lesson_path, data=merged_data)

    def execute(self, markdown_path: Path) -> PlanDetailResult:
        """Lädt Tabelle und erzeugt Spalten-Daten für die Detailansicht."""
        table = self.plan_repo.load_plan_table(markdown_path)
        return PlanDetailResult(table=table, day_columns=self.build_day_columns(table))

    def build_day_columns(self, table: PlanTableData) -> list[dict[str, object]]:
        """Erzeugt aufbereitete Tages-Spalten inkl. geladener YAML-Daten."""
        header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
        idx_datum = header_map.get("datum", 0)
        idx_stunden = header_map.get("stunden", 1)
        idx_inhalt = header_map.get("inhalt", 2)
        group_name = strip_wiki_link(str(table.metadata.get("Lerngruppe", "")))

        collected: list[dict[str, object]] = []
        for row_index, row in enumerate(table.rows):
            datum = row[idx_datum] if idx_datum < len(row) else ""
            stunden = row[idx_stunden] if idx_stunden < len(row) else ""
            inhalt = row[idx_inhalt] if idx_inhalt < len(row) else ""
            marker_text = normalize_marker_text(inhalt)

            link = self.lesson_repo.resolve_row_link_path(table, row_index)
            has_link_ref = self._contains_markdown_link(inhalt)
            link_target = self._extract_primary_link_target(inhalt)
            valid_unterricht_link = self._is_valid_unterricht_link(
                link=link,
                link_target=link_target,
                group_name=group_name,
            )
            is_cancel = is_ausfall_marker(marker_text)
            is_unresolved_link = bool(inhalt.strip() and has_link_ref and link is None)
            is_hospitation = is_hospitation_marker(marker_text, group_name)
            is_unterricht = is_unterricht_marker(marker_text, group_name)

            yaml_data: dict[str, object] = {}
            lesson_type = "Unterricht"
            if valid_unterricht_link and isinstance(link, Path):
                extracted_topic = link_target
                split = link_target.split(" ", 1)
                if len(split) == 2:
                    extracted_topic = split[1].strip() or link_target
                lesson = self._ensure_valid_lesson_yaml(link, topic=extracted_topic)
                yaml_data = lesson.data if isinstance(lesson.data, dict) else {}
                lesson_type = infer_stundentyp(yaml_data)
                ub_link = str(yaml_data.get("Unterrichtsbesuch", "")).strip()
                if ub_link:
                    steps, resources = self._load_ub_development_lists(
                        workspace_root=self._workspace_root_from_table(table),
                        ub_link_stem=ub_link,
                    )
                    yaml_data = dict(yaml_data)
                    yaml_data["Professionalisierungsschritte"] = steps
                    yaml_data["Nutzbare Ressourcen"] = resources

            is_lzk = lesson_type == "LZK"
            header_content = marker_text or ""
            is_link_header = bool(has_link_ref)

            if lesson_type == "Ausfall":
                is_cancel = True
            if lesson_type == "Hospitation":
                is_hospitation = True
            if lesson_type == "Unterricht":
                is_unterricht = True

            collected.append(
                {
                    "row_index": row_index,
                    "datum": datum,
                    "stunden": stunden,
                    "inhalt": inhalt,
                    "link": link,
                    "is_cancel": is_cancel,
                    "is_unresolved_link": is_unresolved_link,
                    "is_hospitation": is_hospitation,
                    "is_unterricht": is_unterricht,
                    "is_lzk": is_lzk,
                    "is_ub": bool(str(yaml_data.get("Unterrichtsbesuch", "")).strip()),
                    "is_valid_unterricht_file": valid_unterricht_link,
                    "yaml": yaml_data,
                    "Stundentyp": lesson_type,
                    "content_marker_text": marker_text,
                    "header_content": header_content,
                    "is_link_header": is_link_header,
                }
            )

        return collected
