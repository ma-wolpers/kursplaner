"""Reine Datums-/Halbjahres-Formatierungshelfer für Export-Use-Cases.

Diese Funktionen enthalten keine Fachentscheidungen über *was* exportiert wird,
sondern ausschließlich Text-/Datumsformatierung, die von mehreren Export-Use-Cases
(z. B. `ExportTopicUnitsPdfUseCase`) benötigt wird. Die Extraktion in ein eigenes
Modul hält die aufrufenden Use-Case-Dateien innerhalb des Zeilenbudgets und macht
die Formatierung unabhängig testbar.
"""

from __future__ import annotations

from datetime import date, datetime

from kursplaner.core.domain.plan_table import PlanTableData

_DATE_INPUT_PATTERNS = ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d-%m-%Y", "%d-%m-%y")


def parse_day_date(raw_value: object) -> date | None:
    """Parst einen Datumstext in einem der unterstützten Eingabeformate.

    Args:
        raw_value: Roher Datumswert aus einer Tages-Spalte (meist ein String).

    Returns:
        Das geparste Datum oder ``None``, wenn kein bekanntes Format passt.
    """
    text = str(raw_value or "").strip()
    if not text:
        return None
    for pattern in _DATE_INPUT_PATTERNS:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def format_day_date(raw_value: object) -> str:
    """Formatiert einen Datumswert einheitlich als ``TT.MM.JJJJ``.

    Args:
        raw_value: Roher Datumswert aus einer Tages-Spalte.

    Returns:
        Das formatierte Datum, oder der unveränderte Originaltext, wenn er sich
        nicht parsen lässt.
    """
    parsed = parse_day_date(raw_value)
    if parsed is None:
        return str(raw_value or "").strip()
    return parsed.strftime("%d.%m.%Y")


def extract_term_token(table: PlanTableData) -> str:
    """Ermittelt das Halbjahres-Token (z. B. ``25-2``) aus Ordner- oder Dateinamen.

    Args:
        table: Planungstabelle, deren Pfad das Halbjahres-Token trägt.

    Returns:
        Das gefundene Halbjahres-Token.

    Raises:
        RuntimeError: Wenn sich kein Halbjahres-Token bestimmen lässt.
    """
    candidates = [table.markdown_path.parent.name, table.markdown_path.stem]
    for candidate in candidates:
        parts = str(candidate).strip().split()
        if not parts:
            continue
        token = parts[-1].strip()
        if len(token) == 4 and token[2] == "-" and token[:2].isdigit() and token[3] in {"1", "2"}:
            return token
    raise RuntimeError("Halbjahr konnte aus dem Kursnamen nicht bestimmt werden (erwartet z. B. '25-2').")


def schoolyear_from_term(term_token: str) -> str:
    """Wandelt ein Halbjahres-Token in eine lesbare Schuljahresangabe um.

    Args:
        term_token: Halbjahres-Token im Format ``JJ-H`` (z. B. ``25-2``).

    Returns:
        Schuljahresangabe im Format ``JJJJ/JJ`` (z. B. ``2025/26``).
    """
    year_short = int(term_token[:2])
    start_year = 2000 + year_short
    end_year_short = (year_short + 1) % 100
    return f"{start_year}/{end_year_short:02d}"
