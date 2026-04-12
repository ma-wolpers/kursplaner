from kursplaner.core.domain.unterrichtsbesuch_policy import UB_OVERVIEW_FILE_NAME
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository


def test_ub_repository_creates_expected_root(tmp_path):
    repo = FileSystemUbRepository()
    root = repo.ensure_ub_root(tmp_path)

    assert root.exists()
    assert root.is_dir()
    assert root.name == "02 UBs"
    assert root.parent.name == "00 Orga"


def test_ub_repository_unique_path_adds_suffix(tmp_path):
    repo = FileSystemUbRepository()
    first = repo.unique_ub_markdown_path(tmp_path, "UB 26-03-31 Test")
    first.parent.mkdir(parents=True, exist_ok=True)
    first.write_text("x", encoding="utf-8")

    second = repo.unique_ub_markdown_path(tmp_path, "UB 26-03-31 Test")
    assert second.name == "UB 26-03-31 Test 2.md"


def test_ub_repository_save_and_load_roundtrip(tmp_path):
    repo = FileSystemUbRepository()
    path = repo.unique_ub_markdown_path(tmp_path, "UB 26-03-31 Funktionen")

    repo.save_ub_markdown(
        path,
        {
            "Bereich": ["Pädagogik", "Mathematik"],
            "Langentwurf": True,
            "Beobachtungsschwerpunkt": "Aktivierung",
            "Einheit": "[[gruen-6 03-31 Funktionen]]",
        },
        reflection_text="Reflexionstext",
        professional_steps=["Ich plane klarere Übergänge."],
        usable_resources=["Exit-Tickets"],
    )

    yaml_data, body = repo.load_ub_markdown(path)
    assert yaml_data["Einheit"] == "[[gruen-6 03-31 Funktionen]]"
    assert "Reflexionstext" in body
    assert "Professionalisierungsschritte" in body
    assert "Nutzbare Ressourcen" in body


def test_ub_repository_overview_io(tmp_path):
    repo = FileSystemUbRepository()
    target = repo.save_ub_overview(tmp_path, "# UB Übersicht")

    assert target.name == UB_OVERVIEW_FILE_NAME
    assert repo.load_ub_overview(tmp_path).startswith("# UB Übersicht")
