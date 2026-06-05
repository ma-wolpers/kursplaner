from kursplaner.core.domain.file_relation_registry import CourseFileRelations, FileRelationRegistrySnapshot
from kursplaner.infrastructure.repositories.file_relation_registry_repository import (
    FileSystemFileRelationRegistryRepository,
)


def test_file_relation_registry_loads_empty_snapshot_when_missing(tmp_path):
    repo = FileSystemFileRelationRegistryRepository(registry_path=tmp_path / "config" / "relations.json")

    snapshot = repo.load_snapshot()

    assert snapshot.version == 1
    assert snapshot.courses == ()
    assert isinstance(snapshot.generated_at, str)


def test_file_relation_registry_roundtrip_persists_snapshot(tmp_path):
    registry_path = tmp_path / "config" / "relations.json"
    repo = FileSystemFileRelationRegistryRepository(registry_path=registry_path)

    plan_a = (tmp_path / "Unterricht" / "A" / "A.md").resolve()
    plan_b = (tmp_path / "Unterricht" / "B" / "B.md").resolve()
    lesson_path = (tmp_path / "Unterricht" / "A" / "Einheiten" / "A 01.md").resolve()
    ub_path = (tmp_path / "7thVault" / "UB" / "UB 26-03-10 A.md").resolve()
    sequence_path = (tmp_path / "Unterricht" / "A" / "Sequenzen" / "Seq A 26-2.md").resolve()

    snapshot = FileRelationRegistrySnapshot(
        version=1,
        generated_at="2026-05-01T10:00:00+00:00",
        courses=(
            CourseFileRelations(
                course_plan_path=plan_b,
                lesson_paths=(),
                ub_paths=(),
                sequence_paths=(),
            ),
            CourseFileRelations(
                course_plan_path=plan_a,
                lesson_paths=(lesson_path,),
                ub_paths=(ub_path,),
                sequence_paths=(sequence_path,),
            ),
        ),
    )

    repo.save_snapshot(snapshot)
    loaded = repo.load_snapshot()

    assert registry_path.exists()
    assert loaded.version == 1
    assert loaded.generated_at == "2026-05-01T10:00:00+00:00"
    assert len(loaded.courses) == 2
    assert loaded.courses[0].course_plan_path == plan_a
    assert loaded.courses[1].course_plan_path == plan_b
    assert loaded.courses[0].lesson_paths == (lesson_path,)
    assert loaded.courses[0].ub_paths == (ub_path,)
    assert loaded.courses[0].sequence_paths == (sequence_path,)
