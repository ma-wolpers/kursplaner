from __future__ import annotations

from datetime import date

import pytest

from kursplaner.core.domain.course_rhythm import WeekdayRhythm
from kursplaner.infrastructure.repositories.plan_repository import FileSystemPlanRepository


def test_update_plan_rhythm_preserves_table_when_rhythmus_is_last_frontmatter_field(tmp_path):
    """Regression: `Rhythmus` als letztes Frontmatter-Feld vor dem schliessenden `---`
    durfte den Rest der Datei (Tabelle, alles danach) nicht verschlucken.

    Bug: die Zeilen-Scan-Schleife brach beim schliessenden `---` sofort ab,
    bevor sie `end_idx` auf dessen Index setzen konnte, falls `Rhythmus` das
    letzte Feld war - `end_idx` blieb `None` und fiel auf `len(lines)`
    zurueck, wodurch `lines[end_idx:]` (schliessendes `---` + komplette
    Tabelle) beim Zusammenbau der neuen Datei wegfiel.
    """
    plan_file = tmp_path / "Inf gr3 26-2.md"
    plan_file.write_text(
        "---\n"
        'Lerngruppe: "[[gr3]]"\n'
        "Kursfach: Informatik\n"
        "Stufe: 8\n"
        "Rhythmus:\n"
        '  - "Fr 11:30 2"\n'
        "---\n\n"
        "| Datum | Inhalt | Thema/Ausfall |\n"
        "| --- | --- | --- |\n"
        "| 14-08-26 | [[abc]] |  |\n"
        "\n"
        "## Notizen\n"
        "\n"
        "Freitext-Abschnitt nach der Tabelle, der ebenfalls erhalten bleiben muss.\n",
        encoding="utf-8",
    )

    repo = FileSystemPlanRepository()
    new_rhythm = (
        WeekdayRhythm(weekday=0, start_time="11:30", hours=2),
        WeekdayRhythm(weekday=1, start_time="11:30", hours=2, valid_from=date(2026, 8, 15)),
    )
    repo.update_plan_rhythm(plan_file, new_rhythm)

    text = plan_file.read_text(encoding="utf-8")
    assert sum(1 for line in text.splitlines() if line.strip() == "---") == 2
    assert "| Datum | Inhalt | Thema/Ausfall |" in text
    assert "| 14-08-26 | [[abc]] |  |" in text
    assert "## Notizen" in text
    assert "Freitext-Abschnitt nach der Tabelle, der ebenfalls erhalten bleiben muss." in text
    assert '  - "Mo 11:30 2"' in text
    assert '  - "ab 15-08-26 Di 11:30 2"' in text


def test_update_plan_rhythm_preserves_fields_after_rhythmus(tmp_path):
    """Felder nach `Rhythmus` (z. B. `Kompetenzen`) bleiben unveraendert erhalten."""
    plan_file = tmp_path / "M GK blau-1 26-1.md"
    plan_file.write_text(
        "---\n"
        'Lerngruppe: "[[GK blau-1]]"\n'
        "Kursfach: Mathematik\n"
        "Stufe: 11\n"
        "Rhythmus:\n"
        '  - "Di 08:00 2"\n'
        "Kompetenzen:\n"
        '  - "Modellieren"\n'
        "---\n\n"
        "| Datum | Inhalt | Thema/Ausfall |\n"
        "| --- | --- | --- |\n"
        "| 10-03-26 | [[Einheit]] |  |\n",
        encoding="utf-8",
    )

    repo = FileSystemPlanRepository()
    repo.update_plan_rhythm(plan_file, (WeekdayRhythm(weekday=2, start_time="08:00", hours=2),))

    text = plan_file.read_text(encoding="utf-8")
    assert '  - "Mi 08:00 2"' in text
    assert 'Kompetenzen:' in text
    assert '  - "Modellieren"' in text
    assert "| 10-03-26 | [[Einheit]] |  |" in text


def test_update_plan_rhythm_raises_without_rhythmus_field(tmp_path):
    plan_file = tmp_path / "unmigrated.md"
    plan_file.write_text(
        "---\nLerngruppe: \"[[gr3]]\"\n---\n\n| Datum | Inhalt | Thema/Ausfall |\n",
        encoding="utf-8",
    )

    repo = FileSystemPlanRepository()
    with pytest.raises(RuntimeError, match="kein 'Rhythmus'-Feld"):
        repo.update_plan_rhythm(plan_file, (WeekdayRhythm(weekday=0, start_time="08:00", hours=2),))
