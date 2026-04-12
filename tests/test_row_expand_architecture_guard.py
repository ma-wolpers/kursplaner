from pathlib import Path


def test_row_expanded_mutations_are_centralized_in_intent_controller_and_renderer():
    root = Path(__file__).resolve().parents[1]
    gui_dir = root / "kursplaner" / "adapters" / "gui"
    allowed = {"ui_intent_controller.py", "grid_renderer.py"}
    forbidden = (
        "row_expanded[",
        "row_expanded.get(",
    )

    violations: list[str] = []
    for path in gui_dir.glob("*.py"):
        if path.name in allowed:
            continue
        content = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in content:
                violations.append(f"{path.name}: {token}")

    assert not violations, "Row expansion state used outside allowed modules: " + "; ".join(violations)
