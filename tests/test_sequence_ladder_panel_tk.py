"""Leiter-Oberfläche an einem echten Tk-Root (außerhalb des Bildschirms): Tasten → Aktionen.

Nur synthetische Daten in tmp_path. Tasten über `bw_gui.testing.keys.press_key` ohne OS-Fokus.
Undo/Redo und Escape bindet die Leiter nicht selbst (Hauptfenster-Bindungen).
"""

from __future__ import annotations

import pytest
from bw_gui.runtime import ui
from bw_gui.testing.keys import press_key
from bw_gui.widgets.card_board import BoardCell
from sequence_ladder_test_support import make_ladder_env
from test_sequence_ladder_controller import FakeDialogs

from kursplaner.adapters.gui.sequence_choices import SequenceChoice
from kursplaner.adapters.gui.sequence_ladder_board_mapping import LANE_IDEEN, LANE_INHALT, card_key, rung_key
from kursplaner.adapters.gui.sequence_ladder_controller import SequenceLadderController
from kursplaner.adapters.gui.sequence_ladder_keys import bind_ladder_keys
from kursplaner.adapters.gui.sequence_ladder_panel import SequenceLadderPanel
from kursplaner.core.domain.sequence_ladder import BlockRef, LadderSide

CTRL = 0x4


@pytest.fixture
def ladder(root, tmp_path):
    env = make_ladder_env(tmp_path)
    window = ui.Toplevel(root)
    window.geometry("1000x600+3000+3000")
    moved, chosen = [], []
    panel = SequenceLadderPanel(
        window,
        window,
        add_help=lambda *_a, **_kw: None,
        on_import_click=lambda: None,
        on_sequence_chosen=chosen.append,
        on_cursor_moved=moved.append,
    )
    panel.toolbar.pack(fill="x")
    panel.body.pack(fill="both", expand=True)
    dialogs = FakeDialogs()
    controller = SequenceLadderController(
        sequence_path=env.sequence_path,
        load=env.load,
        edit=env.edit,
        context=lambda: env.context,
        dialogs=dialogs,
        text_input=panel,
        render=panel.render,
        after_write=lambda _written: None,
    )
    panel.attach(controller)

    def move_cursor(cursor):
        controller.set_cursor(cursor)
        moved.append(cursor)

    bind_ladder_keys(panel.board, lambda: controller, move_cursor)
    controller.reload()
    window.update()
    panel.board.flush_now()
    yield panel, controller, dialogs, moved
    window.destroy()


def _type(panel, text):
    """Tippt *text* in den offenen Inline-Editor des Boards und übernimmt mit Enter."""
    field = panel.board.editor.field
    assert field is not None, "kein Inline-Editor offen"
    field.set(text)
    assert press_key(field.text, "Return") is True
    panel.board.flush_now()


def test_enter_on_empty_cell_adds_and_ctrl_up_moves_across_rungs(ladder):
    panel, controller, _dialogs, _moved = ladder
    key_widget = panel.board.key_widget
    assert press_key(key_widget, "Return") is True
    _type(panel, "A")
    assert [b.text for b in controller.ladder.rung(0).inhalt] == ["A"]
    assert press_key(key_widget, "Up", state=CTRL) is True
    assert [b.text for b in controller.ladder.rung(1).inhalt] == ["A"]
    panel.board.flush_now()
    assert panel.board.cursor == card_key(BlockRef(1, LadderSide.INHALT, "A"))


def test_delete_is_consumed_but_undo_goes_to_the_main_window(ladder):
    panel, controller, _dialogs, _moved = ladder
    key_widget = panel.board.key_widget
    press_key(key_widget, "Return")
    _type(panel, "A")
    assert press_key(key_widget, "Delete") is True
    assert controller.ladder.is_empty
    assert press_key(key_widget, "z", char="\x1a", state=CTRL) is False


def test_arrow_keys_take_the_one_cursor_path_and_are_handled_at_the_edge(ladder):
    panel, controller, _dialogs, moved = ladder
    key_widget = panel.board.key_widget
    assert press_key(key_widget, "Right") is True
    assert controller.cursor == panel.board.cursor and moved[-1] == panel.board.cursor
    for _ in range(5):
        assert press_key(key_widget, "Down") is True


def test_banner_appears_for_a_malformed_ladder(ladder):
    panel, controller, _dialogs, _moved = ladder
    path = controller.sequence_path
    path.write_text(
        path.read_text(encoding="utf-8").replace("## Export", "## Sequenzleiter\n\nkaputt\n\n## Export"),
        encoding="utf-8",
    )
    controller.reload()
    panel.body.update()
    assert panel._banner.label.winfo_manager() == "pack"
    assert "Zeile 1" in panel._banner.label.cget("text")
    assert controller.read_only


def test_choices_mirror_the_host_and_empty_state_hides_the_board(ladder, tmp_path):
    panel, _controller, _dialogs, _moved = ladder
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    panel.set_choices([SequenceChoice(a, "Brüche", "2 Einheiten"), SequenceChoice(b, "Prozente", "1 Einheit")], b)
    assert panel._chooser.get() == "Prozente (1 Einheit)"
    panel.show_empty("Noch keine Sequenz")
    panel.body.update()
    assert panel.board.frame.winfo_manager() == "" and panel._empty.winfo_manager() == "pack"


def test_f2_renames_in_place_and_an_invalid_name_shows_inline(ladder):
    panel, controller, _dialogs, _moved = ladder
    key_widget = panel.board.key_widget
    for name in ("A", "B"):
        controller.set_cursor(BoardCell(rung_key(0), LANE_INHALT))
        controller.add(BoardCell(rung_key(0), LANE_INHALT))
        _type(panel, name)
    assert press_key(key_widget, "F2") is True
    field = panel.board.editor.field
    assert field.get() == "B"
    field.set("a")
    press_key(field.text, "Return")
    assert "bereits" in panel.board.editor.error_message
    _type(panel, "C")
    assert [b.text for b in controller.ladder.rung(0).inhalt] == ["A", "C"]


def test_plus_in_the_ideas_lane_adds_material_above_the_ideas(ladder):
    panel, controller, _dialogs, _moved = ladder
    controller.add(BoardCell(rung_key(0), LANE_IDEEN))
    _type(panel, "Buch S. 12")
    assert [b.text for b in controller.ladder.rung(0).material] == ["Buch S. 12"]
    card = panel.board._layout.cards[card_key(BlockRef(0, LadderSide.MATERIAL, "Buch S. 12"))]
    cell = panel.board._layout.cells[BoardCell(rung_key(0), LANE_IDEEN)]
    assert card.box[3] < cell.text_box[1]


def test_plus_lines_in_the_idea_text_become_material(ladder):
    panel, controller, _dialogs, _moved = ladder
    panel.board.edit_text(BoardCell(rung_key(0), LANE_IDEEN))
    panel.board.editor.field.set("+ AB 1\nPlakat")
    panel.board.editor.commit()
    rung = controller.ladder.rung(0)
    assert [b.text for b in rung.material] == ["AB 1"] and rung.ideen == ("Plakat",)
