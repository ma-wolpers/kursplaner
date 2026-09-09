from kursplaner.core.domain.kompetenzgraph_dag import (
    check_kompetenz_graph_for_cycles,
    find_back_edges,
    find_cycles,
)
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from tests.kompetenzgraph_test_support import make_node


def test_find_cycles_returns_empty_for_acyclic_chain():
    edges = {"A": ("B",), "B": ("C",), "C": ()}

    assert find_cycles(edges) == ()
    assert find_back_edges(edges) == frozenset()


def test_find_cycles_detects_self_reference():
    edges = {"A": ("A",)}

    cycles = find_cycles(edges)

    assert cycles == (("A",),)
    assert ("A", "A") in find_back_edges(edges)


def test_find_cycles_detects_two_node_cycle():
    edges = {"A": ("B",), "B": ("A",)}

    cycles = find_cycles(edges)

    assert len(cycles) == 1
    assert set(cycles[0]) == {"A", "B"}


def test_find_cycles_detects_three_node_cycle():
    edges = {"A": ("B",), "B": ("C",), "C": ("A",)}

    cycles = find_cycles(edges)

    assert len(cycles) == 1
    assert set(cycles[0]) == {"A", "B", "C"}


def test_diamond_multi_parent_dag_is_not_a_cycle():
    """A hat zwei Kinder B und C, die beide zu D fuehren -- ein Multi-Parent-DAG, kein Zyklus."""
    edges = {"A": (), "B": ("A",), "C": ("A",), "D": ("B", "C")}

    assert find_cycles(edges) == ()


def test_edge_to_unresolved_target_is_not_a_cycle():
    """Eine Kante zu einer ID, die selbst kein Schluessel im Kantenbild ist, ist eine Senke."""
    edges = {"A": ("NICHT-EXISTENT",)}

    assert find_cycles(edges) == ()


def test_check_kompetenz_graph_for_cycles_separates_edge_kinds():
    """Ein Zyklus in voraussetzungen darf die oberkompetenzen-Pruefung nicht beeinflussen und umgekehrt."""
    node_a = make_node("A", oberkompetenzen_ids=(), voraussetzungen_ids=("B",))
    node_b = make_node("B", oberkompetenzen_ids=(), voraussetzungen_ids=("A",))

    snapshot = build_kompetenz_graph_snapshot([node_a, node_b], [])

    diagnostics = check_kompetenz_graph_for_cycles(snapshot)

    assert len(diagnostics) == 1
    assert diagnostics[0].edge_kind == "prerequisite"
    assert set(diagnostics[0].member_ids) == {"A", "B"}


def test_check_kompetenz_graph_for_cycles_returns_empty_for_clean_graph():
    node_a = make_node("A")
    node_b = make_node("B", oberkompetenzen_ids=("A",))

    snapshot = build_kompetenz_graph_snapshot([node_a, node_b], [])

    assert check_kompetenz_graph_for_cycles(snapshot) == ()
