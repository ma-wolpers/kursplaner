from pathlib import Path


def test_vertical_canvas_calls_are_centralized_in_viewport_sync():
    root = Path(__file__).resolve().parents[1]
    gui_dir = root / "kursplaner" / "adapters" / "gui"
    allowed = {"grid_viewport_sync.py"}
    forbidden = (
        "grid_canvas.yview(",
        "grid_canvas.yview_scroll(",
        "grid_canvas.yview_moveto(",
        "fixed_canvas.yview(",
        "fixed_canvas.yview_scroll(",
        "fixed_canvas.yview_moveto(",
    )

    violations: list[str] = []
    for path in gui_dir.glob("*.py"):
        if path.name in allowed:
            continue
        content = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in content:
                violations.append(f"{path.name}: {token}")

    assert not violations, "Direct vertical canvas calls found outside viewport sync: " + "; ".join(violations)
