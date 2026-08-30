"""Tests für `DayColumn.is_valid_unterricht_file`/`stundentyp` als `cached_property`

(Kursplaner Item 3, Perf-Fix 2026-08-29).

Beweist über Aufruf-Zähler auf den zugrunde liegenden freien Funktionen
(`is_valid_unterricht_link`, `infer_stundentyp`), dass wiederholte Zugriffe
auf dieselbe `DayColumn`-Instanz tatsächlich gecacht werden, statt nur zu
prüfen, dass sich der zurückgegebene Wert nicht geändert hat (das würde auch
bei einer versehentlich uncached gebliebenen Property gelten). Prüft
zusätzlich, dass zwei *verschiedene* `DayColumn`-Instanzen (der Normalfall
nach einem echten Edit, s. `LoadPlanDetailUseCase.build_day_columns_incremental`)
unabhängig voneinander neu berechnen — der Cache ist Instanzzustand, kein
Modul-Global.
"""

from __future__ import annotations

import kursplaner.core.domain.day_column as day_column_module
from kursplaner.core.domain.lesson_yaml_policy import infer_stundentyp as real_infer_stundentyp
from tests.day_column_factory import make_day_column


def _make_call_counter(real_fn):
    calls: list = []

    def counting_fn(*args, **kwargs):
        calls.append((args, kwargs))
        return real_fn(*args, **kwargs)

    return counting_fn, calls


def test_is_valid_unterricht_file_computed_once_per_instance(monkeypatch, tmp_path):
    link = tmp_path / "Einheiten" / "stunde.md"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.write_text("---\nStundentyp: Unterricht\n---\n", encoding="utf-8")

    counting_fn, calls = _make_call_counter(day_column_module.is_valid_unterricht_link)
    monkeypatch.setattr(day_column_module, "is_valid_unterricht_link", counting_fn)

    day = make_day_column(datum="27-03-26", link=link)

    _ = day.is_valid_unterricht_file
    _ = day.is_valid_unterricht_file
    _ = day.is_valid_unterricht_file

    assert len(calls) == 1  # nicht 3 -- zweiter/dritter Zugriff kam aus dem Cache


def test_stundentyp_computed_once_even_when_read_by_multiple_derived_methods(monkeypatch, tmp_path):
    """`is_lzk()`/`is_hospitation()`/`is_unterricht()` lesen alle `self.stundentyp` --

    vor dem Fix hätte das dieselbe teure Berechnung (inkl. der `Path.exists()`-
    Prüfung in `is_valid_unterricht_file`) mehrfach ausgelöst.
    """
    link = tmp_path / "Einheiten" / "stunde.md"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.write_text("---\nStundentyp: LZK\n---\n", encoding="utf-8")

    exists_counting_fn, exists_calls = _make_call_counter(day_column_module.is_valid_unterricht_link)
    monkeypatch.setattr(day_column_module, "is_valid_unterricht_link", exists_counting_fn)
    typ_counting_fn, typ_calls = _make_call_counter(real_infer_stundentyp)
    monkeypatch.setattr(day_column_module, "infer_stundentyp", typ_counting_fn)

    day = make_day_column(datum="27-03-26", link=link, yaml={"Stundentyp": "LZK"})

    assert day.is_lzk() is True
    assert day.is_hospitation() is False
    assert day.is_unterricht() is False
    _ = day.stundentyp

    assert len(exists_calls) == 1
    assert len(typ_calls) == 1


def test_cache_is_per_instance_not_shared_across_columns(monkeypatch, tmp_path):
    link_a = tmp_path / "Einheiten" / "stunde-a.md"
    link_b = tmp_path / "Einheiten" / "stunde-b.md"
    for link, typ in ((link_a, "Unterricht"), (link_b, "LZK")):
        link.parent.mkdir(parents=True, exist_ok=True)
        link.write_text(f"---\nStundentyp: {typ}\n---\n", encoding="utf-8")

    day_a = make_day_column(row_index=0, datum="27-03-26", link=link_a, yaml={"Stundentyp": "Unterricht"})
    day_b = make_day_column(row_index=1, datum="28-03-26", link=link_b, yaml={"Stundentyp": "LZK"})

    assert day_a.stundentyp == "Unterricht"
    assert day_b.stundentyp == "LZK"  # eigener Cache-Eintrag, nicht durch day_a's Wert verfaelscht
    assert day_a.stundentyp == "Unterricht"  # weiterhin korrekt, kein Cross-Talk
