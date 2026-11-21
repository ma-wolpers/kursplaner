"""Alias-Regeln der Netz-Bausteine: Zurücksetzen, Kopie-Vorschlag, Anzeige des Originals (synthetische Daten)."""

from __future__ import annotations

from kursplaner.core.domain.sequence_ladder import BlockRef, LadderBlock, LadderRung, LadderSide, SequenceLadder
from kursplaner.core.domain.sequence_ladder_alias import alias_problem, resolve_alias, shows_original

INH = LadderSide.INHALT
ORIGINAL = "stellen Brüche dar"


def _ladder(*texts: tuple[str, str | None]) -> SequenceLadder:
    return SequenceLadder(tuple(LadderRung((LadderBlock(text, kid),)) for text, kid in texts))


def test_empty_input_resets_to_the_original_otherwise_the_input_counts():
    assert resolve_alias("   ", "K-31", ORIGINAL) == ORIGINAL
    assert resolve_alias(" Brüche zeigen ", "K-31", ORIGINAL) == "Brüche zeigen"
    assert resolve_alias("", "K-31", None) == ""


def test_reset_is_accepted_when_the_original_is_free():
    ladder = _ladder(("Brüche zeigen", "K-31"))
    ref = BlockRef(0, INH, "Brüche zeigen")
    assert alias_problem("", ladder, side=INH, rung=0, kompetenz_id="K-31", original=ORIGINAL, ignore=ref) is None


def test_reset_onto_an_existing_original_suggests_a_free_copy():
    ladder = _ladder((ORIGINAL, "K-31"), ("Brüche zeigen", "K-31"), (f"{ORIGINAL} (Kopie)", None))
    ref = BlockRef(1, INH, "Brüche zeigen")
    problem = alias_problem("", ladder, side=INH, rung=1, kompetenz_id="K-31", original=ORIGINAL, ignore=ref)
    assert problem is not None
    assert problem.suggestion == f"{ORIGINAL} (Kopie 2)"
    assert "bereits" in problem.message and "Vorschlag" in problem.message


def test_typed_duplicate_gets_no_suggestion():
    ladder = _ladder(("Brüche zeigen", "K-31"), ("anders", "K-31"))
    ref = BlockRef(1, INH, "anders")
    problem = alias_problem(
        "brüche zeigen", ladder, side=INH, rung=1, kompetenz_id="K-31", original=ORIGINAL, ignore=ref
    )
    assert problem is not None and problem.suggestion is None


def test_empty_input_without_known_original_is_a_missing_description():
    problem = alias_problem("", SequenceLadder(), side=INH, rung=0, kompetenz_id="K-31", original=None)
    assert problem is not None and "Beschreibung" in problem.message and problem.suggestion is None


def test_original_is_shown_only_for_an_edited_network_block():
    assert shows_original(LadderBlock("Brüche zeigen", "K-31"), ORIGINAL)
    assert shows_original(LadderBlock("Stellen Brüche dar", "K-31"), ORIGINAL)  # Großschreibung ist auch eine Änderung
    assert not shows_original(LadderBlock(ORIGINAL, "K-31"), ORIGINAL)
    assert not shows_original(LadderBlock("Brüche zeigen", "K-31"), None)
    assert not shows_original(LadderBlock("eigener Baustein"), ORIGINAL)
