"""Tests für den GUI-Ablauf der KH-Exporte (Dialoge gefälscht, keine Fenster)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from kursplaner.adapters.gui import expected_horizon_export_flow as flow_module
from kursplaner.adapters.gui.expected_horizon_export_flow import ExpectedHorizonExportFlow


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
    state = SimpleNamespace(topics=["A"], save_path=str(tmp_path / "KH.md"), messages=[])
    monkeypatch.setattr(flow_module, "ask_expected_horizon_topics", lambda *_a, **_k: state.topics)
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
