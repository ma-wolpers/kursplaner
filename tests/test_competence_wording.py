"""Formulierung einer Netz-Kompetenz: Original je Seite, Alias-Zustand, Rückfall ohne Infinitiv (synthetisch)."""

from __future__ import annotations

import pytest
from kompetenzgraph_test_support import make_node

from kursplaner.core.domain.competence_wording import CompetenceWording, wording_of
from kursplaner.core.domain.sequence_ladder import SIDE_RULES, LadderSide, NetworkWording
from kursplaner.core.domain.sequence_ladder_entries import network_block_text

WORDING = CompetenceWording("K-31", "stellen Brüche dar", "Brüche darstellen")


def test_side_rules_name_the_variant_and_only_network_sides_have_one():
    assert SIDE_RULES[LadderSide.INHALT].wording is NetworkWording.INFINITIVE
    assert SIDE_RULES[LadderSide.PROZESS].wording is NetworkWording.TITLE
    assert SIDE_RULES[LadderSide.MATERIAL].wording is None
    assert [side for side, rules in SIDE_RULES.items() if rules.network] == [LadderSide.INHALT, LadderSide.PROZESS]


def test_original_per_side_is_normalized_like_the_import():
    assert WORDING.for_side(LadderSide.INHALT) == "Brüche darstellen"
    assert WORDING.for_side(LadderSide.PROZESS) == "stellen Brüche dar"
    odd = CompetenceWording("K-1", "Titel [mit] Klammern", "Klammern [haben]")
    assert odd.for_side(LadderSide.PROZESS) == network_block_text("K-1", "Titel [mit] Klammern")
    with pytest.raises(ValueError):
        WORDING.for_side(LadderSide.MATERIAL)


def test_alias_is_any_deviation_from_the_original_of_the_side():
    assert WORDING.alias_on("Brüche darstellen", LadderSide.INHALT) is None
    assert WORDING.alias_on("stellen Brüche dar", LadderSide.INHALT) == "stellen Brüche dar"
    assert WORDING.text_on(LadderSide.PROZESS, None) == "stellen Brüche dar"
    assert WORDING.text_on(LadderSide.PROZESS, "eigener Text") == "eigener Text"


def test_wording_of_a_node_falls_back_to_the_title_without_infinitive():
    with_field = wording_of(make_node("K-1", title="stellen Brüche dar", title_infinitive="Brüche darstellen"))
    assert with_field.infinitive == "Brüche darstellen"
    without = wording_of(make_node("K-2", title="stellen Brüche dar"))
    assert without.infinitive == "stellen Brüche dar"
    assert without.for_side(LadderSide.INHALT) == without.for_side(LadderSide.PROZESS)
