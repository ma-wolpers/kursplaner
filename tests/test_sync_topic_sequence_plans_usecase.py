from pathlib import Path

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.sync_sequence_export_table_usecase import SyncSequenceExportTableUseCase
from kursplaner.core.usecases.sync_topic_sequence_plans_usecase import SyncTopicSequencePlansUseCase
from kursplaner.infrastructure.repositories.sequence_plan_repository import FileSystemSequencePlanRepository
from tests.day_column_factory import make_day_column


def _usecase(repo: FileSystemSequencePlanRepository) -> SyncTopicSequencePlansUseCase:
    return SyncTopicSequencePlansUseCase(
        sequence_plan_repo=repo,
        sequence_export_sync=SyncSequenceExportTableUseCase(sequence_plan_repo=repo),
    )


def _table(tmp_path: Path) -> PlanTableData:
    plan_dir = tmp_path / "Unterricht" / "M GK blau-1 26-2"
    plan_dir.mkdir(parents=True, exist_ok=True)
    return PlanTableData(
        markdown_path=plan_dir / "M GK blau-1 26-2.md",
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Lerngruppe": "[[GK blau-1]]"},
    )


def _day(*, row_index: int, kind: str, obert: str = "", datum: str = "", thema: str = "") -> DayColumn:
    """Baut eine `DayColumn` mit den in diesen Tests ausschließlich verwendeten "Unterricht"-Zeilen.

    Ohne gültigen Link liefert `DayColumn.stundentyp` immer ``"Unterricht"``
    (siehe `day_column.py`), was hier genügt, da diese Testdatei nie andere
    Stundentypen braucht.
    """
    return make_day_column(
        row_index=row_index,
        datum=datum,
        yaml={"Stundentyp": kind, "Oberthema": obert, "Stundenthema": thema},
    )


def test_creates_sequence_file_only_for_runs_with_at_least_two_members(tmp_path):
    usecase = _usecase(FileSystemSequencePlanRepository())
    table = _table(tmp_path)

    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="Lineare Funktionen"),
        _day(row_index=1, kind="Unterricht", obert="Lineare Funktionen"),
        _day(row_index=2, kind="Unterricht", obert="Einzelthema"),
    ]

    views = usecase.execute(table=table, day_columns=day_columns)

    assert len(views) == 1
    assert views[0].run.oberthema == "Lineare Funktionen"
    assert views[0].sequence_path.exists()
    assert views[0].sequenzziel == ""
    assert views[0].leitkompetenz == ""
    assert views[0].is_incomplete is True


def test_resync_is_idempotent_and_reads_back_persisted_values(tmp_path):
    repo = FileSystemSequencePlanRepository()
    usecase = _usecase(repo)
    table = _table(tmp_path)

    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="Ableitungen"),
        _day(row_index=1, kind="Unterricht", obert="Ableitungen"),
    ]

    first_views = usecase.execute(table=table, day_columns=day_columns)
    repo.write_goal_and_focus_competency(
        sequence_path=first_views[0].sequence_path,
        sequenzziel="Ableitungen sicher anwenden",
        leitkompetenz="Modellieren",
    )

    second_views = usecase.execute(table=table, day_columns=day_columns)

    assert len(second_views) == 1
    assert second_views[0].sequence_path == first_views[0].sequence_path
    assert second_views[0].sequenzziel == "Ableitungen sicher anwenden"
    assert second_views[0].leitkompetenz == "Modellieren"
    assert second_views[0].is_incomplete is False


def test_no_sequences_detected_returns_empty_list(tmp_path):
    usecase = _usecase(FileSystemSequencePlanRepository())
    table = _table(tmp_path)

    day_columns = [_day(row_index=0, kind="Unterricht", obert="Einzelthema")]

    assert usecase.execute(table=table, day_columns=day_columns) == []


def test_auto_sync_writes_export_table_without_manual_export(tmp_path):
    """Regression: die '## Export'-Tabelle einer Sequenz-md muss schon beim
    automatischen Sync gefuellt werden, nicht erst beim manuellen Export."""
    usecase = _usecase(FileSystemSequencePlanRepository())
    table = _table(tmp_path)

    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="Kodierung", datum="13-02-26", thema="Caesar"),
        _day(row_index=1, kind="Unterricht", obert="Kodierung", datum="20-02-26", thema="Vigenere"),
    ]

    views = usecase.execute(table=table, day_columns=day_columns)

    content = views[0].sequence_path.read_text(encoding="utf-8")
    assert "Caesar" in content
    assert "Vigenere" in content
    assert "13.02.2026" in content
    assert "20.02.2026" in content


def test_cleared_oberthema_removes_unit_from_export_table(tmp_path):
    """Regression: Löschen des Oberthemas einer Einheit muss sie aus der
    Sequenz-md entfernen, auch wenn der Lauf dadurch unter die Mindestgröße
    fällt (Bugreport: Einheit blieb bisher in der Export-Tabelle stehen)."""
    repo = FileSystemSequencePlanRepository()
    usecase = _usecase(repo)
    table = _table(tmp_path)

    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="Kodierung", datum="13-02-26", thema="Caesar"),
        _day(row_index=1, kind="Unterricht", obert="Kodierung", datum="20-02-26", thema="Vigenere"),
    ]
    first_views = usecase.execute(table=table, day_columns=day_columns)
    sequence_path = first_views[0].sequence_path
    repo.write_goal_and_focus_competency(
        sequence_path=sequence_path, sequenzziel="Verschlüsselungen verstehen", leitkompetenz="Modellieren"
    )
    assert "Caesar" in sequence_path.read_text(encoding="utf-8")

    # Oberthema der ersten Einheit wird gelöscht -> Lauf schrumpft auf 1 Mitglied.
    day_columns_after_clear = [
        _day(row_index=0, kind="Unterricht", obert="", datum="13-02-26", thema="Caesar"),
        _day(row_index=1, kind="Unterricht", obert="Kodierung", datum="20-02-26", thema="Vigenere"),
    ]

    views = usecase.execute(table=table, day_columns=day_columns_after_clear)

    assert views == []
    content = sequence_path.read_text(encoding="utf-8")
    assert "Caesar" not in content
    assert "Vigenere" not in content
    # Datei bleibt erhalten, da Sequenzziel/Leitkompetenz noch gesetzt sind (nicht trivial).
    assert sequence_path.exists()


def test_cleared_oberthema_deletes_file_when_it_becomes_fully_trivial(tmp_path):
    """Wird eine Sequenzdatei durch das Bereinigen komplett inhaltsleer
    (kein Sequenzziel/Leitkompetenz/Brainstorming), wird sie gelöscht."""
    repo = FileSystemSequencePlanRepository()
    usecase = _usecase(repo)
    table = _table(tmp_path)

    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="Kodierung", datum="13-02-26", thema="Caesar"),
        _day(row_index=1, kind="Unterricht", obert="Kodierung", datum="20-02-26", thema="Vigenere"),
    ]
    first_views = usecase.execute(table=table, day_columns=day_columns)
    sequence_path = first_views[0].sequence_path

    day_columns_after_clear = [
        _day(row_index=0, kind="Unterricht", obert="", datum="13-02-26", thema="Caesar"),
        _day(row_index=1, kind="Unterricht", obert="", datum="20-02-26", thema="Vigenere"),
    ]

    views = usecase.execute(table=table, day_columns=day_columns_after_clear)

    assert views == []
    assert not sequence_path.exists()


def test_sync_ignores_sequence_documents_whose_run_still_qualifies(tmp_path):
    """Läuft ein Sequenzname weiterhin qualifiziert, darf die Bereinigung ihn
    nicht anfassen (Abgrenzung: nur tatsächlich verwaiste Dateien werden geprüft)."""
    repo = FileSystemSequencePlanRepository()
    usecase = _usecase(repo)
    table = _table(tmp_path)

    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="Kodierung", datum="13-02-26", thema="Caesar"),
        _day(row_index=1, kind="Unterricht", obert="Kodierung", datum="20-02-26", thema="Vigenere"),
    ]

    views = usecase.execute(table=table, day_columns=day_columns)
    sequence_path = views[0].sequence_path
    content = sequence_path.read_text(encoding="utf-8")
    assert "Caesar" in content
    assert "Vigenere" in content
