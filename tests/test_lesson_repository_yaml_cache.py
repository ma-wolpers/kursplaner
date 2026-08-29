"""Tests für den `(mtime_ns, size)`-gekeyten YAML-Cache in

`FileSystemLessonRepository` (Perf-Fix Item 1, 2026-08-29 — Ergänzung zum
Einzelzeilen-Patch für Fälle, die trotzdem einen vollen Neu-Einlesevorgang
brauchen, z. B. initiales Laden eines Plans).

Zentrale Invariante, die hier geprüft wird: der Cache ist ausschließlich eine
Performance-Optimierung, nie Quelle der Wahrheit — eine externe Änderung an
der Datei (mit einem anderen Programm, hier über `pathlib` simuliert) muss
beim nächsten Lesevorgang zuverlässig sichtbar werden, während eine
unveränderte Datei tatsächlich aus dem Cache bedient wird (bewiesen über
Objekt-Identität des zurückgegebenen `LessonYamlData`, kein Mock nötig).
"""

from __future__ import annotations

import time
from pathlib import Path

from kursplaner.core.domain.plan_table import LessonYamlData
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository


def _write_lesson(repo: FileSystemLessonRepository, path: Path, *, stundenthema: str) -> LessonYamlData:
    path.parent.mkdir(parents=True, exist_ok=True)
    lesson = LessonYamlData(
        lesson_path=path,
        data={
            "Stundentyp": "Unterricht",
            "Dauer": "2",
            "Stundenthema": stundenthema,
            "Oberthema": "",
            "Stundenziel": "",
            "Kompetenzen": [],
            "Material": [],
        },
    )
    repo.save_lesson_yaml(lesson)
    return lesson


def test_unchanged_file_is_served_from_cache(tmp_path):
    repo = FileSystemLessonRepository()
    path = tmp_path / "Einheiten" / "lesson_a.md"
    _write_lesson(repo, path, stundenthema="Thema A")

    first = repo.load_lesson_yaml(path)
    second = repo.load_lesson_yaml(path)

    assert first is second  # zweiter Aufruf kam aus dem Cache, kein erneutes Parsen
    assert second.data.get("Stundenthema") == "Thema A"


def test_externally_modified_file_is_detected_not_served_stale(tmp_path):
    """Simuliert: ein anderes Programm ändert die Datei, während Kursplaner offen ist."""
    repo = FileSystemLessonRepository()
    path = tmp_path / "Einheiten" / "lesson_a.md"
    _write_lesson(repo, path, stundenthema="Thema A")

    first = repo.load_lesson_yaml(path)
    assert first.data.get("Stundenthema") == "Thema A"

    # Externe Änderung -- NICHT über repo.save_lesson_yaml() (das würde den
    # Cache explizit invalidieren und damit den eigentlich zu prüfenden
    # Mechanismus -- die signaturbasierte Erkennung -- umgehen).
    time.sleep(0.01)  # manche Dateisysteme haben grobe mtime-Aufloesung
    path.write_text(
        '---\nStundentyp: "Unterricht"\nDauer: "2"\nStundenthema: "Extern geändert"\n'
        'Oberthema: ""\nStundenziel: ""\nKompetenzen: []\nMaterial: []\n---\n',
        encoding="utf-8",
    )

    second = repo.load_lesson_yaml(path)
    assert second.data.get("Stundenthema") == "Extern geändert"
    assert second is not first


def test_save_lesson_yaml_invalidates_cache_immediately(tmp_path):
    repo = FileSystemLessonRepository()
    path = tmp_path / "Einheiten" / "lesson_a.md"
    lesson = _write_lesson(repo, path, stundenthema="Thema A")

    first = repo.load_lesson_yaml(path)
    assert first.data.get("Stundenthema") == "Thema A"

    lesson.data["Stundenthema"] = "Über repo.save_lesson_yaml geändert"
    repo.save_lesson_yaml(lesson)

    second = repo.load_lesson_yaml(path)
    assert second.data.get("Stundenthema") == "Über repo.save_lesson_yaml geändert"


def test_load_lessons_for_rows_benefits_from_the_same_cache(tmp_path):
    """`load_lessons_for_rows()` dedupliziert bereits *innerhalb* eines Aufrufs

    nach Pfad; dieser Test prüft, dass es zusätzlich denselben Cache über
    mehrere Aufrufe hinweg nutzt (über `load_lesson_yaml`, nicht mehr die
    freie Funktion direkt).
    """
    from kursplaner.core.domain.plan_table import PlanTableData

    repo = FileSystemLessonRepository()
    plan_dir = tmp_path / "Mathe Kurs"
    plan_path = plan_dir / "Mathe Kurs.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("# Kursplan\n", encoding="utf-8")
    _write_lesson(repo, plan_dir / "Einheiten" / "lesson_a.md", stundenthema="Thema A")

    table = PlanTableData(
        markdown_path=plan_path,
        headers=["Datum", "Inhalt", "Thema/Ausfall"],
        rows=[["10-03-26", "[[lesson_a]]", ""]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=True,
        metadata={},
    )

    first = repo.load_lessons_for_rows(table, [0])
    second = repo.load_lessons_for_rows(table, [0])

    assert first[0] is second[0]
