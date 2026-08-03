"""Tests für build_sequence_stem und das neue Dateibenennungsschema der Sequenz-Dokumente.

Das neue Format ist ``<Gruppe> <Sequenzname>`` – ohne Halbjahr.  Der halfyear_token-Parameter
wird ignoriert, damit bestehende Aufrufer unverändert bleiben.
"""

from __future__ import annotations

import pytest

from kursplaner.core.domain.sequence_planning import build_sequence_stem


class TestBuildSequenceStemFormat:
    """Prüft, dass der Stem im neuen Format ``<Gruppe> <Sequenzname>`` erzeugt wird."""

    def test_standard_case_returns_gruppe_then_sequenz(self):
        """Normalfall: Gruppe voran, dann Sequenzname, kein Halbjahr."""
        result = build_sequence_stem(
            sequence_name="Kodierung",
            group_name="li2",
            halfyear_token="26-2",
        )
        assert result == "li2 Kodierung"

    def test_halfyear_token_is_ignored(self):
        """halfyear_token darf keinen Einfluss auf den Stem haben."""
        stem_a = build_sequence_stem(
            sequence_name="Analysis",
            group_name="GK blau-1",
            halfyear_token="25-1",
        )
        stem_b = build_sequence_stem(
            sequence_name="Analysis",
            group_name="GK blau-1",
            halfyear_token="26-2",
        )
        assert stem_a == stem_b == "GK blau-1 Analysis"

    def test_wiki_link_in_group_name_is_stripped(self):
        """Wiki-Link-Syntax ``[[li2]]`` in group_name wird automatisch entfernt."""
        result = build_sequence_stem(
            sequence_name="Lineare Funktionen",
            group_name="[[GK blau-1]]",
            halfyear_token="26-2",
        )
        assert result == "GK blau-1 Lineare Funktionen"

    def test_empty_group_name_falls_back_to_sanitize_default(self):
        """Leerer group_name: sanitize_hour_title liefert 'Neue Stunde' als Fallback."""
        result = build_sequence_stem(
            sequence_name="Kodierung",
            group_name="",
            halfyear_token="26-2",
        )
        assert result.endswith("Kodierung")
        assert "Neue Stunde" in result

    def test_empty_sequence_name_falls_back_to_sanitize_default(self):
        """Leerer sequence_name: sanitize_hour_title liefert 'Neue Stunde' als Fallback."""
        result = build_sequence_stem(
            sequence_name="",
            group_name="li2",
            halfyear_token="26-2",
        )
        assert result.startswith("li2")
        assert "Neue Stunde" in result

    def test_forbidden_filesystem_chars_are_removed(self):
        """Sonderzeichen die in Dateinamen verboten sind werden bereinigt."""
        result = build_sequence_stem(
            sequence_name='Ko:dierung "Test"',
            group_name="li2",
            halfyear_token="26-2",
        )
        assert ":" not in result
        assert '"' not in result
        assert "li2" in result

    def test_group_then_sequence_order(self):
        """Gruppe steht immer vor dem Sequenznamen."""
        result = build_sequence_stem(
            sequence_name="Ableitungen",
            group_name="rot-3",
            halfyear_token="26-2",
        )
        gruppe_pos = result.index("rot-3")
        seq_pos = result.index("Ableitungen")
        assert gruppe_pos < seq_pos


class TestEnsureSequenceDocumentUsesNewStem:
    """Integrationstests: ensure_sequence_document legt Datei mit neuem Stem an."""

    def test_sequence_file_stem_is_gruppe_sequenzname(self, tmp_path):
        """Die erzeugte Sequenzdatei hat den Stem 'Gruppe Sequenzname'."""
        from kursplaner.core.domain.plan_table import PlanTableData
        from kursplaner.infrastructure.repositories.sequence_plan_repository import (
            FileSystemSequencePlanRepository,
        )

        plan_dir = tmp_path / "Unterricht" / "M li2 26-2"
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_path = plan_dir / "M li2 26-2.md"
        plan_path.write_text("# Kursplan\n", encoding="utf-8")

        table = PlanTableData(
            markdown_path=plan_path,
            headers=["Datum", "Stunden", "Inhalt"],
            rows=[["10-03-26", "2", "[[abc123]]"]],
            start_line=0,
            end_line=0,
            source_lines=[],
            had_trailing_newline=True,
            metadata={"Lerngruppe": "[[li2]]"},
        )

        repo = FileSystemSequencePlanRepository()
        sequence_path = repo.ensure_sequence_document(table=table, sequence_name="Kodierung")

        assert sequence_path.stem == "li2 Kodierung"
        assert sequence_path.parent.name == "Sequenzen"

    def test_sequence_file_stem_with_plain_group_name(self, tmp_path):
        """Gruppenname ohne Wiki-Link-Syntax wird korrekt verarbeitet."""
        from kursplaner.core.domain.plan_table import PlanTableData
        from kursplaner.infrastructure.repositories.sequence_plan_repository import (
            FileSystemSequencePlanRepository,
        )

        plan_dir = tmp_path / "Unterricht" / "M gruen-6 26-2"
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_path = plan_dir / "M gruen-6 26-2.md"
        plan_path.write_text("# Kursplan\n", encoding="utf-8")

        table = PlanTableData(
            markdown_path=plan_path,
            headers=["Datum", "Stunden", "Inhalt"],
            rows=[["10-03-26", "2", "[[abc123]]"]],
            start_line=0,
            end_line=0,
            source_lines=[],
            had_trailing_newline=True,
            metadata={"Lerngruppe": "gruen-6"},
        )

        repo = FileSystemSequencePlanRepository()
        sequence_path = repo.ensure_sequence_document(
            table=table, sequence_name="Lineare Funktionen"
        )

        assert sequence_path.stem == "gruen-6 Lineare Funktionen"
