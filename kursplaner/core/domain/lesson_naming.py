from __future__ import annotations

from datetime import datetime

from kursplaner.core.domain.plan_table import PlanTableData, sanitize_hour_title


def parse_mmdd(date_text: str) -> str:
    """Konvertiert bekannte Datumsformate in den Dateiname-Token `mm-dd`."""
    raw = str(date_text or "").strip()
    if not raw:
        return "00-00"

    for pattern in ("%Y-%m-%d", "%d-%m-%y", "%d-%m-%Y", "%d.%m.%y", "%d.%m.%Y"):
        try:
            parsed = datetime.strptime(raw, pattern)
            return parsed.strftime("%m-%d")
        except ValueError:
            continue

    return "00-00"


def row_mmdd(table: PlanTableData, row_index: int) -> str:
    """Leitet fuer eine Tabellenzeile den `mm-dd`-Token aus der Datumsspalte ab."""
    header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
    idx_datum = header_map.get("datum")
    if idx_datum is None or not (0 <= row_index < len(table.rows)):
        return "00-00"
    row = table.rows[row_index]
    if idx_datum >= len(row):
        return "00-00"
    return parse_mmdd(row[idx_datum])


def build_lesson_stem(group_name: str, date_mmdd: str, content_title: str) -> str:
    """Baut den kanonischen Dateistamm `Lerngruppe mm-dd Inhalt`."""
    group = sanitize_hour_title(group_name) or "gruppe"
    mmdd = sanitize_hour_title(date_mmdd) or "00-00"
    content = sanitize_hour_title(content_title) or "einheit"
    return f"{group} {mmdd} {content}".strip()
