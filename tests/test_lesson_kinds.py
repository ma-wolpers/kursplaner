"""Terminart einer Tagesspalte: eine Rangfolge (`DayColumn.lesson_type`), eine Schlüsselmenge (synthetisch)."""

from __future__ import annotations

from kursplaner.adapters.gui.lesson_kind_tints import LESSON_KIND_TINTS
from kursplaner.core.domain import lesson_kinds
from kursplaner.core.domain.lesson_yaml_policy import LESSON_TYPE_VALUES
from kursplaner.core.domain.sequence_ladder_homes import RungKind
from kursplaner.core.usecases.column_visibility_projection_usecase import ColumnVisibilityProjectionUseCase
from kursplaner.core.usecases.row_display_mode_usecase import RowDisplayModeUseCase
from tests.day_column_factory import make_day_column


def test_kind_keys_are_the_lowercased_lesson_types_and_shared_by_all_consumers():
    kinds = {
        lesson_kinds.KIND_UNTERRICHT,
        lesson_kinds.KIND_LZK,
        lesson_kinds.KIND_AUSFALL,
        lesson_kinds.KIND_HOSPITATION,
    }
    assert kinds == {value.lower() for value in LESSON_TYPE_VALUES}
    modes = RowDisplayModeUseCase
    assert {modes.MODE_UNTERRICHT, modes.MODE_LZK, modes.MODE_AUSFALL, modes.MODE_HOSPITATION} == kinds
    visibility = ColumnVisibilityProjectionUseCase
    assert {
        visibility.KIND_UNTERRICHT,
        visibility.KIND_LZK,
        visibility.KIND_AUSFALL,
        visibility.KIND_HOSPITATION,
    } == kinds
    assert set(LESSON_KIND_TINTS) == kinds - {lesson_kinds.KIND_UNTERRICHT}
    assert {kind.value for kind in RungKind} - {RungKind.OFFEN.value} == kinds


def test_cancel_marker_wins_over_hospitation_marker():
    day = make_day_column(thema_ausfall="X Krank", inhalt="HO Grund")
    assert day.lesson_type() == "Ausfall" and day.lesson_kind() == "ausfall"


def test_hospitation_marker_and_plain_column():
    assert make_day_column(inhalt="HO Grund").lesson_type() == "Hospitation"
    assert make_day_column().lesson_type() == "Unterricht"


def test_consumers_read_the_one_rule():
    day = make_day_column(thema_ausfall="X Krank")
    assert RowDisplayModeUseCase.infer_day_mode(day) == lesson_kinds.KIND_AUSFALL
