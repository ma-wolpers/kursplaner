from kursplaner.core.usecases.column_visibility_projection_usecase import (
    ColumnVisibilityProjectionUseCase,
    ColumnVisibilitySettings,
)


def _day(*, inhalt: str = "", is_cancel: bool = False, is_lzk: bool = False, is_hospitation: bool = False):
    return {
        "inhalt": inhalt,
        "is_cancel": is_cancel,
        "is_lzk": is_lzk,
        "is_hospitation": is_hospitation,
        "link": None,
        "yaml": {},
    }


def test_projection_hides_selected_kinds():
    usecase = ColumnVisibilityProjectionUseCase()
    result = usecase.project(
        day_columns=[
            _day(inhalt="[[U1]]"),
            _day(is_cancel=True, inhalt="Ausfall"),
            _day(is_lzk=True, inhalt="[[LZK 1]]"),
            _day(is_hospitation=True, inhalt="Hospitation"),
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
    assert bool(result.visible_day_columns[0]["is_cancel"]) is False
    assert bool(result.visible_day_columns[1]["is_hospitation"]) is True


def test_projection_attaches_hidden_markers_before_next_visible_column():
    usecase = ColumnVisibilityProjectionUseCase()
    result = usecase.project(
        day_columns=[
            _day(inhalt="[[U1]]"),
            _day(is_cancel=True, inhalt="Ausfall"),
            _day(is_lzk=True, inhalt="[[LZK 1]]"),
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
    first_hidden = result.visible_day_columns[0].get("hidden_kinds_before")
    second_hidden = result.visible_day_columns[1].get("hidden_kinds_before")
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
    assert result.visible_day_columns[0]["inhalt"] == "[[U2]]"
