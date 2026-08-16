from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

from kursplaner.core.domain.plan_row_placement import find_stattfindend_rows_in_range
from kursplaner.core.domain.plan_table import parse_plan_row_date
from kursplaner.core.domain.school_wide_cancellation import (
    SchoolWideCancellationEntry,
    course_key_for_path,
    find_claiming_entry,
)
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.ports.repositories import PlanRepository


def _col_index(headers: list[str], name: str) -> int | None:
    """Liefert den Index einer Spaltenueberschrift (case-insensitiv); None falls fehlt."""
    lc = name.lower()
    for i, h in enumerate(headers):
        if str(h).strip().lower() == lc:
            return i
    return None


@dataclass(frozen=True)
class AffectedUnit:
    """Eine im gewaehlten Zeitraum/Stufen-Set betroffene Einheit eines Kurses."""

    markdown_path: Path
    course_label: str
    row_index: int
    datum: date
    content_preview: str
    claimed_by_reason: str | None


@dataclass(frozen=True)
class SchoolWideCancellationPreviewResult:
    """Ergebnis der Live-Vorschau: alle betroffenen Einheiten, chronologisch sortiert."""

    affected_units: tuple[AffectedUnit, ...]

    @property
    def affected_course_count(self) -> int:
        """Anzahl unterschiedlicher betroffener Kurse."""
        return len({unit.markdown_path for unit in self.affected_units})


class SchoolWideCancellationPreviewUseCase:
    """Berechnet, welche Kurse/Einheiten von einem schulweiten Ausfall betroffen waeren.

    Read-only, arbeitet direkt auf `PlanTableData.rows` statt `DayColumn`, um
    fuer die Live-Vorschau bei jeder Datums-/Stufenaenderung keine teuren
    YAML-/Link-Ladevorgaenge pro Zeile auszuloesen. Wird auch intern von
    `SchoolWideCancellationApplyUseCase` genutzt, um denselben betroffenen
    Zeilen-Satz zu ermitteln - eine Selektionslogik statt zweier, die
    auseinanderlaufen koennten.
    """

    def __init__(self, plan_repo: PlanRepository):
        """Nimmt das Plan-Repository fuer den kursuebergreifenden Lesezugriff entgegen."""
        self._plan_repo = plan_repo

    def compute(
        self,
        *,
        base_dir: Path,
        date_from: date,
        date_to: date,
        grade_levels: frozenset[int],
        other_entries: Sequence[SchoolWideCancellationEntry] = (),
        exclude_entry_id: str | None = None,
    ) -> SchoolWideCancellationPreviewResult:
        """Ermittelt alle betroffenen Einheiten ueber alle passenden Kurse.

        Args:
            base_dir: Unterrichts-Basisverzeichnis mit allen Kursordnern.
            date_from: Erster Tag des Ausfall-Zeitraums.
            date_to: Letzter Tag des Ausfall-Zeitraums.
            grade_levels: Konkrete, bereits aufgeloeste betroffene Jahrgangsstufen.
            other_entries: Andere aktive Eintraege, gegen die auf Tag-Exklusivitaet
                geprueft wird (siehe `school_wide_cancellation.find_claiming_entry`).
            exclude_entry_id: Beim Bearbeiten eines bestehenden Eintrags dessen
                eigene ID, damit er sich nicht selbst als Kollision meldet.
        """
        if grade_levels:
            grade_levels_by_stufe = grade_levels
        else:
            grade_levels_by_stufe = frozenset()

        affected: list[AffectedUnit] = []
        for markdown_path in self._plan_repo.list_plan_markdown_files(base_dir):
            if not self._matches_grade(markdown_path, grade_levels_by_stufe):
                continue

            try:
                table = self._plan_repo.load_plan_table(markdown_path)
            except Exception:
                continue

            row_indices = find_stattfindend_rows_in_range(table.headers, table.rows, date_from, date_to)
            if not row_indices:
                continue

            course_key = course_key_for_path(markdown_path)
            idx_datum = _col_index(table.headers, "datum")
            idx_inhalt = _col_index(table.headers, "inhalt")
            group_name = strip_wiki_link(str(table.metadata.get("Lerngruppe", "")))
            course_label = group_name or markdown_path.parent.name

            for row_index in row_indices:
                row = table.rows[row_index]
                raw_datum = row[idx_datum] if idx_datum is not None and idx_datum < len(row) else ""
                row_datum = parse_plan_row_date(raw_datum)
                if row_datum is None:
                    continue

                claiming_entry = find_claiming_entry(
                    other_entries,
                    course_key=course_key,
                    target_date=row_datum,
                    exclude_entry_id=exclude_entry_id,
                )
                inhalt = row[idx_inhalt] if idx_inhalt is not None and idx_inhalt < len(row) else ""
                affected.append(
                    AffectedUnit(
                        markdown_path=markdown_path,
                        course_label=course_label,
                        row_index=row_index,
                        datum=row_datum,
                        content_preview=strip_wiki_link(str(inhalt)).strip(),
                        claimed_by_reason=claiming_entry.reason if claiming_entry is not None else None,
                    )
                )

        affected.sort(key=lambda unit: (unit.datum, unit.course_label))
        return SchoolWideCancellationPreviewResult(affected_units=tuple(affected))

    def _matches_grade(self, markdown_path: Path, grade_levels: frozenset[int]) -> bool:
        if not grade_levels:
            return False
        try:
            metadata = self._plan_repo.load_plan_metadata(markdown_path)
        except Exception:
            return False
        stufe_raw = str(metadata.get("Stufe", "")).strip()
        return stufe_raw.isdigit() and int(stufe_raw) in grade_levels
