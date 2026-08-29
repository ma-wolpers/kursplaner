from pathlib import Path


def test_horizontal_canvas_calls_are_centralized_in_viewport_sync():
    root = Path(__file__).resolve().parents[1]
    gui_dir = root / "kursplaner" / "adapters" / "gui"
    allowed = {"grid_viewport_sync.py"}
    forbidden = (
        "grid_canvas.xview(",
        "grid_canvas.xview_scroll(",
        "grid_canvas.xview_moveto(",
        "header_canvas.xview(",
        "header_canvas.xview_scroll(",
        "header_canvas.xview_moveto(",
    )

    violations: list[str] = []
    for path in gui_dir.glob("*.py"):
        if path.name in allowed:
            continue
        content = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in content:
                violations.append(f"{path.name}: {token}")

    assert not violations, "Direct horizontal canvas calls found outside viewport sync: " + "; ".join(violations)
