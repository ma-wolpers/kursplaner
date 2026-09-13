import itertools

from kursplaner.core.domain.kompetenzgraph_layout import compute_layered_layout
from kursplaner.core.domain.kompetenzgraph_layout_forces import (
    compute_bereich_centroid_positions,
    relax_horizontal_positions,
)
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_OBER_TEIL
from tests.kompetenzgraph_test_support import make_synthetic_informatik_like_snapshot

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


# --- Primärbereich-Kohäsion (`bereich_of_node`-Parameter von `relax_horizontal_positions()`) ---
#
# Verankert Filter-Waisen (Knoten, die durch eine Filteransicht ihre echten Hierarchie-Nachbarn
# verlieren und sonst an ihrer arbiträren Slot-Index-Position einfrieren würden) an einem aus den
# ANDEREN sichtbaren Mitgliedern desselben `primarer_bereich_id` geschätzten, EINMALIG vor der
# Sweep-Schleife fixierten Anker. Siehe die Konstanten-Docstrings in `kompetenzgraph_layout_forces.py`
# für die vollständige Herleitung inklusive des verworfenen, nachweislich instabilen
# live-peer-Mittelwert-Entwurfs (Übergangsmatrix-Eigenwert exakt 1.0 -> unbegrenzter Drift).


def test_node_without_primarer_bereich_id_is_bit_identical_to_no_cohesion_at_all():
    """Ein Knoten, der in `bereich_of_node` gar nicht vorkommt (kein `primarer_bereich_id`), darf
    durch die bloße Anwesenheit des Parameters für ANDERE Knoten nicht mitbeeinflusst werden."""
    sorted_layers = {0: ("PARENT",) + tuple(f"F-{i}" for i in range(5)), 1: ("NOBEREICH", "OTHER")}
    edges = {"NOBEREICH": ("PARENT",)}
    bereich_of_node = {"OTHER": "X"}  # NOBEREICH bewusst nicht in der Map

    with_dict = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=100.0, bereich_of_node=bereich_of_node)
    without_dict = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=100.0)

    assert with_dict["NOBEREICH"] == without_dict["NOBEREICH"]


def test_sole_visible_bereich_member_falls_back_cleanly_to_pure_hierarchy_target():
    """Regressionstest für den im Zuge dieser Änderung selbst gefundenen Bug: ein Knoten OHNE
    jeden sichtbaren Peer seines Bereichs darf NICHT zu seiner eigenen (Selbst-)Position gezogen
    werden -- `_estimate_bereich_anchor_positions()` schließt den Knoten selbst aus und liefert für
    einen alleinigen Bereichsträger deshalb GAR KEINEN Anker, nicht etwa `0.15`/`0.8` Richtung sich
    selbst. Der Knoten muss exakt auf seinem reinen Hierarchie-Ziel landen, obwohl er sowohl einen
    `primarer_bereich_id` als auch einen sichtbaren Hierarchie-Nachbarn hat."""
    sorted_layers = {0: ("FAR_PARENT",) + tuple(f"F-{i}" for i in range(20)), 1: ("SOLO",)}
    edges = {"SOLO": ("FAR_PARENT",)}
    bereich_of_node = {"SOLO": "Z"}  # einziger Träger von "Z" im gesamten Aufruf

    with_dict = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=100.0, bereich_of_node=bereich_of_node)
    without_dict = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=100.0)

    assert with_dict["SOLO"] == without_dict["SOLO"]


def test_filtering_a_bereich_group_down_to_one_visible_member_falls_back_to_hierarchy_target():
    """Der Fall, der den ursprünglichen Clutter-Bug ausgelöst hat: im Vollgraphen hat ein Knoten
    mehrere sichtbare Peers desselben Bereichs, eine Filteransicht reduziert die sichtbare Menge
    aber auf genau diesen einen Knoten. `bereich_of_node` wird pro `compute_layered_layout()`-Aufruf
    frisch aus der AKTUELL sichtbaren Menge gebaut (siehe `kompetenzgraph_layout.py`) -- der hier
    übergebene Dict enthält deshalb, wie in der gefilterten Ansicht, nur noch diesen einen Knoten
    für Bereich "X". Kein Anker verfügbar (peer_count < 2) -> reines Hierarchie-Ziel, kein Einfrieren
    an einer arbiträren Position mehr."""
    sorted_layers = {0: ("PARENT",) + tuple(f"F-{i}" for i in range(5)), 1: ("LONE_SURVIVOR",)}
    edges = {"LONE_SURVIVOR": ("PARENT",)}
    bereich_of_node = {"LONE_SURVIVOR": "X"}  # die früheren Peers sind schlicht nicht mehr in der Map

    with_dict = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=100.0, bereich_of_node=bereich_of_node)
    without_dict = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=100.0)

    assert with_dict["LONE_SURVIVOR"] == without_dict["LONE_SURVIVOR"]


def test_bereich_group_members_end_up_measurably_closer_together():
    """Drei sichtbare Knoten desselben Bereichs, ohne jede Hierarchiekante untereinander, mit weit
    auseinanderliegenden Elternteilen (drei unabhängige, weit gestreute Ein-Kind-Elternteile) --
    die Kohäsion zieht sie näher zueinander als ohne sie. Geprüft wird die Streuung (max-min der
    X-Werte, nicht die gerichtete Differenz N3-N1 -- bei dem seit der Vereinheitlichung starken
    Gewicht können sich N1/N3 in ihrer Reihenfolge um den gemeinsamen Anker herum vertauschen, eine
    gerichtete Differenz würde dann fälschlich negativ)."""
    layer0 = ("P1",) + tuple(f"F1-{i}" for i in range(9)) + ("P2",) + tuple(f"F2-{i}" for i in range(9)) + ("P3",)
    sorted_layers = {0: layer0, 1: ("N1", "N2", "N3")}
    edges = {"N1": ("P1",), "N2": ("P2",), "N3": ("P3",)}
    bereich_of_node = {"N1": "X", "N2": "X", "N3": "X"}

    without = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=10.0)
    with_cohesion = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=10.0, bereich_of_node=bereich_of_node)

    spread_without = max(without[n] for n in ("N1", "N2", "N3")) - min(without[n] for n in ("N1", "N2", "N3"))
    spread_with = max(with_cohesion[n] for n in ("N1", "N2", "N3")) - min(with_cohesion[n] for n in ("N1", "N2", "N3"))
    assert spread_with < spread_without * 0.5  # deutlich enger, nicht nur minimal


def test_hierarchy_connected_and_hierarchy_free_group_members_now_shift_comparably():
    """Regressionstest gegen die frühere Zwei-Stufen-Gewichtung: seit der Vereinheitlichung auf
    `_BEREICH_COHESION_WEIGHT` entscheidet Hierarchie-Nachbarschaft NICHT mehr über die Stärke des
    Zugs Richtung Bereichs-Anker -- genau das war die Root Cause des gemeldeten Symptoms (im
    ungefilterten Graphen hat fast jeder Knoten einen Hierarchie-Nachbarn, die frühere schwache
    Stufe griff also praktisch überall). MAIN hat einen echten Elternknoten, FARPEER keinen --
    beide teilen denselben Bereich und damit denselben Anker (die jeweils andere Startposition).
    Ein einziger Top-Down-Sweep (`iterations=1`) hält die Elternposition unverändert, sodass die
    Verschiebung ausschließlich den Gewichts-Effekt zeigt. 20 unbeteiligte Füllknoten zwischen MAIN
    und FARPEER halten den Anker-Abstand (1050px) groß gegenüber `min_spacing` (50px), damit
    `_resolve_min_spacing()`-Pooling die beiden Ziele nicht künstlich verzerrt."""
    layer1 = ("MAIN",) + tuple(f"FILL-{i}" for i in range(20)) + ("FARPEER",)
    sorted_layers = {0: ("STRONGPARENT",), 1: layer1}
    edges = {"MAIN": ("STRONGPARENT",)}  # FARPEER hat keinen sichtbaren Hierarchie-Nachbarn
    bereich_of_node = {"MAIN": "X", "FARPEER": "X"}

    with_cohesion = relax_horizontal_positions(sorted_layers, edges, iterations=1, min_spacing=50.0, bereich_of_node=bereich_of_node)
    without = relax_horizontal_positions(sorted_layers, edges, iterations=1, min_spacing=50.0)

    anchor_distance = without["FARPEER"] - without["MAIN"]  # 1050.0 -- der volle Anker-Abstand
    main_shift_fraction = abs(with_cohesion["MAIN"] - without["MAIN"]) / anchor_distance
    farpeer_shift_fraction = abs(with_cohesion["FARPEER"] - without["FARPEER"]) / anchor_distance

    # Beide klar Richtung Anker gezogen (nicht nur einer von beiden) UND ungefähr gleich stark --
    # keine große Diskrepanz mehr zwischen "mit" und "ohne" Hierarchie-Nachbarn.
    assert main_shift_fraction > 0.6
    assert farpeer_shift_fraction > 0.6
    assert abs(main_shift_fraction - farpeer_shift_fraction) < 0.05


def test_bereich_members_with_real_widely_separated_hierarchy_targets_still_cluster_strongly():
    """Direkter Regressionstest gegen das tatsächlich gemeldete Symptom: im UNGEFILTERTEN Graphen
    (keine Waisen, jeder Knoten hat einen echten, eigenen Elternknoten) sollen Mitglieder desselben
    Bereichs trotzdem sichtbar näher zusammenrücken als ihre jeweiligen Hierarchie-Ziele allein
    vorgeben würden -- das war mit der alten, an Hierarchie-Nachbarschaft gekoppelten Gewichtung
    (0.15 für praktisch jeden Knoten mit Elternteil) nicht der Fall und exakt das vom Nutzer als
    "immer noch krass durchmischt" gemeldete Verhalten. Vier Knoten desselben Bereichs, jeder mit
    einem eigenen, weit separierten Elternteil (kein gemeinsamer Elternteil, keine Filter-Waisen)."""
    layer0 = (
        ("PA",)
        + tuple(f"FA-{i}" for i in range(9))
        + ("PB",)
        + tuple(f"FB-{i}" for i in range(9))
        + ("PC",)
        + tuple(f"FC-{i}" for i in range(9))
        + ("PD",)
    )
    sorted_layers = {0: layer0, 1: ("A", "B", "C", "D")}
    edges = {"A": ("PA",), "B": ("PB",), "C": ("PC",), "D": ("PD",)}
    bereich_of_node = {"A": "X", "B": "X", "C": "X", "D": "X"}

    without_cohesion = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=10.0)
    with_cohesion = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=10.0, bereich_of_node=bereich_of_node)

    hierarchy_spread = max(without_cohesion[n] for n in "ABCD") - min(without_cohesion[n] for n in "ABCD")
    cohesion_spread = max(with_cohesion[n] for n in "ABCD") - min(with_cohesion[n] for n in "ABCD")
    assert cohesion_spread < hierarchy_spread * 0.3


def test_more_iterations_of_bereich_cohesion_stabilize_instead_of_drifting_further():
    """Konvergenznachweis für die Kohäsionskraft selbst -- analog zu
    `test_more_iterations_stabilize_instead_of_drifting_further`, aber mit `bereich_of_node`
    aktiviert. Dies ist der direkte Regressionstest gegen die während der Entwicklung gefundene,
    ECHTE Instabilität eines früheren (live-peer-Mittelwert-)Entwurfs: mit dem fixen Anker ist die
    Blend-Rekursion `x_{t+1} = a·x_t + c` mit konstantem `c` und `|a| < 1`, also nachweislich
    konvergent -- 6 und 40 Sweeps müssen exakt dasselbe Ergebnis liefern, nicht nur ein ähnliches."""
    sorted_layers = {0: ("P1", "P2", "P3", "P4", "P5", "P6"), 1: ("N1", "N2", "N3", "N4", "N5", "N6")}
    edges = {f"N{i}": (f"P{i}",) for i in range(1, 7)}
    bereich_of_node = {f"N{i}": "X" for i in range(1, 7)}  # alle sechs im selben Bereich

    positions_six = relax_horizontal_positions(sorted_layers, edges, iterations=6, min_spacing=100.0, bereich_of_node=bereich_of_node)
    positions_forty = relax_horizontal_positions(sorted_layers, edges, iterations=40, min_spacing=100.0, bereich_of_node=bereich_of_node)

    assert positions_six == positions_forty


def test_filtering_out_a_layer_clusters_orphaned_bereich_members_more_tightly_than_across_bereiche():
    """Integrationstest auf realistischer Skala (144 Knoten / 9 Bereiche / 6 Schichten, dieselbe
    Fixture wie der Gesamt-Pipeline-Smoke-Test), über die volle `compute_layered_layout()`-Pipeline
    -- nicht nur `relax_horizontal_positions()` isoliert. Eine ganze mittlere Schicht wird aus der
    sichtbaren Menge entfernt (genau der ursprünglich gemeldete Fall: ein Filter lässt Kinder ohne
    ihre echten Eltern zurück). Direkte Prüfung des eigentlichen Nutzerwunsches: Knoten desselben
    `primarer_bereich_id` liegen im Schnitt klar enger beieinander als Knoten verschiedener
    Bereiche -- statt einer bloßen "sieht weniger verstreut aus"-Behauptung."""
    snapshot = make_synthetic_informatik_like_snapshot()
    removed_layer_node_ids = {f"NODE-{i}" for i in range(48, 72)}  # dritte von sechs Schichten
    visible_node_ids = frozenset(snapshot.nodes.keys() - removed_layer_node_ids)
    visible_bereich_ids = frozenset(snapshot.bereiche.keys())

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible_node_ids, visible_bereich_ids)

    x_by_bereich: dict[str, list[float]] = {}
    for node_id in visible_node_ids:
        bereich_id = snapshot.nodes[node_id].primarer_bereich_id
        x_by_bereich.setdefault(bereich_id, []).append(layout.positions[node_id].x)

    intra_bereich_distances = [
        abs(a - b) for xs in x_by_bereich.values() if len(xs) >= 2 for a, b in itertools.combinations(xs, 2)
    ]
    inter_bereich_distances = [
        abs(a - b)
        for (_id1, xs1), (_id2, xs2) in itertools.combinations(x_by_bereich.items(), 2)
        for a, b in itertools.product(xs1[:5], xs2[:5])  # Stichprobe -- Paarzahl sonst quadratisch groß
    ]

    avg_intra = sum(intra_bereich_distances) / len(intra_bereich_distances)
    avg_inter = sum(inter_bereich_distances) / len(inter_bereich_distances)
    assert avg_intra < avg_inter * 0.5  # deutlich enger, nicht nur knapp kleiner
