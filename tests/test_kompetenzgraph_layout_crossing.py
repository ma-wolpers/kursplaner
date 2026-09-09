from kursplaner.core.domain.kompetenzgraph_layout_crossing import count_crossings, minimize_crossings

_CROSSED_LAYERS = {0: ("P1", "P2"), 1: ("C1", "C2")}
_CROSSED_EDGES = {"P1": (), "P2": (), "C1": ("P2",), "C2": ("P1",)}


def test_count_crossings_detects_a_single_crossing():
    assert count_crossings(_CROSSED_LAYERS, _CROSSED_EDGES) == 1


def test_count_crossings_zero_for_non_crossing_configuration():
    non_crossed_layers = {0: ("P1", "P2"), 1: ("C2", "C1")}
    assert count_crossings(non_crossed_layers, _CROSSED_EDGES) == 0


def test_count_crossings_ignores_edges_sharing_the_same_lower_node():
    """Zwei Kanten, die im selben unteren Knoten zusammenlaufen, sind keine Kreuzung."""
    layers = {0: ("P1", "P2"), 1: ("C1",)}
    edges = {"P1": (), "P2": (), "C1": ("P1", "P2")}
    assert count_crossings(layers, edges) == 0


def test_minimize_crossings_finds_the_zero_crossing_reordering():
    result = minimize_crossings(_CROSSED_LAYERS, _CROSSED_EDGES)

    assert result[0] == ("P1", "P2")
    assert result[1] == ("C2", "C1")
    assert count_crossings(result, _CROSSED_EDGES) == 0


def test_minimize_crossings_never_returns_a_worse_ordering_than_the_input():
    result = minimize_crossings(_CROSSED_LAYERS, _CROSSED_EDGES)
    initial_crossings = count_crossings(_CROSSED_LAYERS, _CROSSED_EDGES)
    result_crossings = count_crossings(result, _CROSSED_EDGES)

    assert result_crossings <= initial_crossings


def test_minimize_crossings_is_deterministic():
    first = minimize_crossings(_CROSSED_LAYERS, _CROSSED_EDGES)
    second = minimize_crossings(_CROSSED_LAYERS, _CROSSED_EDGES)

    assert first == second


def test_minimize_crossings_leaves_already_optimal_layout_unchanged():
    layers = {0: ("Single",)}
    result = minimize_crossings(layers, {})

    assert result == layers


def test_minimize_crossings_terminates_on_a_larger_random_like_configuration():
    """Kein exaktes Ergebnis erwartet -- nur, dass das Verfahren terminiert und nie verschlechtert."""
    upper = tuple(f"P{i}" for i in range(20))
    lower = tuple(f"C{i}" for i in range(20))
    # Bewusst "verdreht": Ci haengt am Elternteil P(19-i) -- maximal durchmischt.
    edges = {f"C{i}": (f"P{19 - i}",) for i in range(20)}
    for parent in upper:
        edges.setdefault(parent, ())
    layers = {0: upper, 1: lower}

    initial_crossings = count_crossings(layers, edges)
    result = minimize_crossings(layers, edges)
    result_crossings = count_crossings(result, edges)

    assert result_crossings <= initial_crossings
    assert set(result[0]) == set(upper)
    assert set(result[1]) == set(lower)
