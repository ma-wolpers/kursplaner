from kursplaner.core.domain.kompetenzgraph_layout_forces import (
    compute_bereich_centroid_positions,
    relax_horizontal_positions,
)


def test_relax_preserves_layer_order_with_no_edges():
    sorted_layers = {0: ("B", "A", "C")}  # bewusst nicht alphabetisch -- simuliert crossing-minimierte Reihenfolge
    edges = {}

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=100.0)

    ordered_by_x = tuple(sorted(positions, key=lambda node_id: positions[node_id]))
    assert ordered_by_x == ("B", "A", "C")


def test_relax_never_reorders_within_layer_even_under_conflicting_pull():
    """Harte Invariante: die Schicht-Reihenfolge bleibt erhalten, auch wenn X von rechts und Z von links gezogen wird."""
    sorted_layers = {0: ("FAR_LEFT_PARENT", "FAR_RIGHT_PARENT"), 1: ("X", "Y", "Z")}
    edges = {"X": ("FAR_RIGHT_PARENT",), "Z": ("FAR_LEFT_PARENT",)}

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=100.0)

    ordered_by_x = tuple(sorted(("X", "Y", "Z"), key=lambda node_id: positions[node_id]))
    assert ordered_by_x == ("X", "Y", "Z")


def test_relax_respects_minimum_spacing_when_siblings_share_one_parent():
    sorted_layers = {0: ("PARENT1", "PARENT2"), 1: ("CHILD1", "CHILD2", "CHILD3")}
    edges = {"CHILD1": ("PARENT1",), "CHILD2": ("PARENT1",), "CHILD3": ("PARENT1",)}

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=170.0)

    child_positions = sorted(positions[node_id] for node_id in ("CHILD1", "CHILD2", "CHILD3"))
    assert child_positions[1] - child_positions[0] >= 170.0
    assert child_positions[2] - child_positions[1] >= 170.0


def test_relax_pulls_connected_nodes_closer_together():
    """Ein Kind, das nur an EINEM von zwei Eltern hängt, bewegt sich Richtung dieses Elternteils."""
    sorted_layers = {0: ("FAR_PARENT", "NEAR_PARENT"), 1: ("CHILD",)}
    edges = {"CHILD": ("NEAR_PARENT",)}

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=170.0)

    assert positions["CHILD"] == positions["NEAR_PARENT"]


def test_zero_iterations_returns_pure_slot_index_positions_despite_edges():
    """`iterations=0` (Performance-Budget-Fallback für sehr große sichtbare Mengen) überspringt jede Relaxation."""
    sorted_layers = {0: ("A",), 1: ("B", "C")}
    edges = {"B": ("A",), "C": ("A",)}

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=0, min_spacing=100.0)

    assert positions == {"A": 0.0, "B": 0.0, "C": 100.0}


def test_bereich_centroid_lands_near_actual_cluster_not_alphabetical_order():
    node_x_by_id = {"A": 0.0, "B": 10.0, "Z": 1000.0}
    classification_edges = {"I-Zebra": ("Z",), "I-Anfang": ("A", "B")}

    positions = compute_bereich_centroid_positions(
        frozenset({"I-Zebra", "I-Anfang"}), node_x_by_id, classification_edges, min_spacing=170.0
    )

    # Alphabetisch stünde "I-Anfang" vor "I-Zebra" -- hier muss die tatsächliche
    # Knoten-Position entscheiden: "I-Anfang" liegt nahe 0/10, "I-Zebra" nahe 1000.
    assert positions["I-Anfang"] < positions["I-Zebra"]


def test_bereich_without_classified_visible_nodes_falls_back_to_zero():
    positions = compute_bereich_centroid_positions(frozenset({"I-Leer"}), {}, {}, min_spacing=170.0)

    assert positions["I-Leer"] == 0.0


def test_bereich_centroid_respects_minimum_spacing():
    node_x_by_id = {"A": 500.0, "B": 505.0}  # zwei fast identische Cluster-Schwerpunkte
    classification_edges = {"I-Eins": ("A",), "I-Zwei": ("B",)}

    positions = compute_bereich_centroid_positions(
        frozenset({"I-Eins", "I-Zwei"}), node_x_by_id, classification_edges, min_spacing=170.0
    )

    assert abs(positions["I-Eins"] - positions["I-Zwei"]) >= 170.0
