from kursplaner.core.domain import kompetenzgraph_layout
from kursplaner.core.domain.kompetenzgraph_layout import (
    _BEREICH_SPACING,
    _build_bereich_classification_edges,
    compute_layered_layout,
)
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_ABHAENGIGKEITEN, MODE_OBER_TEIL
from tests.kompetenzgraph_test_support import make_bereich, make_node

_MAX_VERTICAL_JITTER = 20.0
"""Muss zum betragsmäßig größten Wert in `kompetenzgraph_layout.py::_VERTICAL_JITTER_PATTERN`
passen -- hier bewusst dupliziert statt importiert, damit ein Test fehlschlägt, falls die
Implementierung den Versatz je vergrößert, ohne dass die Schichtgrenzen-Sicherheitsmarge
(Tests unten) explizit gegengeprüft wird."""


def _diamond_snapshot():
    root = make_node("ROOT")
    a = make_node("A", oberkompetenzen_ids=("ROOT",))
    b = make_node("B", oberkompetenzen_ids=("ROOT",))
    leaf = make_node("LEAF", oberkompetenzen_ids=("A", "B"))
    return build_kompetenz_graph_snapshot([root, a, b, leaf], [])


def test_diamond_dag_gets_correct_layer_depths():
    """Y bleibt strikt die Hierarchieschicht -- ein kleiner kosmetischer Y-Versatz innerhalb
    einer Schicht (siehe `_VERTICAL_JITTER_PATTERN`) ist erlaubt, daher keine exakten
    Absolutwerte, sondern nur die relative Schicht-Reihenfolge wird geprüft."""
    snapshot = _diamond_snapshot()
    visible = frozenset({"ROOT", "A", "B", "LEAF"})

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible, frozenset())

    assert layout.positions["A"].y > layout.positions["ROOT"].y + _MAX_VERTICAL_JITTER
    assert layout.positions["LEAF"].y > layout.positions["A"].y + _MAX_VERTICAL_JITTER


def test_vertical_jitter_pattern_never_crosses_a_layer_boundary():
    """Harte Invariante, algebraisch geprüft: selbst der betragsmäßig größte Y-Versatz auf BEIDEN
    Seiten einer Schichtgrenze darf `_LAYER_SPACING` nicht aufzehren -- sonst könnte ein Knoten
    aus Schicht N tiefer erscheinen als einer aus Schicht N+1 ("höher/niedriger" würde mehrdeutig)."""
    max_jitter = max(abs(value) for value in kompetenzgraph_layout._VERTICAL_JITTER_PATTERN)

    assert kompetenzgraph_layout._LAYER_SPACING - 2 * max_jitter > 0


def test_diamond_layer_gap_leaves_a_visible_safety_margin_with_real_jitter():
    """Ergänzender End-zu-Ende-Check mit echten Knoten (mehrere pro Schicht, damit der Versatz
    tatsächlich zyklisch angewendet wird): die Schichten bleiben klar getrennt."""
    root = make_node("ROOT")
    children = [make_node(f"CHILD-{i}", oberkompetenzen_ids=("ROOT",)) for i in range(5)]
    snapshot = build_kompetenz_graph_snapshot([root, *children], [])
    visible = frozenset({"ROOT", *(c.id for c in children)})

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible, frozenset())

    root_y = layout.positions["ROOT"].y
    min_child_y = min(layout.positions[c.id].y for c in children)
    assert min_child_y > root_y


def test_layout_is_deterministic_across_repeated_calls():
    snapshot = _diamond_snapshot()
    visible = frozenset({"ROOT", "A", "B", "LEAF"})

    first = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible, frozenset())
    second = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible, frozenset())

    assert first.positions == second.positions


def test_cyclic_data_produces_complete_terminating_layout():
    node_a = make_node("A", oberkompetenzen_ids=("B",))
    node_b = make_node("B", oberkompetenzen_ids=("A",))
    snapshot = build_kompetenz_graph_snapshot([node_a, node_b], [])
    visible = frozenset({"A", "B"})

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible, frozenset())

    assert set(layout.positions.keys()) == {"A", "B"}


def test_bereich_hub_gets_fixed_row_independent_of_competency_layers():
    bereich = make_bereich("I-Test", kind="inhaltsbereich")
    node = make_node("A", primarer_bereich_id="I-Test")
    snapshot = build_kompetenz_graph_snapshot([node], [bereich])

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, frozenset({"A"}), frozenset({"I-Test"}))

    assert layout.positions["I-Test"].y != layout.positions["A"].y
    assert layout.positions["I-Test"].y < 0


def test_unresolved_link_marker_is_offset_from_referencing_node():
    bereich = make_bereich("I-Test", kind="inhaltsbereich")
    node = make_node("A", oberkompetenzen_ids=("NICHT-VORHANDEN",))
    snapshot = build_kompetenz_graph_snapshot([node], [bereich])

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, frozenset({"A"}), frozenset())

    assert len(layout.unresolved_marker_positions) == 1
    marker_position = next(iter(layout.unresolved_marker_positions.values()))
    node_position = layout.positions["A"]
    assert marker_position != node_position


def test_invisible_nodes_are_not_included_in_positions():
    snapshot = _diamond_snapshot()

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, frozenset({"ROOT", "A"}), frozenset())

    assert set(layout.positions.keys()) == {"ROOT", "A"}


def test_bereich_spacing_constant_stays_wider_than_render_width():
    """Bewusster Cross-Layer-Contract-Test: vergleicht absichtlich eine Domain-Konstante
    (`_BEREICH_SPACING`) mit einer GUI-Rendering-Konstante (`_BEREICH_WIDTH`) -- ein punktuell
    akzeptierter Layer-Übergriff nur im Test, KEIN Vorbild für Produktionscode (`kompetenzgraph_
    layout.py` importiert weiterhin nichts aus `adapters/gui`). Dokumentiert eine reale,
    unvermeidliche geometrische Vertragsbeziehung: der Domain-Layoutalgorithmus darf keine
    Bereich-Hub-Abstände erzeugen, die kleiner sind als die tatsächlich gerenderte Hub-Breite plus
    sichtbarer Mindestabstand. Ändert sich künftig eine der beiden Konstanten unabhängig von der
    anderen, schlägt dieser Test fehl, statt dass das Overlap-Problem unbemerkt wiederkehrt."""
    from kursplaner.adapters.gui.kompetenzgraph_canvas_render import _BEREICH_WIDTH

    assert _BEREICH_SPACING >= _BEREICH_WIDTH + 10.0


def test_bereich_hub_bounding_boxes_never_overlap():
    """Regressionstest für den realen Informatik-Bug: zwei Bereiche, deren klassifizierende
    Kompetenzen absichtlich nah beieinanderliegende X-Positionen haben, dürfen sich nicht näher
    kommen, als ihre tatsächliche Render-Breite erlaubt. Prüft die eigentliche
    Bounding-Box-Beziehung (alle Hubs teilen dieselbe feste Zeile `_BEREICH_ROW_Y`), nicht nur eine
    nackte Distanzzahl."""
    from kursplaner.adapters.gui.kompetenzgraph_canvas_render import _BEREICH_WIDTH

    bereich_a = make_bereich("I-A")
    bereich_b = make_bereich("I-B")
    nodes = [
        make_node("A1", primarer_bereich_id="I-A"),
        make_node("A2", primarer_bereich_id="I-A"),
        make_node("B1", primarer_bereich_id="I-B"),
        make_node("B2", primarer_bereich_id="I-B"),
    ]
    snapshot = build_kompetenz_graph_snapshot(nodes, [bereich_a, bereich_b])
    visible = frozenset(n.id for n in nodes)

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible, frozenset({"I-A", "I-B"}))

    boxes = {
        bid: (layout.positions[bid].x - _BEREICH_WIDTH / 2, layout.positions[bid].x + _BEREICH_WIDTH / 2)
        for bid in ("I-A", "I-B")
    }
    left_id, right_id = sorted(boxes, key=lambda bid: boxes[bid][0])
    assert boxes[left_id][1] <= boxes[right_id][0]


def test_prozessbereich_ids_never_influence_competency_positions():
    """Härtester Beweis der Trennung von Layoutkraft und Klassifikations-Rendering: zwei
    ansonsten identische Snapshots, die sich NUR in `prozessbereich_ids` eines Knotens
    unterscheiden (gleiche Hierarchie, gleiche `primarer_bereich_id`), müssen nach
    `compute_layered_layout()` exakt identische Kompetenz-Positionen liefern -- Prozessbereiche
    dürfen nachweislich in keinem Kraft-/Positionierungsschritt für Kompetenz-Knoten ankommen
    (Hub-Zentroide dürfen sich unterscheiden, das ist ausdrücklich weiterhin ihr Zweck)."""
    bereich_primary = make_bereich("I-Primary")
    bereich_prozess = make_bereich("P-Prozess", kind="prozessbereich")

    without_prozess = make_node("A", primarer_bereich_id="I-Primary")
    with_prozess = make_node("A", primarer_bereich_id="I-Primary", prozessbereich_ids=("P-Prozess",))

    snapshot_without = build_kompetenz_graph_snapshot([without_prozess], [bereich_primary, bereich_prozess])
    snapshot_with = build_kompetenz_graph_snapshot([with_prozess], [bereich_primary, bereich_prozess])

    layout_without = compute_layered_layout(
        snapshot_without, MODE_OBER_TEIL, frozenset({"A"}), frozenset({"I-Primary"})
    )
    layout_with = compute_layered_layout(
        snapshot_with, MODE_OBER_TEIL, frozenset({"A"}), frozenset({"I-Primary"})
    )

    assert layout_without.positions["A"] == layout_with.positions["A"]
    assert layout_without.positions["I-Primary"] == layout_with.positions["I-Primary"]


def test_bereich_classification_uses_primary_relationship_not_bereich_kind():
    """Primär/Sekundär ist eine Eigenschaft der BEZIEHUNG (welches Feld eine Kompetenz nutzt), NICHT
    eine Eigenschaft des Bereichs selbst (`BereichNode.kind`). Ein Bereich mit
    `kind="prozessbereich"` kann durchaus jemandes `primarer_bereich_id` sein ("primärer
    Prozessbereich") und muss dann ganz normal aus seinen Primärmitgliedern positioniert werden --
    ein früherer (verworfener) Fix-Versuch unterschied fälschlich nach `kind` des Hubs statt nach
    der tatsächlichen Beziehung. Ein Bereich, der NIE `primarer_bereich_id` ist (nur über
    `prozessbereich_ids` referenziert, hier "PURE-SECONDARY"), bekommt bewusst KEIN Signal aus
    dieser Sekundärbereich-Referenz -- explizite Nutzervorgabe, keine Lücke."""
    primary_prozessbereich = make_bereich("PP", kind="prozessbereich")
    inhaltsbereich = make_bereich("IB", kind="inhaltsbereich")
    pure_secondary = make_bereich("PURE-SECONDARY", kind="prozessbereich")

    node_a = make_node("A", primarer_bereich_id="PP")
    node_b = make_node("B", primarer_bereich_id="IB", prozessbereich_ids=("PURE-SECONDARY",))
    snapshot = build_kompetenz_graph_snapshot(
        [node_a, node_b], [primary_prozessbereich, inhaltsbereich, pure_secondary]
    )
    visible = frozenset({"A", "B"})
    visible_bereiche = frozenset({"PP", "IB", "PURE-SECONDARY"})

    edges = _build_bereich_classification_edges(snapshot, visible, visible_bereiche)

    assert edges["PP"] == ("A",)  # primärer Prozessbereich -- ganz normal aus seinem Primärmitglied
    assert edges["IB"] == ("B",)
    assert edges["PURE-SECONDARY"] == ()  # nie Primärbereich -- kein Ersatzsignal aus der Sekundärreferenz


def test_abhaengigkeiten_mode_layers_mixed_edge_types_consistently():
    """P-1 -> K-1 (Teilkompetenz, ueber umgedrehte oberkompetenzen) und K-1 -> V-1 (Voraussetzung)
    sind zwei verschiedene Kantentypen entlang EINES Pfades -- beide muessen in MODE_ABHAENGIGKEITEN
    zur selben, konsistent aufsteigenden Schichttiefe fuehren (P-1 ueber K-1 ueber V-1)."""
    parent = make_node("P-1")
    child = make_node("K-1", oberkompetenzen_ids=("P-1",), voraussetzungen_ids=("V-1",))
    voraussetzung = make_node("V-1")
    snapshot = build_kompetenz_graph_snapshot([parent, child, voraussetzung], [])
    visible = frozenset({"P-1", "K-1", "V-1"})

    layout = compute_layered_layout(snapshot, MODE_ABHAENGIGKEITEN, visible, frozenset())

    assert layout.positions["K-1"].y > layout.positions["P-1"].y + _MAX_VERTICAL_JITTER
    assert layout.positions["V-1"].y > layout.positions["K-1"].y + _MAX_VERTICAL_JITTER
