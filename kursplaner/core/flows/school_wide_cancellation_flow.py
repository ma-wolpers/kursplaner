from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from kursplaner.core.domain.school_wide_cancellation import (
    CourseApplicationLedger,
    SchoolWideCancellationEntry,
    course_key_for_path,
)
from kursplaner.core.ports.repositories import ConflictDecision
from kursplaner.core.usecases.bulk_cancellation_coordinator import (
    BulkCancellationCoordinator,
    BulkOperationResult,
    CourseOperationOutcome,
    OperationKind,
    PlannedOperation,
)
from kursplaner.core.usecases.school_wide_cancellation_preview_usecase import (
    SchoolWideCancellationPreviewResult,
    SchoolWideCancellationPreviewUseCase,
)

StoreLoad = Callable[[], list[SchoolWideCancellationEntry]]
StoreSave = Callable[[list[SchoolWideCancellationEntry]], None]


@dataclass(frozen=True)
class SchoolWideCancellationMutationResult:
    """Ergebnis von `create`/`edit`: das (ggf. nur teilweise) aktualisierte Entry plus Bulk-Ergebnis.

    `entry` ist `None`, wenn der gesamte Vorgang zurueckgerollt wurde
    (`bulk_result.aborted`) - dann wurde nichts persistiert.
    """

    entry: SchoolWideCancellationEntry | None
    bulk_result: BulkOperationResult


class SchoolWideCancellationFlow:
    """Duenne Orchestrierung fuer schulweite Ausfaelle: Kurs-Operationen planen, Coordinator aufrufen, persistieren.

    Enthaelt selbst keine Fehlerbehandlung (siehe `BulkCancellationCoordinator`)
    und keine Zeilen-Mutationslogik (siehe die single-course Apply-/Revert-
    Usecases) - nur die Frage "welche Kurse muessen fuer dieses Entry aktuell
    apply/revert bekommen" und das Zusammenspiel mit dem persistenten Store.

    `course_ledgers` eines Entrys ist keine atomare Alles-oder-Nichts-Grosse,
    sondern die aktuell konvergierte Wahrheit: genau die Kurse, fuer die der
    Ausfall gerade tatsaechlich angewendet ist. Wird beim Erstellen ein Kurs
    uebersprungen, landet er einfach nicht in `course_ledgers` - ein spaeteres
    `edit()` (auch ohne Parameteraenderung) gleicht automatisch ab und holt
    ihn nach, sofern er dann noch zutrifft.
    """

    def __init__(
        self,
        preview_uc: SchoolWideCancellationPreviewUseCase,
        coordinator: BulkCancellationCoordinator,
        store_load: StoreLoad,
        store_save: StoreSave,
    ) -> None:
        """Nimmt Preview-Usecase, Coordinator und Store-Zugriff (Laden/Speichern) entgegen."""
        self._preview_uc = preview_uc
        self._coordinator = coordinator
        self._store_load = store_load
        self._store_save = store_save

    def list_entries(self) -> list[SchoolWideCancellationEntry]:
        """Liefert alle persistierten Eintraege."""
        return self._store_load()

    def preview(
        self,
        *,
        base_dir: Path,
        date_from: date,
        date_to: date,
        grade_levels: frozenset[int],
        exclude_entry_id: str | None = None,
    ) -> SchoolWideCancellationPreviewResult:
        """Berechnet die Live-Vorschau gegen den aktuell persistierten Entry-Bestand."""
        entries = self._store_load()
        return self._preview_uc.compute(
            base_dir=base_dir,
            date_from=date_from,
            date_to=date_to,
            grade_levels=grade_levels,
            other_entries=entries,
            exclude_entry_id=exclude_entry_id,
        )

    def create(
        self,
        *,
        base_dir: Path,
        date_from: date,
        date_to: date,
        grade_levels: frozenset[int],
        reason: str,
        decide: ConflictDecision,
    ) -> SchoolWideCancellationMutationResult:
        """Legt einen neuen Eintrag an und wendet ihn sofort auf alle passenden, freien Kurse an."""
        entries = self._store_load()
        preview = self._preview_uc.compute(
            base_dir=base_dir, date_from=date_from, date_to=date_to, grade_levels=grade_levels, other_entries=entries
        )
        operations = self._build_apply_operations(preview, date_from=date_from, date_to=date_to, reason=reason)

        bulk_result = self._coordinator.run(operations, decide=decide)
        if bulk_result.aborted:
            return SchoolWideCancellationMutationResult(entry=None, bulk_result=bulk_result)

        entry = SchoolWideCancellationEntry(
            entry_id=uuid.uuid4().hex,
            reason=reason,
            date_from=date_from,
            date_to=date_to,
            grade_levels=grade_levels,
            created_at=datetime.now().isoformat(timespec="seconds"),
            course_ledgers=self._ledgers_from_apply_results(bulk_result),
        )
        entries.append(entry)
        self._store_save(entries)
        return SchoolWideCancellationMutationResult(entry=entry, bulk_result=bulk_result)

    def edit(
        self,
        *,
        entry_id: str,
        base_dir: Path,
        date_from: date,
        date_to: date,
        grade_levels: frozenset[int],
        reason: str,
        decide: ConflictDecision,
    ) -> SchoolWideCancellationMutationResult:
        """Gleicht `course_ledgers` gegen die neuen Parameter ab: Wegfall -> Revert, Neuzugang -> Apply.

        Laeuft als ZWEI Phasen (erst alle bisher getrackten Kurse zuruecknehmen,
        DANACH die Vorschau fuer die neuen Parameter frisch berechnen und
        anwenden) - nicht als ein kombinierter Batch. Grund: solange ein Kurs
        noch die alte Ausfall-Markierung dieses Entrys traegt, gilt er fuer
        `find_stattfindend_rows_in_range` als nicht-stattfindend und wuerde in
        einer vorab (vor dem Revert) berechneten Vorschau faelschlich als
        "nicht betroffen" erscheinen - genau die Tage, die derselbe Entry
        weiterhin beanspruchen soll, gingen dann verloren. Erst nach dem
        Revert sind sie fuer eine frische Vorschau wieder sichtbar.

        Bricht die Apply-Phase ab (Rollback-Entscheidung), werden die in
        Phase 1 bereits zurueckgenommenen Kurse per Kompensations-Apply mit
        den ALTEN Parametern wiederhergestellt, damit `edit()` insgesamt
        keine Spur hinterlaesst.
        """
        entries = self._store_load()
        existing = self._require_entry(entries, entry_id)
        other_entries = [e for e in entries if e.entry_id != entry_id]
        previously_tracked = sorted((Path(key) for key in existing.course_ledgers), key=str)

        revert_operations = [
            PlannedOperation(
                kind=OperationKind.REVERT,
                markdown_path=path,
                course_label=path.parent.name,
                date_from=existing.date_from,
                date_to=existing.date_to,
                reason=existing.reason,
                ledger=existing.course_ledgers[course_key_for_path(path)],
            )
            for path in previously_tracked
        ]
        revert_result = self._coordinator.run(revert_operations, decide=decide)
        if revert_result.aborted:
            return SchoolWideCancellationMutationResult(entry=None, bulk_result=revert_result)

        preview = self._preview_uc.compute(
            base_dir=base_dir,
            date_from=date_from,
            date_to=date_to,
            grade_levels=grade_levels,
            other_entries=other_entries,
        )
        apply_operations = self._build_apply_operations(preview, date_from=date_from, date_to=date_to, reason=reason)
        apply_result = self._coordinator.run(apply_operations, decide=decide)

        if apply_result.aborted:
            restore_operations = [
                PlannedOperation(
                    kind=OperationKind.APPLY,
                    markdown_path=path,
                    course_label=path.parent.name,
                    date_from=existing.date_from,
                    date_to=existing.date_to,
                    reason=existing.reason,
                )
                for path in previously_tracked
            ]
            restore_result = self._coordinator.run(restore_operations, decide=decide)
            combined = BulkOperationResult(
                aborted=True,
                course_results=(*revert_result.course_results, *apply_result.course_results, *restore_result.course_results),
            )
            return SchoolWideCancellationMutationResult(entry=None, bulk_result=combined)

        combined = BulkOperationResult(
            aborted=False, course_results=(*revert_result.course_results, *apply_result.course_results)
        )

        course_ledgers: dict[str, CourseApplicationLedger] = {}
        for result in combined.course_results:
            key = course_key_for_path(result.markdown_path)
            if result.kind is OperationKind.APPLY:
                if result.outcome is CourseOperationOutcome.SUCCESS and result.ledger is not None and result.ledger.moves:
                    course_ledgers[key] = result.ledger
            elif result.outcome is CourseOperationOutcome.SKIPPED:
                # Revert uebersprungen: Kurs traegt weiterhin die alte Markierung, Ledger bleibt gueltig.
                course_ledgers[key] = existing.course_ledgers[key]

        updated_entry = replace(
            existing,
            reason=reason,
            date_from=date_from,
            date_to=date_to,
            grade_levels=grade_levels,
            course_ledgers=course_ledgers,
        )
        self._store_save([updated_entry if e.entry_id == entry_id else e for e in entries])
        return SchoolWideCancellationMutationResult(entry=updated_entry, bulk_result=combined)

    def delete(self, *, entry_id: str, decide: ConflictDecision) -> BulkOperationResult:
        """Nimmt alle Kurs-Verschiebungen eines Eintrags zurueck und entfernt ihn (bei vollstaendigem Erfolg)."""
        entries = self._store_load()
        existing = self._require_entry(entries, entry_id)

        operations = [
            PlannedOperation(
                kind=OperationKind.REVERT,
                markdown_path=Path(course_key),
                course_label=Path(course_key).parent.name,
                date_from=existing.date_from,
                date_to=existing.date_to,
                reason=existing.reason,
                ledger=ledger,
            )
            for course_key, ledger in existing.course_ledgers.items()
        ]
        bulk_result = self._coordinator.run(operations, decide=decide)
        if bulk_result.aborted:
            return bulk_result

        remaining_ledgers = {
            course_key_for_path(result.markdown_path): existing.course_ledgers[course_key_for_path(result.markdown_path)]
            for result in bulk_result.course_results
            if result.outcome is CourseOperationOutcome.SKIPPED
        }
        if remaining_ledgers:
            updated_entry = replace(existing, course_ledgers=remaining_ledgers)
            entries = [updated_entry if e.entry_id == entry_id else e for e in entries]
        else:
            entries = [e for e in entries if e.entry_id != entry_id]
        self._store_save(entries)
        return bulk_result

    @staticmethod
    def _require_entry(entries: list[SchoolWideCancellationEntry], entry_id: str) -> SchoolWideCancellationEntry:
        for entry in entries:
            if entry.entry_id == entry_id:
                return entry
        raise ValueError(f"Unbekannter Ausfall-Eintrag: {entry_id}")

    @staticmethod
    def _build_apply_operations(
        preview: SchoolWideCancellationPreviewResult, *, date_from: date, date_to: date, reason: str
    ) -> list[PlannedOperation]:
        course_labels: dict[Path, str] = {}
        free_paths: set[Path] = set()
        for unit in preview.affected_units:
            course_labels.setdefault(unit.markdown_path, unit.course_label)
            if unit.claimed_by_reason is None:
                free_paths.add(unit.markdown_path)

        return [
            PlannedOperation(
                kind=OperationKind.APPLY,
                markdown_path=path,
                course_label=course_labels.get(path, path.parent.name),
                date_from=date_from,
                date_to=date_to,
                reason=reason,
            )
            for path in sorted(free_paths, key=str)
        ]

    @staticmethod
    def _ledgers_from_apply_results(bulk_result: BulkOperationResult) -> dict[str, CourseApplicationLedger]:
        return {
            course_key_for_path(result.markdown_path): result.ledger
            for result in bulk_result.course_results
            if result.outcome is CourseOperationOutcome.SUCCESS and result.ledger is not None and result.ledger.moves
        }
