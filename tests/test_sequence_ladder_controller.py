"""Leiter-Controller: jede Aktion eine Operation, Namensabfragen, Sperren (Fake-Dialoge, echte Datei)."""

from __future__ import annotations

import pytest
from bw_gui.widgets.card_board import BoardCell, BoardSlot, TextRejection
from sequence_ladder_test_support import make_ladder_env

from kursplaner.adapters.gui.sequence_ladder_board_mapping import (
    LANE_IDEEN,
    LANE_INHALT,
    LANE_PROZESS,
    card_key,
    rung_key,
)
from kursplaner.adapters.gui.sequence_ladder_controller import LadderClipboard, SequenceLadderController
from kursplaner.core.domain.competence_wording import CompetenceWording
from kursplaner.core.domain.sequence_ladder import BlockRef, LadderBlock, LadderSide
from kursplaner.core.domain.sequence_ladder_alias import CopiedBlock

PRO = LadderSide.PROZESS
NETZ = CompetenceWording("Mat-PL-1", "Netz", "Netz knüpfen")
"""Erfundene Kompetenz: Satzform „Netz“ (Kompetenzspalte), Lernziel-Form „Netz knüpfen“."""


class FakeDialogs:
    """`LadderDialogs` und `BlockTextInput` zugleich: Antworten der Namenseingabe stehen in ``answers``.

    Wie der Inline-Editor des Boards: ``None`` bricht ab, ein abgelehnter Text (``validate``)
    bleibt in der Eingabe stehen – beides ruft ``done`` nicht auf. Eine `TextRejection` landet
    in ``rejections`` (ihr Vorschlag stünde dann im Feld).
    """

    def __init__(self):
        self.answers: list[str | None] = []
        self.asked: list[tuple[object, str]] = []
        self.validators = []
        self.rejections: list[TextRejection] = []
        self.infos: list[str] = []
        self.errors: list[str] = []

    def request(self, target, *, initial, validate, done):
        self.asked.append((target, initial))
        self.validators.append(validate)
        answer = self.answers.pop(0)
        if answer is None:
            return
        result = validate(answer)
        if isinstance(result, TextRejection):
            self.rejections.append(result)
        elif result is None:
            done(answer)

    def show_error(self, title, message):
        self.errors.append(message)

    def show_info(self, title, message):
        self.infos.append(message)


@pytest.fixture
def make(tmp_path):
    """Controller über einer synthetischen Sequenz; ohne *kinds* liegen alle Sprossen in der Ablage."""

    def factory(kinds="", *, missing=False, after_write=None, clipboard=None, root=None, **units):
        if root is not None:
            root.mkdir()
        env = make_ladder_env(root or tmp_path, kinds, originals=FakeOriginals(), **units)
        dialogs, renders, writes = FakeDialogs(), [], []
        controller = SequenceLadderController(
            sequence_path=env.sequence_path,
            load=env.load,
            edit=env.edit,
            context=lambda: None if missing else env.context,
            dialogs=dialogs,
            text_input=dialogs,
            render=lambda view, cursor, banner: renders.append((view, cursor, banner)),
            after_write=after_write or writes.append,
            clipboard=clipboard,
        )
        controller.reload()
        return controller, dialogs, renders, writes, env.history

    return factory


class FakeOriginals:
    """Originale-Puffer mit einer erfundenen Kompetenz (`NETZ`)."""

    def original(self, kompetenz_id):
        return NETZ if kompetenz_id == "Mat-PL-1" else None


def _with_ablage(controller, *lines):
    """Schreibt eine Ablage in die Sequenzdatei (wie von Hand) und lädt neu."""
    path = controller.sequence_path
    section = "## Sequenzleiter\n\n- Ablage 1\n" + "".join(f"  - {line}\n" for line in lines) + "\n## Export"
    path.write_text(path.read_text(encoding="utf-8").replace("## Export", section), encoding="utf-8")
    controller.reload()


def _key(text, rung=0, side=LadderSide.INHALT):
    return card_key(BlockRef(rung, side, text))


def _inhalt(controller, rung=0):
    return [b.text for b in controller.ladder.rung(rung).inhalt]


def test_plus_asks_for_a_name_and_appends_in_the_cell(make):
    controller, dialogs, _renders, writes, history = make()
    dialogs.answers = ["A", "B"]
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    assert _inhalt(controller) == ["A", "B"] and controller.cursor == _key("B")
    assert len(writes) == 2 and len(history.undo_stack) == 2
    assert dialogs.validators[-1]("a") is not None  # Eindeutigkeit schon im Dialog


def test_copy_paste_inserts_above_with_prefilled_name(make):
    controller, dialogs, *_ = make()
    dialogs.answers = ["A", "B", "A2"]
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.set_cursor(_key("A"))
    controller.copy()
    controller.set_cursor(_key("B"))
    controller.paste()
    assert dialogs.asked[-1] == (BoardSlot(rung_key(0), LANE_INHALT, 1), "A")  # Entwurf über „B“
    assert _inhalt(controller) == ["A", "A2", "B"]


def test_paste_without_clipboard_or_target_explains_itself(make):
    controller, dialogs, *_ = make()
    controller.paste()
    controller.clipboard.copied = CopiedBlock.of(LadderBlock("A"), LadderSide.INHALT, None)
    controller.set_cursor(None)
    controller.paste()
    assert len(dialogs.infos) == 2


def test_rename_of_network_block_edits_the_alias_and_keeps_the_link(make):
    controller, dialogs, *_ = make()
    _with_ablage(controller, "Prozess: [[Mat-PL-1|Netz]]")
    controller.set_cursor(_key("Netz", side=PRO))
    dialogs.answers = ["Netz anders"]
    controller.rename()
    assert controller.ladder.rung(0).prozess == (LadderBlock("Netz anders", "Mat-PL-1"),)
    assert "[[Mat-PL-1|Netz anders]]" in controller.sequence_path.read_text(encoding="utf-8")
    assert controller.view.originals == {"Mat-PL-1": NETZ}


def test_empty_rename_resets_to_the_original(make):
    controller, dialogs, *_ = make()
    _with_ablage(controller, "Prozess: [[Mat-PL-1|Netz anders]]")
    controller.set_cursor(_key("Netz anders", side=PRO))
    dialogs.answers = [""]
    controller.rename()
    assert controller.ladder.rung(0).prozess == (LadderBlock("Netz", "Mat-PL-1"),)


def test_empty_rename_onto_an_existing_original_suggests_a_copy(make):
    controller, dialogs, *_ = make()
    _with_ablage(controller, "Prozess: [[Mat-PL-1|Netz]]", "Prozess: [[Mat-PL-1|Netz anders]]")
    controller.set_cursor(_key("Netz anders", side=PRO))
    dialogs.answers = [""]
    controller.rename()
    assert [r.replacement for r in dialogs.rejections] == ["Netz (Kopie)"]
    assert [b.text for b in controller.ladder.rung(0).prozess] == ["Netz", "Netz anders"]  # nichts geschrieben


def test_copy_paste_of_a_network_block_keeps_link_and_text_across_ladders(make, tmp_path):
    shared = LadderClipboard()
    source, _dialogs, *_ = make(clipboard=shared)
    _with_ablage(source, "Prozess: [[Mat-PL-1|Netz anders]]", "Inhalt: Ziel")
    source.set_cursor(_key("Netz anders", side=PRO))
    source.copy()
    assert shared.copied == CopiedBlock(LadderBlock("Netz anders", "Mat-PL-1"), NETZ, "Netz anders")
    target, dialogs, *_ = make("U", clipboard=shared, root=tmp_path / "zweite")  # andere Leiter, neuer Controller
    target.set_cursor(BoardCell(rung_key(0), LANE_PROZESS))
    dialogs.answers = ["Netz anders"]
    target.paste()
    assert dialogs.asked[-1][1] == "Netz anders"
    assert target.ladder.rung(0).prozess == (LadderBlock("Netz anders", "Mat-PL-1"),)


def test_copying_without_alias_between_columns_switches_the_wording(make):
    controller, dialogs, *_ = make()
    _with_ablage(controller, "Prozess: [[Mat-PL-1|Netz]]", "Inhalt: Ziel")
    controller.set_cursor(_key("Netz", side=PRO))
    controller.copy()
    controller.set_cursor(BoardCell(rung_key(0), LANE_INHALT))
    dialogs.answers = ["Netz knüpfen"]
    controller.paste()
    assert dialogs.asked[-1][1] == "Netz knüpfen"  # Lernziel-Form, nicht die Satzform
    assert LadderBlock("Netz knüpfen", "Mat-PL-1") in controller.ladder.rung(0).inhalt
    controller.set_cursor(_key("Netz knüpfen"))
    controller.copy()
    controller.set_cursor(BoardCell(rung_key(0), LANE_PROZESS))
    dialogs.answers = [None]  # nur die Vorbelegung prüfen
    controller.paste()
    assert dialogs.asked[-1][1] == "Netz"  # zurück zur Satzform


def test_copying_with_alias_between_columns_keeps_the_alias(make):
    controller, dialogs, *_ = make()
    _with_ablage(controller, "Prozess: [[Mat-PL-1|eigene Fassung]]")
    controller.set_cursor(_key("eigene Fassung", side=PRO))
    controller.copy()
    controller.set_cursor(BoardCell(rung_key(0), LANE_INHALT))
    dialogs.answers = [None]
    controller.paste()
    assert dialogs.asked[-1][1] == "eigene Fassung"


def test_empty_rename_in_the_goal_column_resets_to_the_infinitive(make):
    controller, dialogs, *_ = make()
    _with_ablage(controller, "Inhalt: [[Mat-PL-1|Netz]]")
    controller.set_cursor(_key("Netz"))
    dialogs.answers = [""]
    controller.rename()
    assert controller.ladder.rung(0).inhalt == (LadderBlock("Netz knüpfen", "Mat-PL-1"),)


def test_delete_selects_the_neighbour_or_the_empty_cell(make):
    controller, dialogs, *_ = make()
    dialogs.answers = ["A", "B"]
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.set_cursor(_key("A"))
    controller.delete()
    assert controller.cursor == _key("B")
    controller.delete()
    assert controller.cursor == BoardCell(rung_key(0), LANE_INHALT)


def test_delete_reads_the_ladder_only_once(make):
    """Löschen lud die Leiter früher zweimal (einmal nur, um den Nachbar-Cursor zu zeigen)."""
    controller, dialogs, renders, *_ = make()
    dialogs.answers = ["A", "B"]
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.set_cursor(_key("A"))
    reloads_before = controller._reload_count
    controller.delete()
    assert controller._reload_count == reloads_before + 1
    assert renders[-1][1] == _key("B")


def test_step_and_drop_keep_the_selection(make):
    controller, dialogs, *_ = make()
    dialogs.answers = ["A"]
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.step(up=True)
    assert _inhalt(controller, 1) == ["A"] and controller.cursor == _key("A", 1)
    controller.drop(_key("A", 1), BoardSlot(rung_key(3), LANE_INHALT, 0))
    assert _inhalt(controller, 3) == ["A"] and controller.cursor == _key("A", 3)


def test_drop_lands_exactly_at_the_shown_line_within_the_rung(make):
    """Regression: nach unten in derselben Sprosse landete der Baustein eine Position zu tief."""
    controller, dialogs, *_ = make()
    dialogs.answers = ["A", "B", "C"]
    for _ in range(3):
        controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.drop(_key("A"), BoardSlot(rung_key(0), LANE_INHALT, 2))  # Linie zwischen B und C
    assert _inhalt(controller) == ["B", "A", "C"]
    controller.drop(_key("C"), BoardSlot(rung_key(0), LANE_INHALT, 0))  # Linie über B
    assert _inhalt(controller) == ["C", "B", "A"]


def test_ideas_commit_is_one_step(make):
    controller, _dialogs, _renders, _writes, history = make()
    controller.commit_ideas(BoardCell(rung_key(1), LANE_IDEEN), "Plakat\nPizza")
    assert controller.ladder.rung(1).ideen == ("Plakat", "Pizza")
    assert [e.label for e in history.undo_stack] == ["Ideen bearbeiten"]


def test_missing_sequence_is_read_only_with_banner(make):
    controller, dialogs, renders, writes, _history = make(missing=True)
    controller.add(BoardCell(rung_key(0), LANE_PROZESS))
    assert controller.read_only and writes == [] and dialogs.asked == []
    assert "nicht (mehr) vor" in renders[-1][2]


def test_right_column_names_are_checked_per_rung(make):
    controller, dialogs, *_ = make()
    dialogs.answers = ["P", None, None]
    controller.add(BoardCell(rung_key(0), LANE_PROZESS))
    controller.add(BoardCell(rung_key(1), LANE_PROZESS))
    other_rung = dialogs.validators[-1]
    controller.add(BoardCell(rung_key(0), LANE_PROZESS))
    same_rung = dialogs.validators[-1]
    assert other_rung("p") is None
    assert same_rung("p") is not None


def test_write_refreshes_the_written_files_and_reloads_the_ladder_exactly_once(make):
    reloads = []
    holder = {}

    def after_write(written):
        reloads.append(written)
        holder["controller"].reload()  # wie `_publish_sequence_plans` nach dem gezielten Refresh

    controller, dialogs, renders, *_ = make("U", after_write=after_write)
    holder["controller"] = controller
    dialogs.answers = ["Ziel"]
    before = len(renders)
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    ((written,),) = reloads
    assert written.parent.name == "Einheiten" and len(renders) == before + 1
    assert controller.cursor == _key("Ziel")


def test_locked_rung_explains_itself_instead_of_asking(make):
    controller, dialogs, _renders, writes, _history = make("UL")
    controller.add(BoardCell(rung_key(1), LANE_INHALT))
    assert dialogs.asked == [] and writes == [] and "Sprosse 2" in dialogs.infos[0]


def test_banner_lists_legacy_duplicates(make):
    _controller, _dialogs, renders, *_ = make("UU", u0={"ziel": "Gleich"}, u1={"ziel": "Gleich"})
    assert "„Gleich“ steht mehrfach (Sprossen 1 und 2)" in renders[-1][2]
