"""Lebenszyklus-Klassifikation eines Kurses (aktiv vs. ehemalig).

Buendelt die einzige Definition von "ehemaliger Kurs" (siehe
:func:`is_former_course`) sowie die Pfad-Konvention fuer das Kurs-Archiv,
in das ehemalige Kurse automatisch verschoben werden (siehe
``core.usecases.archive_former_courses_usecase``).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData, parse_plan_row_date

COURSE_ARCHIVE_RELATIVE_PARTS: tuple[str, ...] = ("-ALT",)
"""Relativer Pfad des Kurs-Archivs unterhalb von ``unterricht_dir``.

Entspricht dem real im Vault vorhandenen Ordner (``10 Unterricht/-ALT/<Kurs>``,
Kurse liegen dort direkt, ohne weitere Verschachtelung).
"""


def course_archive_root(unterricht_dir: Path) -> Path:
    """Liefert den Wurzelordner des Kurs-Archivs unterhalb eines Unterrichtsordners."""
    root = unterricht_dir
    for part in COURSE_ARCHIVE_RELATIVE_PARTS:
        root = root / part
    return root


def is_archived_course_path(plan_markdown_path: Path, unterricht_dir: Path) -> bool:
    """Prueft, ob ein Plan-Dateipfad innerhalb des Kurs-Archivs liegt."""
    try:
        plan_markdown_path.resolve().relative_to(course_archive_root(unterricht_dir).resolve())
    except ValueError:
        return False
    return True


def last_plan_date(table: PlanTableData) -> date | None:
    """Liefert das spaeteste in der Plantabelle vorkommende Datum, ``None`` falls keins gueltig ist."""
    header_map = {str(name).strip().lower(): idx for idx, name in enumerate(table.headers)}
    idx_datum = header_map.get("datum")
    if idx_datum is None:
        return None
    dates = [parse_plan_row_date(row[idx_datum]) for row in table.rows if row and idx_datum < len(row)]
    valid_dates = [d for d in dates if d is not None]
    return max(valid_dates) if valid_dates else None


def is_former_course(table: PlanTableData, today: date) -> bool:
    """Prueft, ob ein Kurs als 'ehemalig' gilt.

    Einzige Definition von "ehemaliger Kurs" im gesamten System: ein Kurs
    gilt als ehemalig, sobald sein spaetestes Plantabellen-Datum in der
    Vergangenheit liegt (``last_plan_date(table) < today``). Diese Funktion
    ist bewusst die *einzige* Stelle mit dieser Definition - sie wird sich
    absehbar aendern und darf nicht andernorts dupliziert werden. Sowohl die
    automatische Archivierung (``ArchiveFormerCoursesUseCase``) als auch die
    "Ehemalige anzeigen"-Filterung in der Kursuebersicht rufen ausschliesslich
    diese Funktion auf.

    Args:
        table: Geladene Planungstabelle des Kurses.
        today: Referenzdatum (i. d. R. das heutige Datum).

    Returns:
        ``True``, wenn der Kurs als ehemalig gilt.
    """
    last = last_plan_date(table)
    return last is not None and last < today
