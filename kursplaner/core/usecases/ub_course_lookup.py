"""Einheit → Kurs (Name und Jahrgangsstufe) für die kursübergreifende UB-Ansicht – eine Stelle.

UB-Plan (Kursspalte) und UB-Achievements (Jahrgangs-Vorgaben) brauchen dieselbe
Zuordnung; vorher baute jeder Use Case sie selbst aus den Plantabellen.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.unterrichtsbesuch_policy import parse_jahrgangsstufe
from kursplaner.core.domain.wiki_links import extract_wiki_link_target
from kursplaner.core.ports.repositories import PlanRepository


@dataclass(frozen=True)
class LessonCourse:
    """Kurs, zu dem eine Einheit gehört."""

    course_name: str
    stufe: int | None


def courses_by_lesson_stem(plan_repo: PlanRepository, unterricht_base_dir: Path) -> dict[str, LessonCourse]:
    """Ordnet jeder in einer Plantabelle verlinkten Einheit ihren Kurs zu.

    Grundlage ist die ``Inhalt``-Spalte aller aktiven und archivierten Kurse unter
    *unterricht_base_dir* (dem Unterrichtsordner, nicht einem einzelnen Kursordner).
    Die Stufe kommt ausschließlich aus der ``Stufe``-Metadatenangabe des Kurses.

    Args:
        plan_repo: Repository der Plantabellen.
        unterricht_base_dir: Konfigurierter Unterrichtsordner.

    Returns:
        ``lesson_stem`` → `LessonCourse`; leer, wenn der Ordner fehlt.

    Raises:
        RuntimeError: wenn derselbe ``lesson_stem`` in mehr als einem Kurs verlinkt
            ist – eine Einheit gehört strukturell genau einem Kurs, ein Datenfehler
            darf keinen falschen Kurs bzw. keine falsche Stufe liefern.
    """
    if not unterricht_base_dir.exists() or not unterricht_base_dir.is_dir():
        return {}

    result: dict[str, LessonCourse] = {}
    for table in plan_repo.load_plan_tables(unterricht_base_dir):
        course_name = table.markdown_path.parent.name
        header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
        inhalt_idx = header_map.get("inhalt")
        if inhalt_idx is None:
            continue
        course = LessonCourse(course_name=course_name, stufe=parse_jahrgangsstufe(table.metadata.get("Stufe")))
        for row in table.rows:
            if inhalt_idx >= len(row):
                continue
            stem = extract_wiki_link_target(row[inhalt_idx])
            if not stem:
                continue
            existing = result.get(stem)
            if existing is not None and existing.course_name != course_name:
                raise RuntimeError(
                    f"Uneindeutige Kurszuordnung: Einheit '{stem}' ist sowohl '{existing.course_name}' "
                    f"als auch '{course_name}' zugeordnet. Bitte die Kursdateien bereinigen."
                )
            result[stem] = course
    return result
