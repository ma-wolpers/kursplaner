from __future__ import annotations

from kursplaner.infrastructure.repositories.plan_table_file_repository import (
    load_last_plan_table,
    save_plan_table,
)


def _write_plan_file(path, preamble: str) -> None:
    path.write_text(
        preamble
        + "| Datum | Stunden | Inhalt | Thema/Ausfall |\n"
        "| --- | --- | --- | --- |\n"
        "| 10-03-26 | 2 | [[GK blau-1 0310 Einheit]] |  |\n",
        encoding="utf-8",
    )


def test_save_plan_table_preserves_content_added_externally_before_table(tmp_path):
    """Regression: externe Änderungen vor der Tabelle dürfen beim Speichern nicht verloren gehen.

    Szenario: Kursplaner lädt den Kurs (source_lines-Snapshot), der Nutzer
    bearbeitet dieselbe Datei danach extern (z.B. fügt Notizen vor der Tabelle
    ein), und speichert anschließend aus der App heraus eine Zelländerung.
    Der externe Zusatztext darf dabei nicht überschrieben werden.
    """
    plan_file = tmp_path / "M GK blau-1 26-1.md"
    frontmatter = '---\nLerngruppe: "[[GK blau-1]]"\nKursfach: "Mathematik"\nStufe: 11\n---\n\n'
    _write_plan_file(plan_file, frontmatter)

    table = load_last_plan_table(plan_file)

    # Externe Änderung *nach* dem Laden: Notiz vor die Tabelle geschrieben.
    _write_plan_file(plan_file, frontmatter + "WICHTIGE NOTIZ VOR DER TABELLE\n\n")

    # Zell-Edit aus der App (z.B. Oberthema setzen) auf dem *alten* In-Memory-table.
    table.rows[0][3] = "[[GK blau-1 Kodierung]]"
    save_plan_table(table)

    text = plan_file.read_text(encoding="utf-8")
    assert "WICHTIGE NOTIZ VOR DER TABELLE" in text
    assert "[[GK blau-1 Kodierung]]" in text


def test_save_plan_table_reuses_snapshot_when_file_unchanged(tmp_path):
    """Kein unnötiges Neu-Einlesen, wenn die Datei seit dem Laden unverändert ist."""
    plan_file = tmp_path / "M GK blau-1 26-1.md"
    frontmatter = '---\nLerngruppe: "[[GK blau-1]]"\nKursfach: "Mathematik"\nStufe: 11\n---\n\n'
    _write_plan_file(plan_file, frontmatter)

    table = load_last_plan_table(plan_file)
    original_source_lines = table.source_lines

    table.rows[0][3] = "[[GK blau-1 Kodierung]]"
    save_plan_table(table)

    assert table.source_lines is original_source_lines
    text = plan_file.read_text(encoding="utf-8")
    assert "[[GK blau-1 Kodierung]]" in text
