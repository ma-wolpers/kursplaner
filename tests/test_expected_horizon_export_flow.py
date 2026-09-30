"""Tests für den GUI-Ablauf der KH-Exporte (Dialoge gefälscht, keine Fenster)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from kursplaner.adapters.gui import expected_horizon_export_flow as flow_module
from kursplaner.adapters.gui.expected_horizon_export_flow import ExpectedHorizonExportFlow
from kursplaner.adapters.gui.expected_horizon_topic_dialog import ExpectedHorizonDialogResult
from kursplaner.core.domain.expected_horizon_pdf_layout import ExpectedHorizonPdfLayout


class _Var:
    def get(self):
        return "light"


class _Recorder:
    def __init__(self, result=None):
        self.calls: list[dict] = []
        self.result = result

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


@pytest.fixture
def dialogs(monkeypatch, tmp_path):
    """Ersetzt Themen-, Speichern- und Meldungsdialoge durch steuerbare Fakes."""
    state = SimpleNamespace(topics=["A"], layout=None, save_path=str(tmp_path / "KH.md"), messages=[], dialog_kwargs=[])

    def _ask(*_args, **kwargs):
        state.dialog_kwargs.append(kwargs)
        return None if state.topics is None else ExpectedHorizonDialogResult(state.topics, state.layout)

    monkeypatch.setattr(flow_module, "ask_expected_horizon_topics", _ask)
    monkeypatch.setattr(flow_module.filedialog, "asksaveasfilename", lambda **_k: state.save_path)
    for name in ("showinfo", "showwarning", "showerror"):
        monkeypatch.setattr(
            flow_module.messagebox, name, lambda title, text, parent=None, n=name: state.messages.append((n, text))
        )
    return state


def _app(tmp_path: Path):
    visible = SimpleNamespace(row_index=0)
    hidden = SimpleNamespace(row_index=1)
    table = SimpleNamespace(markdown_path=tmp_path / "Kurs.md")
    return SimpleNamespace(
        current_table=table,
        day_columns=[visible],
        raw_day_columns=[visible, hidden],
        theme_var=_Var(),
    )


class _LzkUseCase:
    def __init__(self, tmp_path: Path):
        self.proposal = SimpleNamespace(
            options=SimpleNamespace(), default_markdown_path=lambda selection, now: tmp_path / "Default.md"
        )
        self.build_calls: list[dict] = []
        self.execute_calls: list[dict] = []

    def build_proposal(self, **kwargs):
        self.build_calls.append(kwargs)
        return self.proposal

    def execute(self, **kwargs):
        self.execute_calls.append(kwargs)
        return SimpleNamespace(
            markdown_path=kwargs["markdown_path"],
            pdf_path=kwargs["markdown_path"].with_suffix(".pdf"),
            oberthemen=("A",),
            row_count=1,
            removed_unavailable=(),
            link_written=True,
        )


def _flow(app, lzk):
    return ExpectedHorizonExportFlow(
        app,
        lzk_usecase=lzk,
        markdown_usecase=None,
        pdf_usecase=None,
        topic_query=None,
        run_tracked_write=lambda *, label, action, extra_before, extra_after: action(),
        refresh_after_write=lambda **_kwargs: None,
    )


def test_lzk_export_passes_raw_day_columns_including_hidden_ones(tmp_path, dialogs):
    app = _app(tmp_path)
    lzk = _LzkUseCase(tmp_path)

    _flow(app, lzk).export_lzk(anchor_row_index=1, selected_index=0)

    assert lzk.build_calls[0]["raw_day_columns"] == app.raw_day_columns
    assert lzk.build_calls[0]["anchor_row_index"] == 1
    call = lzk.execute_calls[0]
    assert call["raw_day_columns"] == app.raw_day_columns
    assert call["selection"] == ["A"]
    assert call["markdown_path"] == Path(dialogs.save_path).resolve()
    assert dialogs.messages[-1][0] == "showinfo"


def test_lzk_export_asks_pdf_layout_and_passes_it_on(tmp_path, dialogs):
    app = _app(tmp_path)
    lzk = _LzkUseCase(tmp_path)
    dialogs.layout = ExpectedHorizonPdfLayout(with_task_column=True, font_size=11)

    _flow(app, lzk).export_lzk(anchor_row_index=1, selected_index=0)

    assert dialogs.dialog_kwargs[0]["with_pdf_layout"] is True
    assert lzk.execute_calls[0]["pdf_layout"] == dialogs.layout


class _AdhocUseCase:
    def __init__(self):
        self.execute_calls: list[dict] = []

    def default_adhoc_output_path(self, table, **_kwargs):
        return table.markdown_path.parent / "KH.pdf"

    def execute(self, **kwargs):
        self.execute_calls.append(kwargs)
        return SimpleNamespace(output_path=kwargs["output_path"], oberthemen=("A",), row_count=1)


def _adhoc_flow(app, usecase):
    query = SimpleNamespace(query=lambda **_k: SimpleNamespace(ordered_selection=lambda sel: tuple(sel), cutoff=None))
    return ExpectedHorizonExportFlow(
        app,
        lzk_usecase=None,
        markdown_usecase=usecase,
        pdf_usecase=usecase,
        topic_query=query,
        run_tracked_write=lambda **_k: None,
        refresh_after_write=lambda **_k: None,
    )


@pytest.mark.parametrize(("output_format", "expects_layout"), [("pdf", True), ("markdown", False)])
def test_adhoc_export_asks_pdf_layout_only_for_pdf(tmp_path, dialogs, output_format, expects_layout):
    usecase = _AdhocUseCase()
    dialogs.layout = ExpectedHorizonPdfLayout(font_size=8) if expects_layout else None

    _adhoc_flow(_app(tmp_path), usecase).export_adhoc(anchor_row_index=1, output_format=output_format)

    assert dialogs.dialog_kwargs[0]["with_pdf_layout"] is expects_layout
    assert usecase.execute_calls[0]["layout"] == dialogs.layout


def test_cancelling_topic_dialog_aborts_export(tmp_path, dialogs):
    app = _app(tmp_path)
    lzk = _LzkUseCase(tmp_path)
    dialogs.topics = None

    _flow(app, lzk).export_lzk(anchor_row_index=1, selected_index=0)

    assert lzk.execute_calls == []


def test_cancelling_save_dialog_aborts_export(tmp_path, dialogs):
    app = _app(tmp_path)
    lzk = _LzkUseCase(tmp_path)
    dialogs.save_path = ""

    _flow(app, lzk).export_lzk(anchor_row_index=1, selected_index=0)

    assert lzk.execute_calls == []


def test_proposal_error_is_shown_and_nothing_is_written(tmp_path, dialogs):
    app = _app(tmp_path)
    lzk = _LzkUseCase(tmp_path)

    def _fail(**_kwargs):
        raise RuntimeError("Die ausgewählte Spalte ist keine LZK.")

    lzk.build_proposal = _fail

    _flow(app, lzk).export_lzk(anchor_row_index=1, selected_index=0)

    assert dialogs.messages == [("showerror", "Die ausgewählte Spalte ist keine LZK.")]
    assert lzk.execute_calls == []
