"""Wiki-Links werden kursplanerweit nur über `core/domain/wiki_links.py` erkannt (SSOT, synthetisch).

Die Tests prüfen die früher eigenständigen Erkennungen an ihren Aufrufstellen und einen
Architektur-Wächter: kein Modul außer `wiki_links.py` enthält eine eigene ``\\[\\[``-Regex.
"""

from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.content_markers import normalize_marker_text
from kursplaner.core.domain.expected_horizon_files import resolve_horizon_link
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.yaml_registry import _is_valid_lerngruppe, _yaml_scalar_line
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase
from kursplaner.core.usecases.load_plan_detail_usecase import LoadPlanDetailUseCase
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_no_module_outside_wiki_links_defines_its_own_link_regex():
    offending = [
        str(path.relative_to(_REPO_ROOT))
        for path in (_REPO_ROOT / "kursplaner").rglob("*.py")
        if path.name != "wiki_links.py" and "\\[\\[" in path.read_text(encoding="utf-8")
    ]
    assert offending == []


def test_marker_text_shows_alias_or_target():
    assert normalize_marker_text("  [[ziel|Ausfall]]  wegen   [[Wandertag]] ") == "Ausfall wegen Wandertag"


def test_lerngruppe_link_must_be_one_link_without_alias():
    assert _is_valid_lerngruppe("[[li2]]")
    assert not _is_valid_lerngruppe("[[li2|Linie 2]]")
    assert not _is_valid_lerngruppe("[[li2|]]")
    assert not _is_valid_lerngruppe("li2")
    assert not _is_valid_lerngruppe("[[a]] [[b]]")


def test_yaml_quotes_whole_links_only():
    assert _yaml_scalar_line("Lerngruppe", "[[li2]]") == 'Lerngruppe: "[[li2]]"'
    assert _yaml_scalar_line("Thema", "Text [[li2]]") == "Thema: Text [[li2]]"


def test_plan_detail_link_label_prefers_alias():
    assert LoadPlanDetailUseCase._extract_markdown_link_target("x [[a|Anzeige]] y") == "Anzeige"
    assert LoadPlanDetailUseCase._extract_markdown_link_target("[[a]]") == "a"
    assert LoadPlanDetailUseCase._extract_markdown_link_target("kein Link") == ""


def test_horizon_link_ignores_alias_and_md_suffix(tmp_path: Path):
    assert resolve_horizon_link("[[KH 1.md|Horizont]]", course_dir=tmp_path, vault_root=None) == tmp_path / "KH 1.md"
    assert resolve_horizon_link("KH 2", course_dir=tmp_path, vault_root=None) == tmp_path / "KH 2.md"


def _table(inhalt: str) -> PlanTableData:
    return PlanTableData(
        markdown_path=Path("plan.md"),
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[["01-09-26", "2", inhalt]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=True,
        metadata={},
    )


def test_transfer_replaces_only_the_first_legacy_link():
    table = _table("Vorher [[alt|Alias]] und [[zweiter]]")
    LessonTransferUseCase(None, None).replace_or_append_first_link(table, 0, "neu")  # type: ignore[arg-type]
    assert table.rows[0][2] == 'Vorher `= link("neu", [[neu]].Stundenthema)` und [[zweiter]]'


def test_transfer_appends_when_there_is_no_link():
    table = _table("Nur Text")
    LessonTransferUseCase(None, None).replace_or_append_first_link(table, 0, "neu")  # type: ignore[arg-type]
    assert table.rows[0][2] == 'Nur Text `= link("neu", [[neu]].Stundenthema)`'


def test_restore_from_cancel_keeps_the_link_target_of_a_legacy_row():
    table = _table("Ausfall [[einheit|Bruchrechnung]]")
    PlanCommandsUseCase(None).restore_from_cancel(table, 0)  # type: ignore[arg-type]
    assert table.rows[0][2] == '`= link("einheit", [[einheit]].Stundenthema)`'
