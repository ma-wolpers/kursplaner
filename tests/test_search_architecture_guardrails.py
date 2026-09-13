"""Architektur-Smell-Tests aus dem Implementierungsplan (Kapselungs-Garantien).

Diese Tests prüfen keine Verhaltens-Logik, sondern strukturelle Invarianten,
die durch normale Verhaltens-Tests nicht erzwungen werden: dass die
Such-Overlay-View niemals direkt in Selection-Mutatoren eingreift, und dass
es für die Kompetenz-Markdown-Struktur genau eine interpretierende Quelle
gibt (siehe Implementierungsplan, Teil C Punkt 8 / Teil B Punkt 1).
"""

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

_FORBIDDEN_MUTATOR_CALLS = (
    "find_next(",
    "find_previous(",
    "set_selection_level(",
    "set_selected_cell(",
    "clear_selected_cell(",
    "close_detail_view(",
)


def test_search_overlay_view_has_no_direct_selection_mutator_calls():
    """Die View darf ausschließlich Intents auslösen -- niemals selbst entscheiden,
    was Enter/Umschalt+Enter bedeutet (siehe `SelectionLayerStack`)."""
    source = (_REPO_ROOT / "kursplaner" / "adapters" / "gui" / "search_overlay_view.py").read_text(encoding="utf-8")

    for forbidden in _FORBIDDEN_MUTATOR_CALLS:
        assert forbidden not in source, f"search_overlay_view.py darf '{forbidden}' nicht enthalten"


def test_only_one_module_interprets_kompetenz_markdown_structure():
    """Nur `kompetenzgraph_mapping.py` darf eine `## Beispiel`-erkennende Heading-Regex
    besitzen -- keine zweite, parallele Markdown-Interpretation nur für die Suche.

    Erwähnungen des WORTES "Beispiel" in Docstrings/UI-Texten (z. B. der
    Toggle-Box-Beschriftung) sind erlaubt und werden hier nicht geprüft --
    verboten ist ausschließlich eine eigene, `## Beispiel` erkennende
    `re.compile(...)`-Konstruktion außerhalb der einen autoritativen Quelle.
    """
    domain_dir = _REPO_ROOT / "kursplaner" / "core" / "domain"
    gui_dir = _REPO_ROOT / "kursplaner" / "adapters" / "gui"
    usecases_dir = _REPO_ROOT / "kursplaner" / "core" / "usecases"
    # Absichtlich NUR die "beispiel"-erkennende Konstruktion, nicht jede generische
    # Heading-Regex: `kompetenzgraph_bereich_mapping.py` hat legitim eine eigene
    # `_HEADING_RE` für die (unabhängige) Bereichs-Titel-Ableitung.
    heading_regex_pattern = re.compile(r"re\.compile\([^)]*[Bb]eispiel|_BEISPIEL_HEADING_TEXT\s*=")

    offending_files = []
    for directory in (domain_dir, gui_dir, usecases_dir):
        for path in directory.glob("*.py"):
            if path.name == "kompetenzgraph_mapping.py":
                continue
            if heading_regex_pattern.search(path.read_text(encoding="utf-8")):
                offending_files.append(path.name)

    assert offending_files == []


def test_kompetenz_text_search_index_uses_load_body_usecase_exclusively():
    """`KompetenzTextSearchIndex` darf Bodies ausschließlich über `LoadKompetenzNodeBodyUseCase`
    lesen -- kein eigenes `path.read_text()`/`open()` für Kompetenz-Dateien."""
    source = (
        _REPO_ROOT / "kursplaner" / "core" / "usecases" / "kompetenzgraph_text_search_usecase.py"
    ).read_text(encoding="utf-8")

    assert "LoadKompetenzNodeBodyUseCase" in source
    assert ".read_text(" not in source
    assert "open(" not in source
