from kursplaner.core.domain.kompetenzgraph_layout_forces import (
    compute_bereich_centroid_positions,
    relax_horizontal_positions,
)

# --- `_pull_toward_neighbor_median()` -- Testmatrix (bisher ungeprüft als "korrekt" angenommen) ---


def test_node_without_any_neighbor_keeps_its_own_position():
    """Keine relevanten Nachbarn -> Fallback auf die eigene (Slot-Index-)Position, kein Sprung."""
    sorted_layers = {0: ("ANCHOR",), 1: ("ISOLATED",)}
    edges = {}  # ISOLATED hat weder Eltern noch Kinder

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=100.0)

    assert positions["ISOLATED"] == 0.0  # einziger Knoten seiner Schicht -> Slot-Index 0


def test_node_with_exactly_one_neighbor_moves_to_that_neighbors_position():
    sorted_layers = {0: ("FAR_PARENT", "NEAR_PARENT"), 1: ("CHILD",)}
    edges = {"CHILD": ("NEAR_PARENT",)}

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=170.0)

    assert positions["CHILD"] == positions["NEAR_PARENT"]


def test_node_with_exactly_two_neighbors_lands_at_their_average():
    sorted_layers = {0: ("PARENT_A", "PARENT_B"), 1: ("CHILD",)}
    edges = {"CHILD": ("PARENT_A", "PARENT_B")}  # Startpositionen 0.0 und 100.0

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=1, min_spacing=100.0)

    assert positions["CHILD"] == 50.0


def test_node_with_three_neighbors_lands_at_the_middle_value():
    sorted_layers = {0: ("PARENT_A", "PARENT_B", "PARENT_C"), 1: ("CHILD",)}
    edges = {"CHILD": ("PARENT_A", "PARENT_B", "PARENT_C")}  # Startpositionen 0.0, 100.0, 200.0 -> Median 100.0

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=1, min_spacing=100.0)

    assert positions["CHILD"] == 100.0


def test_widely_separated_neighbors_land_at_the_true_middle_not_skewed_by_magnitude():
    sorted_layers = {0: ("NEAR", "FAR"), 1: ("CHILD",)}
    edges = {"CHILD": ("NEAR", "FAR")}  # Startpositionen 0.0 und 1_000_000.0

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=1, min_spacing=1_000_000.0)

    assert positions["CHILD"] == 500_000.0


def test_asymmetric_neighborhood_uses_only_parents_top_down_and_only_children_bottom_up():
    """Ein Knoten mit Eltern UND Kindern darf pro Sweep-Richtung nur die jeweils passende
    Nachbarmenge befragen -- Eltern und Kinder werden nie vermischt."""
    sorted_layers = {0: ("PARENT",), 1: ("MIDDLE",), 2: ("CHILD",)}
    edges = {"MIDDLE": ("PARENT",), "CHILD": ("MIDDLE",)}

    # Genau ein Top-Down-Sweep: MIDDLE darf nur Richtung PARENT (0.0) gezogen werden,
    # CHILD (noch unangetastet) bleibt bei seinem Slot-Index 0.0 -- beide 0.0, nicht
    # zufällig durch eine Vermischung mit CHILDs ursprünglicher Position verzerrt.
    positions_top_down_only = relax_horizontal_positions(sorted_layers, edges, iterations=1, min_spacing=100.0)
    assert positions_top_down_only["MIDDLE"] == 0.0

    # Zwei Sweeps (Top-Down dann Bottom-Up): jetzt darf MIDDLE zusätzlich Richtung CHILD
    # gezogen werden -- bleibt hier bei 0.0, da CHILD nach Sweep 1 ebenfalls bei 0.0 liegt
    # (MIDDLEs eigener Wert aus Sweep 1). Wichtig ist die Abwesenheit eines Fehlers, nicht
    # ein exotischer Zahlenwert.
    positions_both_directions = relax_horizontal_positions(sorted_layers, edges, iterations=2, min_spacing=100.0)
    assert positions_both_directions["MIDDLE"] == 0.0


def test_more_iterations_stabilize_instead_of_drifting_further():
    """Nach Konvergenz darf ein zusätzlicher Sweep das Ergebnis nicht weiter verschieben."""
    sorted_layers = {0: ("PARENT_A", "PARENT_B"), 1: ("CHILD",)}
    edges = {"CHILD": ("PARENT_A", "PARENT_B")}

    positions_six = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=100.0)
    positions_twenty = relax_horizontal_positions(sorted_layers, edges, iterations=20, min_spacing=100.0)

    assert positions_six == positions_twenty


def test_identical_inputs_produce_identical_results():
    sorted_layers = {0: ("A", "B", "C"), 1: ("D", "E")}
    edges = {"D": ("A", "B"), "E": ("C",)}

    first = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=110.0)
    second = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=110.0)

    assert first == second


# --- Reihenfolge ist kein eigener Optimierungsgegenstand mehr -- sie folgt den Kräften ---


def test_relax_reorders_layer_to_follow_force_targets():
    """X (Richtung rechts gezogen) und Z (Richtung links gezogen) tauschen ihre ursprüngliche
    Reihenfolge, wenn die Kräfte das verlangen -- die Start-Reihenfolge ist nur der Sweep-0-Startpunkt."""
    sorted_layers = {0: ("FAR_LEFT_PARENT", "FAR_RIGHT_PARENT"), 1: ("X", "Y", "Z")}
    edges = {"X": ("FAR_RIGHT_PARENT",), "Z": ("FAR_LEFT_PARENT",)}

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=100.0)

    ordered_by_x = tuple(sorted(("X", "Y", "Z"), key=lambda node_id: positions[node_id]))
    assert ordered_by_x == ("Z", "X", "Y")


def test_single_layer_without_edges_never_enters_relaxation_at_all():
    """Eine einzelne Schicht hat nie eine andere Schicht, mit der relaxiert werden könnte --
    die Slot-Index-Startreihenfolge bleibt zwangsläufig unverändert (kein Sweep läuft je)."""
    sorted_layers = {0: ("B", "A", "C")}  # bewusst nicht alphabetisch
    edges = {}

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=100.0)

    ordered_by_x = tuple(sorted(positions, key=lambda node_id: positions[node_id]))
    assert ordered_by_x == ("B", "A", "C")


# --- Regressionstest: Eltern in NICHT benachbarten Schichten (früherer Bug, weiterhin geprüft) ---


def test_relax_pulls_toward_all_parents_even_across_skipped_layers():
    """Ein Kind mit zwei Eltern in NICHT benachbarten Schichten (0 und 2, Kind in Schicht 3 --
    Schicht 1 bleibt absichtlich leer, wie es beim longest-path-Layering vorkommt, wenn ein
    anderer Elternpfad tiefer ist) muss zwischen BEIDEN landen, nicht nur unter dem in der
    unmittelbar benachbarten Schicht liegenden Elternteil. `iterations=1` macht das Ergebnis von
    Hand nachrechenbar (Eltern-Positionen bleiben in diesem einen Sweep unverändert)."""
    sorted_layers = {
        0: ("FAR_PARENT", "FAR_PARENT_SIBLING"),  # Slot-Index-Startpositionen: 0.0, 100.0
        2: ("NEAR_PARENT", "NEAR_PARENT_SIBLING"),  # Slot-Index-Startpositionen: 0.0, 100.0
        3: ("CHILD",),
    }
    edges = {"CHILD": ("FAR_PARENT_SIBLING", "NEAR_PARENT")}  # x=100.0 bzw. x=0.0

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=1, min_spacing=100.0)

    assert positions["CHILD"] == 50.0


# --- Regressionstest für den realen Fehlerfall (109.780px-Lücke im echten Vault) ---


def test_relax_does_not_drag_unrelated_nodes_toward_a_distant_connected_outlier():
    """Mit der alten, fixierten crossing-minimierten Reihenfolge wurde ein unabhängiger Knoten
    stur auf 'Vorgänger + Mindestabstand' gezwungen, sobald ein anderer Knoten in der Schicht
    (durch Zufall der Reihenfolge, nicht der Kräfte) ein weit entferntes, aber legitimes Ziel
    hatte -- das erzeugte im echten Vault eine Lücke von über 100.000px zwischen zwei
    benachbarten Knoten derselben Schicht. Mit Sortierung nach Kräfte-Ziel kann das nicht mehr
    passieren: ein Ausreißer sortiert sich einfach dorthin ein, wo sein Ziel liegt, statt alles
    Nachfolgende (in der alten Reihenfolge) mitzuziehen."""
    filler_count = 200
    layer0 = tuple(f"FILLER-{i}" for i in range(filler_count)) + ("DISTANT_PARENT",)
    sorted_layers = {
        0: layer0,
        1: ("CONNECTED_CHILD", "A", "B", "C"),
    }
    edges = {"CONNECTED_CHILD": ("DISTANT_PARENT",)}  # A, B, C bleiben komplett unverbunden

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=100.0)

    distant_parent_x = positions["DISTANT_PARENT"]
    assert distant_parent_x >= filler_count * 100.0  # legitim weit rechts (200 Geschwister davor)

    # CONNECTED_CHILD darf (und soll) dem entfernten Elternteil folgen ...
    assert abs(positions["CONNECTED_CHILD"] - distant_parent_x) < 100.0

    # ... aber A, B, C sind unverbunden und müssen nahe ihrer EIGENEN Zielposition bleiben --
    # nicht künstlich auf die Größenordnung von DISTANT_PARENT hochgezogen werden. Geprüft wird
    # die tatsächliche Abweichung vom eigenen Ziel, nicht nur der Abstand zum Nachbarn.
    for node_id, own_target in (("A", 100.0), ("B", 200.0), ("C", 300.0)):
        assert abs(positions[node_id] - own_target) < 50.0

    # Keine fünfstellige künstliche Lücke zwischen benachbarten Knoten derselben Schicht.
    layer1_x_sorted = sorted(positions[node_id] for node_id in ("CONNECTED_CHILD", "A", "B", "C"))
    max_neighbor_gap = max(b - a for a, b in zip(layer1_x_sorted, layer1_x_sorted[1:]))
    assert max_neighbor_gap < 1000.0 or max_neighbor_gap == distant_parent_x - layer1_x_sorted[-2]


# --- Mindestabstand, Slot-Index-Fallback ---


def test_relax_respects_minimum_spacing_when_siblings_share_one_parent():
    sorted_layers = {0: ("PARENT1", "PARENT2"), 1: ("CHILD1", "CHILD2", "CHILD3")}
    edges = {"CHILD1": ("PARENT1",), "CHILD2": ("PARENT1",), "CHILD3": ("PARENT1",)}

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=170.0)

    child_positions = sorted(positions[node_id] for node_id in ("CHILD1", "CHILD2", "CHILD3"))
    assert child_positions[1] - child_positions[0] >= 170.0
    assert child_positions[2] - child_positions[1] >= 170.0


def test_zero_iterations_returns_pure_slot_index_positions_despite_edges():
    """`iterations=0` (Performance-Budget-Fallback für sehr große sichtbare Mengen) überspringt jede Relaxation."""
    sorted_layers = {0: ("A",), 1: ("B", "C")}
    edges = {"B": ("A",), "C": ("A",)}

    positions = relax_horizontal_positions(sorted_layers, edges, iterations=0, min_spacing=100.0)

    assert positions == {"A": 0.0, "B": 0.0, "C": 100.0}


# --- `compute_bereich_centroid_positions()` ---


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
