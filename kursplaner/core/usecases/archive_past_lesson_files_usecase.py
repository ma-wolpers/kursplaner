"""Use Case: Einheitsdateien mit vergangenem Datum in Alteinheiten/ archivieren.

Beim Programmstart werden alle Stundendateien, deren Datum (aus der Planungstabelle)
in der Vergangenheit liegt, automatisch vom primären ``Einheiten``-Ordner in den
``Alteinheiten``-Ordner verschoben.  Wiki-Links in der Plantabelle müssen nicht
aktualisiert werden, da ``Alteinheiten`` als zweiter Suchpfad in
:func:`~kursplaner.core.domain.lesson_directory.managed_lesson_dir_names` registriert
ist.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.lesson_directory import LESSON_DIR_ARCHIVE, LESSON_DIR_PRIMARY
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.infrastructure.repositories.plan_table_file_repository import get_row_link_path


def _parse_plan_date(date_text: str) -> date | None:
    """Parst ``dd-mm-yy`` in ein :class:`datetime.date`-Objekt.

    Args:
        date_text: Rohtext der Datumsspalte, z. B. ``"10-03-26"``.

    Returns:
        Gepartes Datum oder ``None`` bei ungültigem Format.
    """
    raw = str(date_text or "").strip()
    try:
        d, m, y = raw.split("-")
        return date(2000 + int(y), int(m), int(d))
    except (ValueError, TypeError):
        return None


class ArchivePastLessonFilesUseCase:
    """Verschiebt vergangene Stundendateien in den Alteinheiten-Ordner.

    Der Use Case liest die Datumsspalte jeder Plantabellenzeile.  Liegt das Datum
    in der Vergangenheit *und* hat die Zeile einen gültigen Wiki-Link auf eine
    Datei im ``Einheiten``-Ordner, wird die Datei nach ``Alteinheiten/`` verschoben.
    Der ``Alteinheiten``-Ordner wird bei Bedarf angelegt.

    Wiki-Links in der Plantabelle bleiben unverändert, weil
    :func:`~kursplaner.core.domain.lesson_directory.managed_lesson_dir_names`
    beide Ordner als Suchpfade aufführt.
    """

    def execute(self, table: PlanTableData, *, reference_date: date | None = None) -> int:
        """Archiviert vergangene Stundendateien für eine Planungstabelle.

        Args:
            table: Planungstabelle mit Datum- und Inhalt-Spalten.
            reference_date: Vergleichsdatum (Standard: heutiges Datum).  Wird in
                Tests für deterministisches Verhalten übergeben.

        Returns:
            Anzahl der verschobenen Dateien.
        """
        today = reference_date if reference_date is not None else date.today()
        plan_dir = table.markdown_path.parent
        einheiten_dir = plan_dir / LESSON_DIR_PRIMARY
        archive_dir = plan_dir / LESSON_DIR_ARCHIVE

        header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
        idx_datum = header_map.get("datum", 0)

        moved = 0
        for row_index, row in enumerate(table.rows):
            datum_text = row[idx_datum] if idx_datum < len(row) else ""
            row_date = _parse_plan_date(datum_text)
            if row_date is None or row_date >= today:
                continue

            lesson_path = get_row_link_path(table, row_index)
            if lesson_path is None:
                continue
            if lesson_path.parent.resolve() != einheiten_dir.resolve():
                continue

            archive_dir.mkdir(parents=True, exist_ok=True)
            target = archive_dir / lesson_path.name
            if target.exists():
                continue

            lesson_path.rename(target)
            moved += 1

        return moved
