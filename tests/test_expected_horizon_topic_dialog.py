"""Tests für den Oberthemen-Dialog des Kompetenzhorizonts (echter Tk-Root, off-screen)."""

from __future__ import annotations

from datetime import date

from kursplaner.adapters.gui.expected_horizon_topic_dialog import (
    ExpectedHorizonDialogResult,
    ExpectedHorizonTopicDialog,
    _option_label,
)
from kursplaner.core.domain.expected_horizon_pdf_layout import DEFAULT_FONT_SIZE, ExpectedHorizonPdfLayout
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
        assert dialog.result == ExpectedHorizonDialogResult(["A", "B"], None)
    finally:
        if dialog.winfo_exists():
            dialog.destroy()


def test_pdf_layout_defaults_to_current_size_and_validates_font_size(tk_root):
    dialog = ExpectedHorizonTopicDialog(tk_root, options=_options(), with_pdf_layout=True)
    try:
        assert dialog._pdf_layout() == ExpectedHorizonPdfLayout(with_task_column=False, font_size=DEFAULT_FONT_SIZE)

        dialog._font_size_var.set("abc")
        assert str(dialog._accept_button.cget("state")) == "disabled"
        dialog._font_size_var.set("99")
        assert str(dialog._accept_button.cget("state")) == "disabled"

        dialog._font_size_var.set("11,5")
        dialog._task_column_var.set(True)
        assert str(dialog._accept_button.cget("state")) == "normal"
        dialog._accept()
        assert dialog.result == ExpectedHorizonDialogResult(["B"], ExpectedHorizonPdfLayout(True, 11.5))
    finally:
        if dialog.winfo_exists():
            dialog.destroy()
