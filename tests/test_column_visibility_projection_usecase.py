from pathlib import Path

from kursplaner.core.usecases.column_visibility_projection_usecase import (
    ColumnVisibilityProjectionUseCase,
    ColumnVisibilitySettings,
)
from tests.day_column_factory import make_day_column


def _linked_day(tmp_path: Path, *, stundentyp: str, inhalt: str):
    """Baut eine Zeile mit echtem Link auf eine Stunden-Datei mit gegebenem Stundentyp.

    `DayColumn.is_lzk()`/`is_hospitation()` sind ausschließlich aus einem
    gültigen, existierenden Link ableitbar (siehe `is_valid_unterricht_file`) -
    ein direkt injiziertes `is_lzk`-Flag ohne echten Link wäre ein Zustand, der
    in der Produktion nie vorkommen kann.
    """
    lesson_dir = tmp_path / "Einheiten"
    lesson_dir.mkdir(exist_ok=True)
    lesson_path = lesson_dir / f"{stundentyp.lower()}.md"
    lesson_path.write_text(f"---\nStundentyp: {stundentyp}\n---\n", encoding="utf-8")
    return make_day_column(inhalt=inhalt, link=lesson_path, yaml={"Stundentyp": stundentyp})


def _day(
    *,
    inhalt: str = "",
    is_cancel: bool = False,
    plan_oberthema: str = "",
):
    if is_cancel:
        thema_ausfall = "X Ausfall"
    elif plan_oberthema:
        thema_ausfall = f"[[{plan_oberthema}]]"
    else:
        thema_ausfall = ""

    return make_day_column(inhalt=inhalt, thema_ausfall=thema_ausfall)


def test_projection_hides_selected_kinds(tmp_path):
    usecase = ColumnVisibilityProjectionUseCase()
    result = usecase.project(
        day_columns=[
            _day(inhalt="[[U1]]"),
            _day(is_cancel=True, inhalt="Ausfall"),
            _linked_day(tmp_path, stundentyp="LZK", inhalt="[[LZK 1]]"),
            _linked_day(tmp_path, stundentyp="Hospitation", inhalt="Hospitation"),
        ],
        settings=ColumnVisibilitySettings(
            hide_unterricht=False,
            hide_ausfall=True,
            hide_lzk=True,
            hide_hospitation=False,
            hide_leer=False,
        ),
    )

    assert len(result.visible_day_columns) == 2
    assert result.visible_day_columns[0].is_cancel() is False
    assert result.visible_day_columns[1].is_hospitation() is True


def test_projection_attaches_hidden_markers_before_next_visible_column(tmp_path):
    usecase = ColumnVisibilityProjectionUseCase()
    result = usecase.project(
        day_columns=[
            _day(inhalt="[[U1]]"),
            _day(is_cancel=True, inhalt="Ausfall"),
            _linked_day(tmp_path, stundentyp="LZK", inhalt="[[LZK 1]]"),
            _day(inhalt="[[U2]]"),
        ],
        settings=ColumnVisibilitySettings(
            hide_ausfall=True,
            hide_lzk=True,
            hint_ausfall=True,
            hint_lzk=True,
        ),
    )

    assert len(result.visible_day_columns) == 2
    first_hidden = result.visible_day_columns[0].hidden_kinds_before
    second_hidden = result.visible_day_columns[1].hidden_kinds_before
    assert isinstance(first_hidden, tuple)
    assert isinstance(second_hidden, tuple)
    assert first_hidden == ()
    assert second_hidden == ("ausfall", "lzk")


def test_projection_detects_empty_columns_as_kind_leer():
    usecase = ColumnVisibilityProjectionUseCase()
    result = usecase.project(
        day_columns=[_day(inhalt=""), _day(inhalt="[[U2]]")],
        settings=ColumnVisibilitySettings(hide_leer=True),
    )

    assert len(result.visible_day_columns) == 1
    assert result.visible_day_columns[0].inhalt == "[[U2]]"
