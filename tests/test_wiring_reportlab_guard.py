"""Regressionstests fuer die optionale `reportlab`-Abhaengigkeit in der Composition Root.

`reportlab` bleibt Teil von `requirements.txt` und wird normal mitinstalliert --
diese Tests decken nur die Laufzeit-Robustheit ab, falls es in einer konkreten
Umgebung dennoch fehlt (siehe `docs/DEVELOPMENT_LOG.md`).
"""

from kursplaner.adapters.bootstrap import wiring


def test_build_gui_dependencies_disables_only_pdf_dependent_usecases_without_reportlab(monkeypatch):
    monkeypatch.setattr(wiring, "REPORTLAB_AVAILABLE", False)

    deps = wiring.build_gui_dependencies()

    assert deps.export_topic_units_pdf_usecase is None
    assert deps.export_expected_horizon_pdf_usecase is None
    assert deps.export_lzk_expected_horizon_usecase is None
    assert deps.export_achievements_report_pdf_usecase is None

    # Die Markdown-Gegenstuecke haengen nicht an reportlab und bleiben verfuegbar.
    assert deps.export_topic_units_markdown_usecase is not None
    assert deps.export_expected_horizon_markdown_usecase is not None


def test_build_gui_dependencies_wires_pdf_usecases_when_reportlab_available(monkeypatch):
    monkeypatch.setattr(wiring, "REPORTLAB_AVAILABLE", True)

    deps = wiring.build_gui_dependencies()

    assert deps.export_topic_units_pdf_usecase is not None
    assert deps.export_expected_horizon_pdf_usecase is not None
    assert deps.export_lzk_expected_horizon_usecase is not None
    assert deps.export_achievements_report_pdf_usecase is not None
