"""Alias-Regeln der Netz-Bausteine: Zurücksetzen, Kopie-Vorschlag, Anzeige des Originals, Kopieren (synthetisch)."""

from __future__ import annotations

from kursplaner.core.domain.competence_wording import CompetenceWording
from kursplaner.core.domain.sequence_ladder import BlockRef, LadderBlock, LadderRung, LadderSide, SequenceLadder
from kursplaner.core.domain.sequence_ladder_alias import CopiedBlock, alias_problem, resolve_alias, shows_original

INH = LadderSide.INHALT
PRO = LadderSide.PROZESS
WORDING = CompetenceWording("K-31", "stellen Brüche dar", "Brüche darstellen")
LERNZIEL = "Brüche darstellen"  # Original links (Infinitiv)
KOMPETENZ = "stellen Brüche dar"  # Original rechts (Satzform)


def _ladder(*texts: tuple[str, str | None]) -> SequenceLadder:
    return SequenceLadder(tuple(LadderRung((LadderBlock(text, kid),)) for text, kid in texts))


def test_empty_input_resets_to_the_original_of_the_side_otherwise_the_input_counts():
    assert resolve_alias("   ", "K-31", WORDING, INH) == LERNZIEL
    assert resolve_alias("   ", "K-31", WORDING, PRO) == KOMPETENZ
    assert resolve_alias(" Brüche zeigen ", "K-31", WORDING, INH) == "Brüche zeigen"
    assert resolve_alias("", "K-31", None, INH) == ""


def test_reset_is_accepted_when_the_original_is_free():
    ladder = _ladder(("Brüche zeigen", "K-31"))
    ref = BlockRef(0, INH, "Brüche zeigen")
    assert alias_problem("", ladder, side=INH, rung=0, kompetenz_id="K-31", wording=WORDING, ignore=ref) is None


def test_reset_onto_an_existing_original_suggests_a_free_copy():
    ladder = _ladder((LERNZIEL, "K-31"), ("Brüche zeigen", "K-31"), (f"{LERNZIEL} (Kopie)", None))
    ref = BlockRef(1, INH, "Brüche zeigen")
    problem = alias_problem("", ladder, side=INH, rung=1, kompetenz_id="K-31", wording=WORDING, ignore=ref)
    assert problem is not None
    assert problem.suggestion == f"{LERNZIEL} (Kopie 2)"
    assert "bereits" in problem.message and "Vorschlag" in problem.message


def test_typed_duplicate_gets_no_suggestion():
    ladder = _ladder(("Brüche zeigen", "K-31"), ("anders", "K-31"))
    ref = BlockRef(1, INH, "anders")
    problem = alias_problem("brüche zeigen", ladder, side=INH, rung=1, kompetenz_id="K-31", wording=WORDING, ignore=ref)
    assert problem is not None and problem.suggestion is None


def test_empty_input_without_known_wording_is_a_missing_description():
    problem = alias_problem("", SequenceLadder(), side=INH, rung=0, kompetenz_id="K-31", wording=None)
    assert problem is not None and "Beschreibung" in problem.message and problem.suggestion is None


def test_original_is_shown_only_for_a_network_block_with_alias_on_its_side():
    assert shows_original(LadderBlock("Brüche zeigen", "K-31"), WORDING, INH)
    assert shows_original(LadderBlock("brüche darstellen", "K-31"), WORDING, INH)  # Schreibweise ist eine Änderung
    assert not shows_original(LadderBlock(LERNZIEL, "K-31"), WORDING, INH)
    assert not shows_original(LadderBlock(KOMPETENZ, "K-31"), WORDING, PRO)
    assert not shows_original(LadderBlock("Brüche zeigen", "K-31"), None, INH)
    assert not shows_original(LadderBlock("eigener Baustein"), WORDING, INH)


def test_the_variant_of_the_other_side_is_an_alias_not_an_original():
    # Die Satzform in der Lernziel-Spalte ist falsch formuliert: sichtbar machen, nicht legitimieren.
    assert shows_original(LadderBlock(KOMPETENZ, "K-31"), WORDING, INH)
    assert shows_original(LadderBlock(LERNZIEL, "K-31"), WORDING, PRO)


def test_copying_without_alias_switches_to_the_variant_of_the_target_side():
    copied = CopiedBlock.of(LadderBlock(LERNZIEL, "K-31"), INH, WORDING)
    assert copied.alias is None
    assert copied.text_for(PRO) == KOMPETENZ
    assert copied.text_for(INH) == LERNZIEL
    back = CopiedBlock.of(LadderBlock(KOMPETENZ, "K-31"), PRO, WORDING)
    assert back.text_for(INH) == LERNZIEL


def test_copying_keeps_an_alias_literally_on_every_side():
    copied = CopiedBlock.of(LadderBlock("Brüche zeigen", "K-31"), INH, WORDING)
    assert copied.alias == "Brüche zeigen"
    assert copied.text_for(PRO) == "Brüche zeigen"


def test_copying_onto_material_or_without_wording_keeps_the_visible_text():
    copied = CopiedBlock.of(LadderBlock(LERNZIEL, "K-31"), INH, WORDING)
    assert copied.text_for(LadderSide.MATERIAL) == LERNZIEL
    unknown = CopiedBlock.of(LadderBlock(LERNZIEL, "K-31"), INH, None)
    assert unknown.text_for(PRO) == LERNZIEL
    own = CopiedBlock.of(LadderBlock("Plakat"), LadderSide.MATERIAL, None)
    assert own.text_for(INH) == "Plakat"
