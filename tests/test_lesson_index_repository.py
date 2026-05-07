import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.infrastructure.repositories.lesson_index_repository import FileSystemLessonIndexRepository


def create_dummy_lesson(path: Path, title: str, oberthema: str = ""):
    content = (
        "---\n"
        "Stundentyp: Unterricht\n"
        "Dauer: 2\n"
        "Kompetenzen:\n"
        '  - ""\n'
        "Stundenthema: " + title + "\n"
        'Stundenziel: ""\n'
        "Material:\n"
        '  - ""\n'
        "Oberthema: " + oberthema + "\n"
        "---\n\n# Inhalt\n"
    )
    path.write_text(content, encoding="utf-8")


def test_index_build_and_load(tmp_path):
    root = tmp_path / "Unterricht"
    (root / "FachA" / "Einheiten").mkdir(parents=True)
    (root / "FachB" / "Einheiten").mkdir(parents=True)

    a1 = root / "FachA" / "Einheiten" / "stunde-a1.md"
    a2 = root / "FachA" / "Einheiten" / "stunde-a2.md"
    b1 = root / "FachB" / "Einheiten" / "stunde-b1.md"

    create_dummy_lesson(a1, "Thema A1", "Ober A")
    create_dummy_lesson(a2, "Thema A2")
    create_dummy_lesson(b1, "Thema B1")

    repo = FileSystemLessonIndexRepository()
    # rebuild scans both FachA and FachB
    repo.rebuild_index(root)

    # create a minimal PlanTableData with rows linking to these files
    table = PlanTableData(
        markdown_path=root / "FachA" / "plan.md",
        headers=["datum", "inhalt"],
        rows=[["2026-03-01", "[[stunde-a1]]"], ["2026-03-02", "[[stunde-a2]]"], ["2026-03-03", "[[stunde-b1]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )

    # load metadata for rows
    metadata = repo.load_lessons_metadata_for_all_rows(table)
    assert isinstance(metadata, dict)
    # expect at least one metadata entry and that themes are discoverable
    assert isinstance(metadata, dict) and len(metadata) >= 1
    themes = [v.get("Stundenthema", "") for v in metadata.values()]
    assert "Thema A1" in themes
    # oberthema may be present for one of the entries
    ober_values = [v.get("Oberthema", "") for v in metadata.values()]
    assert "Ober A" in ober_values

    # invalidate and ensure cache cleared
    repo.invalidate_index()
    # after invalidation, cache repopulates on demand
    m2 = repo.load_lessons_metadata_for_rows(table, [0])
    assert m2[0]["Stundenthema"] == "Thema A1"


def test_index_detects_mtime_change(tmp_path):
    root = tmp_path / "Unterricht"
    (root / "FachA" / "Einheiten").mkdir(parents=True)
    a1 = root / "FachA" / "Einheiten" / "stunde-a1.md"
    create_dummy_lesson(a1, "Initial Thema")

    repo = FileSystemLessonIndexRepository()
    repo.rebuild_index(root)

    table = PlanTableData(
        markdown_path=root / "FachA" / "plan.md",
        headers=["datum", "inhalt"],
        rows=[["2026-03-01", "[[stunde-a1]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )
    m1 = repo.load_lessons_metadata_for_rows(table, [0])
    assert m1[0]["Stundenthema"] == "Initial Thema"

    old_mtime_ns = a1.stat().st_mtime_ns

    # modify file
    create_dummy_lesson(a1, "Updated Thema")
    # ensure mtime changes deterministically even on coarse filesystem clocks
    forced_mtime = max(a1.stat().st_mtime + 2.0, (old_mtime_ns / 1_000_000_000) + 2.0)
    os.utime(a1, (forced_mtime, forced_mtime))
    assert a1.stat().st_mtime_ns > old_mtime_ns

    m2 = repo.load_lessons_metadata_for_rows(table, [0])
    assert isinstance(m2, dict) and 0 in m2
    assert m2[0]["Stundenthema"] == "Updated Thema"


def test_index_snapshot_v1_migration(tmp_path):
    root = tmp_path / "Unterricht"
    (root / "FachA" / "Einheiten").mkdir(parents=True)
    a1 = root / "FachA" / "Einheiten" / "stunde-a1.md"
    create_dummy_lesson(a1, "Migration Thema")

    repo = FileSystemLessonIndexRepository()
    repo.rebuild_index(root)
    snapshot_v2 = repo.export_index_snapshot()
    assert snapshot_v2.get("version") == FileSystemLessonIndexRepository.INDEX_FORMAT_VERSION

    # simulate an older v1 snapshot with `mtime` instead of `mtime_ns`
    folder_key = str((root / "FachA" / "Einheiten").resolve()).lower()
    file_key = str(a1.resolve()).lower()
    snapshot_v1 = {
        "version": 1,
        "cache": {
            folder_key: {
                file_key: {
                    "path": str(a1.resolve()),
                    "mtime": int(a1.stat().st_mtime_ns),
                    "data": {
                        "Stundenthema": "Migration Thema",
                        "Oberthema": "",
                    },
                }
            }
        },
    }

    repo.invalidate_index()
    repo.import_index_snapshot(snapshot_v1)

    table = PlanTableData(
        markdown_path=root / "FachA" / "plan.md",
        headers=["datum", "inhalt"],
        rows=[["2026-03-01", "[[stunde-a1]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )
    m = repo.load_lessons_metadata_for_rows(table, [0])
    assert m[0]["Stundenthema"] == "Migration Thema"
    assert m[0]["index_version"] == FileSystemLessonIndexRepository.INDEX_FORMAT_VERSION


def test_index_rebuild_and_concurrent_access(tmp_path):
    root = tmp_path / "Unterricht"
    (root / "FachA" / "Einheiten").mkdir(parents=True)
    for i in range(1, 6):
        create_dummy_lesson(root / "FachA" / "Einheiten" / f"stunde-{i}.md", f"Thema {i}")

    table = PlanTableData(
        markdown_path=root / "FachA" / "plan.md",
        headers=["datum", "inhalt"],
        rows=[[f"2026-03-0{i}", f"[[stunde-{i}]]"] for i in range(1, 6)],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )

    repo = FileSystemLessonIndexRepository()
    repo.rebuild_index(root)

    def _worker(_: int) -> int:
        metadata = repo.load_lessons_metadata_for_all_rows(table)
        # concurrent invalidation/rebuild to simulate racey maintenance operations
        repo.invalidate_index(unterricht_dir=root)
        repo.rebuild_index(root)
        return len(metadata)

    with ThreadPoolExecutor(max_workers=4) as executor:
        counts = list(executor.map(_worker, range(10)))

    assert all(count >= 1 for count in counts)
    final_metadata = repo.load_lessons_metadata_for_all_rows(table)
    assert len(final_metadata) >= 1


def test_index_logs_rebuild_and_invalidate(tmp_path, caplog):
    root = tmp_path / "Unterricht"
    (root / "FachA" / "Einheiten").mkdir(parents=True)
    create_dummy_lesson(root / "FachA" / "Einheiten" / "stunde-a1.md", "Thema A1")

    repo = FileSystemLessonIndexRepository()

    logger_name = "kursplaner.infrastructure.repositories.lesson_index_repository"
    caplog.set_level(logging.INFO, logger=logger_name)

    repo.rebuild_index(root)
    repo.invalidate_index(unterricht_dir=root)

    rebuild_logs = [rec for rec in caplog.records if rec.message == "lesson_index.rebuild completed"]
    invalidate_logs = [rec for rec in caplog.records if rec.message == "lesson_index.invalidate completed"]

    assert rebuild_logs
    assert invalidate_logs

    rebuild = rebuild_logs[-1]
    invalidate = invalidate_logs[-1]

    assert int(getattr(rebuild, "scanned_files", 0)) >= 1
    assert float(getattr(rebuild, "duration_ms", 0.0)) >= 0.0
    assert str(getattr(invalidate, "scope", "")).startswith("unterricht_dir=")
    assert ":\\" not in str(getattr(rebuild, "unterricht_dir", ""))
    assert ":\\" not in str(getattr(invalidate, "scope", ""))
    assert int(getattr(invalidate, "removed_folders", 0)) >= 1


def test_index_snapshot_serializes_paths_workspace_relative(tmp_path):
    root = tmp_path / "Unterricht"
    (root / "FachA" / "Einheiten").mkdir(parents=True)
    lesson_path = root / "FachA" / "Einheiten" / "stunde-a1.md"
    create_dummy_lesson(lesson_path, "Thema A1")

    repo = FileSystemLessonIndexRepository()
    repo.rebuild_index(root)

    snapshot = repo.export_index_snapshot()
    assert snapshot.get("version") == FileSystemLessonIndexRepository.INDEX_FORMAT_VERSION

    cache = snapshot.get("cache", {})
    for _, entries in cache.items():
        for _, item in entries.items():
            path_text = str(item.get("path", ""))
            assert path_text
            assert ":\\" not in path_text
            assert not path_text.startswith("\\")
