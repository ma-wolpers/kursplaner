from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.plan_row_payload import PayloadColumns
from kursplaner.core.domain.plan_row_placement import strip_empty_dateless_rows
from kursplaner.core.domain.plan_table import COLUMN_INHALT, COLUMN_THEMA_AUSFALL, header_index
from kursplaner.core.domain.row_identity import (
    MoveResolution,
    ResolutionStatus,
    SourceResolution,
    TargetResolution,
    resolve_move,
)
from kursplaner.core.domain.school_wide_cancellation import CourseApplicationLedger, UnitMove
from kursplaner.core.ports.repositories import PlanRepository


@dataclass(frozen=True)
class RevertIssue:
    """Ein Move, der nicht (automatisch) zurueckgenommen werden konnte."""

    move: UnitMove
    resolution: MoveResolution


@dataclass(frozen=True)
class RevertOutcome:
    """Ergebnis eines Revert-Versuchs fuer einen Kurs."""

    reverted_move_count: int
    issues: tuple[RevertIssue, ...]

    @property
    def is_complete(self) -> bool:
        """True, wenn jeder Move des Ledgers zurueckgenommen wurde."""
        return not self.issues


class SchoolWideCancellationRevertUseCase:
    """Nimmt die Wirkung eines `CourseApplicationLedger` in einem einzelnen Kurs zurueck.

    Reine Positions-Operation mit LIVE aktuellem Zellinhalt - kein
    Content-Snapshot. Fuer jeden Move wird zunaechst die Identitaet gegen die
    aktuelle Tabelle aufgeloest (`core.domain.row_identity.resolve_move`);
    nur bei eindeutigem Ergebnis (oder erzwungener Warnung) wird tatsaechlich
    geschrieben. Single-course, keine Fehler-/Konflikt-Entscheidungslogik -
    das ist Aufgabe des `BulkCancellationCoordinator`.
    """

    def __init__(self, plan_repo: PlanRepository) -> None:
        """Nimmt das Plan-Repository fuer Lade- und Speicheroperationen entgegen."""
        self._plan_repo = plan_repo

    def execute(
        self,
        *,
        markdown_path: Path,
        ledger: CourseApplicationLedger,
        force_warnings: bool = False,
    ) -> RevertOutcome:
        """Versucht, alle Moves des Ledgers in diesem Kurs zurueckzunehmen.

        Args:
            markdown_path: Zielkurs.
            ledger: Das zurueckzunehmende Bewegungs-Ledger.
            force_warnings: Wenn `True`, werden auch Moves mit `WARNING`-Status
                (z. B. geaenderte Referenz) zurueckgenommen ("trotzdem machen").
                Moves mit `ERROR`-Status werden nie automatisch zurueckgenommen.
        """
        table = self._plan_repo.load_plan_table(markdown_path)
        headers = table.headers
        idx_inhalt = header_index(headers, COLUMN_INHALT)
        idx_thema = header_index(headers, COLUMN_THEMA_AUSFALL)
        if idx_inhalt is None or idx_thema is None:
            missing_columns_issue = SourceResolution(
                ResolutionStatus.ERROR, None, "Spalten 'Inhalt'/'Thema/Ausfall' fehlen."
            )
            return RevertOutcome(
                reverted_move_count=0,
                issues=tuple(
                    RevertIssue(
                        move=move,
                        resolution=MoveResolution(
                            ResolutionStatus.ERROR,
                            missing_columns_issue,
                            TargetResolution(ResolutionStatus.ERROR, None),
                            missing_columns_issue.detail,
                        ),
                    )
                    for move in ledger.moves
                ),
            )

        reverted = 0
        issues: list[RevertIssue] = []
        for move in ledger.moves:
            resolution = resolve_move(headers, table.rows, move)
            if resolution.status == ResolutionStatus.ERROR:
                issues.append(RevertIssue(move=move, resolution=resolution))
                continue
            if resolution.status == ResolutionStatus.WARNING and not force_warnings:
                issues.append(RevertIssue(move=move, resolution=resolution))
                continue

            self._revert_single_move(table.rows, idx_inhalt=idx_inhalt, idx_thema=idx_thema, resolution=resolution)
            reverted += 1

        if reverted:
            table.rows = strip_empty_dateless_rows(headers, table.rows)
            self._plan_repo.save_plan_table(table)

        return RevertOutcome(reverted_move_count=reverted, issues=tuple(issues))

    @staticmethod
    def _revert_single_move(
        rows: list[list[str]],
        *,
        idx_inhalt: int,
        idx_thema: int,
        resolution: MoveResolution,
    ) -> None:
        """Schreibt den aktuellen Zielinhalt auf die Quellzeile zurueck und leert das Ziel."""
        source_index = resolution.source.row_index
        if source_index is None:
            return
        source_row = rows[source_index]
        columns = PayloadColumns(idx_inhalt, idx_thema)
        # Die Ausfall-Markierung der Quelle wird bewusst entfernt (Rücknahme des Ausfalls).
        columns.clear_slot_marker(source_row)

        target_index = resolution.target.row_index
        if target_index is None:
            return  # Storniert ohne verdraengten Inhalt: nur die Markierung war zu entfernen.

        target_row = rows[target_index]
        columns.write(source_row, columns.read(target_row))
        columns.clear(target_row)
