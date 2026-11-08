"""Übernahme-Leiste: Spaltenfrage nur bei Kompetenzen mit Inhalts- und Prozessbereich (ohne Tk).

Die Leiste wird per `object.__new__()` ohne Widgets gebaut; der Dialog
(`ask_mixed_side`) ist ersetzt, die Entscheidung kommt aus der Domain
(`sequence_ladder_import.mixed_side_ids`).
"""

from __future__ import annotations

from types import SimpleNamespace

from kompetenzgraph_test_support import make_bereich, make_node

from kursplaner.adapters.gui import kompetenzgraph_import_bar as bar_module
from kursplaner.adapters.gui.kompetenzgraph_import_bar import KompetenzGraphImportBar
from kursplaner.adapters.gui.sequence_ladder_board_mapping import LANES, side_title
from kursplaner.core.domain.course_kc_context import CourseKcContext
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.sequence_ladder import LadderSide

_SNAPSHOT = build_kompetenz_graph_snapshot(
    [
        make_node("Mat-ZA-1", primarer_bereich_id="I-Zahlen"),
        make_node("Mat-ZA-2", primarer_bereich_id="I-Zahlen", prozessbereich_ids=("P-Darstellen",)),
    ],
    [make_bereich("I-Zahlen", kind="inhaltsbereich"), make_bereich("P-Darstellen", kind="prozessbereich")],
)


def _bar(marked, imports):
    bar = object.__new__(KompetenzGraphImportBar)
    bar._snapshot, bar._frame = _SNAPSHOT, None
    bar._state = SimpleNamespace(marked_ids=set(marked))
    bar._target = SimpleNamespace(
        kc_context=CourseKcContext,
        import_ids=lambda ids, snapshot, side=None: imports.append((list(ids), side)),
    )
    return bar


def test_without_mixed_competences_nothing_is_asked(monkeypatch):
    monkeypatch.setattr(bar_module, "ask_mixed_side", lambda *a: (_ for _ in ()).throw(AssertionError("gefragt")))
    imports: list = []
    _bar({"Mat-ZA-1"}, imports).do_import()
    assert imports == [(["Mat-ZA-1"], None)]


def test_mixed_competences_ask_once_and_pass_the_choice(monkeypatch):
    asked: list = []

    def ask(_parent, mixed, total):
        asked.append((mixed, total))
        return LadderSide.PROZESS

    monkeypatch.setattr(bar_module, "ask_mixed_side", ask)
    imports: list = []
    _bar({"Mat-ZA-1", "Mat-ZA-2"}, imports).do_import()
    assert asked == [(1, 2)]
    assert imports == [(["Mat-ZA-1", "Mat-ZA-2"], LadderSide.PROZESS)]


def test_cancelling_the_column_question_imports_nothing(monkeypatch):
    monkeypatch.setattr(bar_module, "ask_mixed_side", lambda *a: None)
    imports: list = []
    _bar({"Mat-ZA-2"}, imports).do_import()
    assert imports == []


def test_column_titles_come_from_the_board_lanes():
    assert [side_title(side) for side in LadderSide] == [lane.title for lane in LANES[:2]]


def test_question_offers_both_columns_and_maps_the_answer(monkeypatch):
    seen = []

    class FakeChoice:
        def askchoice(self, title, message, options, *, parent=None):
            seen.append((message, [(o.key, o.label, o.description) for o in options]))
            return options[1].key

    monkeypatch.setattr(bar_module, "ChoiceDialogService", FakeChoice)
    assert bar_module.ask_mixed_side(None, 1, 3) is LadderSide.PROZESS
    message, options = seen[0]
    assert "1 der 3" in message and "übrigen" in message
    assert options == [
        (LadderSide.INHALT.value, side_title(LadderSide.INHALT), "Spalte 1"),
        (LadderSide.PROZESS.value, side_title(LadderSide.PROZESS), "Spalte 2"),
    ]
