from __future__ import annotations

from pathlib import Path

import pytest

from kursplaner.core.config import school_wide_cancellations_store as store


@pytest.fixture(autouse=True)
def _isolate_override(monkeypatch, tmp_path):
    """Ersetzt die Override-Ablage durch ein In-Memory-Fake, damit Tests nie die echte ui_preferences.json beruehren."""
    state: dict[str, str] = {"value": ""}

    def fake_load() -> str:
        return state["value"]

    def fake_save(value: str) -> None:
        state["value"] = value.strip()

    monkeypatch.setattr(store, "load_school_wide_cancellations_path_override", fake_load)
    monkeypatch.setattr(store, "save_school_wide_cancellations_path_override", fake_save)

    default_path = tmp_path / "default" / "schulweite_ausfaelle.json"
    legacy_path = tmp_path / "legacy" / "schulweite_ausfaelle.json"
    monkeypatch.setattr(store, "_default_store_path", lambda: default_path)
    monkeypatch.setattr(store, "_LEGACY_STORE_PATH", legacy_path)

    yield {"default": default_path, "legacy": legacy_path, "state": state}


def test_empty_override_uses_default_path(_isolate_override):
    assert store._store_path() == _isolate_override["default"]


def test_legacy_default_is_migrated_and_removed(_isolate_override):
    legacy = _isolate_override["legacy"]
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text('{"entries": []}', encoding="utf-8")

    resolved = store._store_path()

    assert resolved == _isolate_override["default"]
    assert resolved.exists()
    assert resolved.read_text(encoding="utf-8") == '{"entries": []}'
    assert not legacy.exists()


def test_legacy_migration_skipped_if_default_already_has_data(_isolate_override):
    legacy = _isolate_override["legacy"]
    default = _isolate_override["default"]
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text('{"entries": ["old"]}', encoding="utf-8")
    default.parent.mkdir(parents=True, exist_ok=True)
    default.write_text('{"entries": ["new"]}', encoding="utf-8")

    store._store_path()

    assert legacy.exists()
    assert default.read_text(encoding="utf-8") == '{"entries": ["new"]}'


def test_set_store_path_override_copies_and_removes_old_file(_isolate_override, tmp_path):
    old_default = _isolate_override["default"]
    old_default.parent.mkdir(parents=True, exist_ok=True)
    old_default.write_text('{"entries": ["real-data"]}', encoding="utf-8")

    new_target = tmp_path / "custom" / "schulweite_ausfaelle.json"
    store.set_store_path_override(str(new_target))

    assert new_target.exists()
    assert new_target.read_text(encoding="utf-8") == '{"entries": ["real-data"]}'
    assert not old_default.exists()
    assert _isolate_override["state"]["value"] == str(new_target)


def test_set_store_path_override_keeps_old_path_when_target_unwritable(_isolate_override, monkeypatch):
    old_default = _isolate_override["default"]
    old_default.parent.mkdir(parents=True, exist_ok=True)
    old_default.write_text('{"entries": ["real-data"]}', encoding="utf-8")

    def _boom(*_args, **_kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(store.shutil, "copy2", _boom)

    with pytest.raises(RuntimeError):
        store.set_store_path_override(str(old_default.parent.parent / "unwritable" / "x.json"))

    # Override wurde nicht gespeichert, alter Pfad bleibt aktiv.
    assert _isolate_override["state"]["value"] == ""
    assert old_default.exists()


def test_set_store_path_override_empty_string_resets_to_default(_isolate_override):
    store.set_store_path_override("")
    assert _isolate_override["state"]["value"] == ""
    assert store._store_path() == _isolate_override["default"]


def test_set_store_path_override_same_path_is_noop_for_migration(_isolate_override):
    default = _isolate_override["default"]
    default.parent.mkdir(parents=True, exist_ok=True)
    default.write_text('{"entries": []}', encoding="utf-8")

    store.set_store_path_override(str(default))

    assert default.exists()
    assert _isolate_override["state"]["value"] == str(default)


def test_load_and_save_round_trip_uses_resolved_path(_isolate_override):
    entries = store.load_school_wide_cancellations()
    assert entries == []

    from datetime import date

    from kursplaner.core.domain.school_wide_cancellation import SchoolWideCancellationEntry

    entry = SchoolWideCancellationEntry(
        entry_id="abc",
        reason="Testtag",
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 1),
        grade_levels=frozenset({7}),
        created_at="2026-01-01T00:00:00",
    )
    store.save_school_wide_cancellations([entry])

    reloaded = store.load_school_wide_cancellations()
    assert len(reloaded) == 1
    assert reloaded[0].entry_id == "abc"
    assert _isolate_override["default"].exists()
