from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.export_expected_horizon_usecase import ExportExpectedHorizonUseCase
from kursplaner.infrastructure.export.expected_horizon_markdown_renderer import ExpectedHorizonMarkdownRenderer


def _table() -> PlanTableData:
    return PlanTableData(
        markdown_path=Path("A:/7thCloud/Unterricht/INF lila-5 25-2/INF lila-5 25-2.md"),
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[],
        start_line=1,
        end_line=1,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Kursfach": "Informatik", "Lerngruppe": "[[lila-5]]", "Stufe": "5"},
    )


def _day(*, row_index: int, datum: str, kind: str, obert: str, ziel: str, teilziele: list[str]):
    return {
        "row_index": row_index,
        "datum": datum,
        "stunden": "1",
        "Stundentyp": kind,
        "yaml": {
            "Stundentyp": kind,
            "Oberthema": obert,
            "Stundenziel": ziel,
            "Teilziele": teilziele,
        },
        "link": Path(f"A:/7thCloud/unit-{row_index}.md"),
        "is_cancel": False,
    }


def test_expected_horizon_markdown_uses_swapped_headings_and_bold_main_goals(tmp_path: Path):
    output = tmp_path / "Kompetenzhorizont.md"
    usecase = ExportExpectedHorizonUseCase(renderer=ExpectedHorizonMarkdownRenderer())

    day_columns = [
        _day(
            row_index=0,
            datum="01-09-25",
            kind="Unterricht",
            obert="Algorithmen",
            ziel="I 1.1 Sortierverfahren vergleichen",
            teilziele=["I 2.3: Bubble Sort erklären"],
        )
    ]

    usecase.execute(
        table=_table(),
        day_columns=day_columns,
        selected_day_index=0,
        output_path=output,
        export_date=date(2026, 4, 2),
    )

    text = output.read_text(encoding="utf-8")

    assert text.startswith("# Kompetenzhorizont: Algorithmen")
    assert "Informatik lila-5 2025/26 Hj. 2" in text
    assert "Exportdatum:" not in text
    assert "| Datum | Die SuS können ... | AFB | Aufg | Pkte |" in text
    assert "| **01.09.25** | **... Sortierverfahren vergleichen** |  |  |  |" in text
    assert "|  | ... Bubble Sort erklären |  |  |  |" in text


def test_markdown_renderer_merges_existing_scores_and_marks_removed_rows(tmp_path: Path) -> None:
    output_path = tmp_path / "KH.md"
    output_path.write_text(
        "\n".join(
            [
                "# Kompetenzhorizont: Algorithmen",
                "",
                "Informatik lila-5 2025/26 Hj. 2",
                "",
                "| Datum | Die SuS können ... | AFB | Aufg | Pkte |",
                "| --- | --- | --- | --- | --- |",
                "| **01.09.25** | **... Sortierverfahren vergleichen** | II | 1a | 2 |",
                "|  | ... Bubble Sort erklären | I | 1b | 1 |",
            ]
        ),
        encoding="utf-8",
    )

    usecase = ExportExpectedHorizonUseCase(renderer=ExpectedHorizonMarkdownRenderer())
    day_columns = [
        _day(
            row_index=0,
            datum="01-09-25",
            kind="Unterricht",
            obert="Algorithmen",
            ziel="I 1.1 Sortierverfahren vergleichen",
            teilziele=[],
        )
    ]

    usecase.execute(
        table=_table(),
        day_columns=day_columns,
        selected_day_index=0,
        output_path=output_path,
        export_date=date(2026, 4, 2),
    )

    content = output_path.read_text(encoding="utf-8")
    assert "| **01.09.25** | **... Sortierverfahren vergleichen** | II | 1a | 2 |" in content
    assert "|  | ~~... Bubble Sort erklären~~ | I | 1b | 1 |" in content


def test_markdown_renderer_merge_is_idempotent_on_repeated_export(tmp_path: Path) -> None:
    output_path = tmp_path / "KH.md"
    output_path.write_text(
        "\n".join(
            [
                "# Kompetenzhorizont: Algorithmen",
                "",
                "Informatik lila-5 2025/26 Hj. 2",
                "",
                "| Datum | Die SuS können ... | AFB | Aufg | Pkte |",
                "| --- | --- | --- | --- | --- |",
                "| **01.09.25** | **... Sortierverfahren vergleichen** | II | 1a | 2 |",
                "|  | ... Bubble Sort erklären | I | 1b | 1 |",
            ]
        ),
        encoding="utf-8",
    )

    usecase = ExportExpectedHorizonUseCase(renderer=ExpectedHorizonMarkdownRenderer())
    day_columns = [
        _day(
            row_index=0,
            datum="01-09-25",
            kind="Unterricht",
            obert="Algorithmen",
            ziel="I 1.1 Sortierverfahren vergleichen",
            teilziele=[],
        )
    ]

    usecase.execute(
        table=_table(),
        day_columns=day_columns,
        selected_day_index=0,
        output_path=output_path,
        export_date=date(2026, 4, 2),
    )
    first = output_path.read_text(encoding="utf-8")

    usecase.execute(
        table=_table(),
        day_columns=day_columns,
        selected_day_index=0,
        output_path=output_path,
        export_date=date(2026, 4, 2),
    )
    second = output_path.read_text(encoding="utf-8")

    assert first == second
    assert second.count("~~... Bubble Sort erklären~~") == 1


def test_markdown_renderer_merges_colliding_goal_texts_by_date_and_goal_key(tmp_path: Path) -> None:
    output_path = tmp_path / "KH.md"
    output_path.write_text(
        "\n".join(
            [
                "# Kompetenzhorizont: Algorithmen",
                "",
                "Informatik lila-5 2025/26 Hj. 2",
                "",
                "| Datum | Die SuS können ... | AFB | Aufg | Pkte |",
                "| --- | --- | --- | --- | --- |",
                "| **01.09.25** | **... Modellieren anwenden** | I | 1a | 2 |",
                "| **08.09.25** | **... Modellieren anwenden** | III | 2c | 4 |",
            ]
        ),
        encoding="utf-8",
    )

    usecase = ExportExpectedHorizonUseCase(renderer=ExpectedHorizonMarkdownRenderer())
    day_columns = [
        _day(
            row_index=0,
            datum="01-09-25",
            kind="Unterricht",
            obert="Algorithmen",
            ziel="I 1.1 Modellieren anwenden",
            teilziele=[],
        ),
        _day(
            row_index=1,
            datum="08-09-25",
            kind="Unterricht",
            obert="Algorithmen",
            ziel="I 1.2 Modellieren anwenden",
            teilziele=[],
        ),
    ]

    usecase.execute(
        table=_table(),
        day_columns=day_columns,
        selected_day_index=0,
        output_path=output_path,
        export_date=date(2026, 4, 2),
    )

    content = output_path.read_text(encoding="utf-8")
    assert "| **01.09.25** | **... Modellieren anwenden** | I | 1a | 2 |" in content
    assert "| **08.09.25** | **... Modellieren anwenden** | III | 2c | 4 |" in content


def test_markdown_renderer_keeps_old_rows_order_and_inserts_new_rows_above_anchor(tmp_path: Path) -> None:
    output_path = tmp_path / "KH.md"
    output_path.write_text(
        "\n".join(
            [
                "# Kompetenzhorizont: Algorithmen",
                "",
                "Informatik lila-5 2025/26 Hj. 2",
                "",
                "| Datum | Die SuS können ... | AFB | Aufg | Pkte |",
                "| --- | --- | --- | --- | --- |",
                "| **01.09.25** | **... Ziel A** | I | 1a | 2 |",
                "| **08.09.25** | **... Ziel C** | II | 2a | 3 |",
            ]
        ),
        encoding="utf-8",
    )

    usecase = ExportExpectedHorizonUseCase(renderer=ExpectedHorizonMarkdownRenderer())
    day_columns = [
        _day(
            row_index=0,
            datum="01-09-25",
            kind="Unterricht",
            obert="Algorithmen",
            ziel="Ziel A",
            teilziele=[],
        ),
        _day(
            row_index=1,
            datum="05-09-25",
            kind="Unterricht",
            obert="Algorithmen",
            ziel="Ziel B",
            teilziele=[],
        ),
        _day(
            row_index=2,
            datum="08-09-25",
            kind="Unterricht",
            obert="Algorithmen",
            ziel="Ziel C",
            teilziele=[],
        ),
    ]

    usecase.execute(
        table=_table(),
        day_columns=day_columns,
        selected_day_index=0,
        output_path=output_path,
        export_date=date(2026, 4, 2),
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()
    row_a = "| **01.09.25** | **... Ziel A** | I | 1a | 2 |"
    row_b = "| **05.09.25** | **... Ziel B** |  |  |  |"
    row_c = "| **08.09.25** | **... Ziel C** | II | 2a | 3 |"
    index_a = lines.index(row_a)
    index_b = lines.index(row_b)
    index_c = lines.index(row_c)

    assert index_a < index_b < index_c
