from kursplaner.adapters.gui.kompetenzgraph_canvas_colors import assign_bereich_hues, hue_to_color_pair


def test_assign_bereich_hues_is_order_independent_and_covers_full_circle():
    hues = assign_bereich_hues(["I-C", "I-A", "I-B"])

    assert set(hues.keys()) == {"I-A", "I-B", "I-C"}
    assert hues == assign_bereich_hues(["I-A", "I-B", "I-C"])  # Eingabereihenfolge irrelevant, nur die Menge zaehlt
    assert all(0.0 <= hue < 360.0 for hue in hues.values())


def test_assign_bereich_hues_empty_input_returns_empty_dict():
    assert assign_bereich_hues([]) == {}


def test_hue_to_color_pair_returns_valid_hex_pair():
    light, dark = hue_to_color_pair(120.0)

    assert light.startswith("#") and len(light) == 7
    assert dark.startswith("#") and len(dark) == 7


def test_muted_variant_differs_from_primary_variant():
    primary = hue_to_color_pair(200.0)
    muted = hue_to_color_pair(200.0, muted=True)

    assert primary != muted


def test_same_hue_is_stable_across_calls():
    assert hue_to_color_pair(45.0) == hue_to_color_pair(45.0)
