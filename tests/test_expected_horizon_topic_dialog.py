"""Tests für den Oberthemen-Dialog des Kompetenzhorizonts (echter Tk-Root, off-screen)."""

from __future__ import annotations

from datetime import date

from kursplaner.adapters.gui.expected_horizon_topic_dialog import ExpectedHorizonTopicDialog, _option_label
from kursplaner.core.domain.expected_horizon_cutoff import HorizonCutoff
from kursplaner.core.usecases.expected_horizon_topic_query_usecase import (
    ExpectedHorizonTopicOption,
    ExpectedHorizonTopicOptions,
)


def _options(*, unavailable: tuple[str, ...] = (), invalid: int = 0) -> ExpectedHorizonTopicOptions:
    return ExpectedHorizonTopicOptions(
        anchor_row_index=3,
        is_lzk_anchor=True,
        cutoff=HorizonCutoff.before(date(2026, 9, 10)),
        options=(
            ExpectedHorizonTopicOption("A", date(2026, 9, 1), date(2026, 9, 8), 2),
            ExpectedHorizonTopicOption("B", date(2026, 9, 3), date(2026, 9, 3), 1),
        ),
        preselected=("B",),
        stored=("B",) + unavailable,
        unavailable_stored=unavailable,
        invalid_unit_count=invalid,
    )


def test_option_label_shows_span_and_count():
    options = _options()

    assert _option_label(options.options[0]) == "A   (01.09. – 08.09.2026, 2 Stunden)"
    assert _option_label(options.options[1]) == "B   (03.09.2026, 1 Stunde)"


def test_dialog_preselects_and_requires_at_least_one_topic(tk_root):
    dialog = ExpectedHorizonTopicDialog(tk_root, options=_options(unavailable=("Alt",), invalid=1))
    try:
        assert dialog._selected() == ["B"]
        assert len(dialog._warnings()) == 2

        dialog._set_all(False)
        assert str(dialog._accept_button.cget("state")) == "disabled"
        dialog._accept()
        assert dialog.result is None

        dialog._set_all(True)
        assert str(dialog._accept_button.cget("state")) == "normal"
        dialog._accept()
        assert dialog.result == ["A", "B"]
    finally:
        if dialog.winfo_exists():
            dialog.destroy()
