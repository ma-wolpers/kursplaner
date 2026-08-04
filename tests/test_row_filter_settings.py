import json

import pytest

from kursplaner.core.config import ui_preferences_store
from kursplaner.core.usecases.row_display_mode_usecase import RowFilterSettings


def test_default_row_filter_settings_shows_all_fields():
    settings = RowFilterSettings()

    assert settings.is_visible("Oberthema") is True
    assert settings.is_visible("Stundenthema") is True
    assert settings.is_visible("inhalt") is True


def test_hidden_field_is_not_visible():
    settings = RowFilterSettings(hidden_fields=frozenset({"Oberthema"}))

    assert settings.is_visible("Oberthema") is False


def test_non_hidden_field_is_visible_even_when_other_fields_are_hidden():
    settings = RowFilterSettings(hidden_fields=frozenset({"Oberthema"}))

    assert settings.is_visible("Stundenthema") is True
    assert settings.is_visible("Stundenziel") is True


def test_row_filter_settings_is_immutable():
    settings = RowFilterSettings(hidden_fields=frozenset({"Oberthema"}))

    with pytest.raises((AttributeError, TypeError)):
        settings.hidden_fields = frozenset()


def test_save_and_load_row_filter_settings_roundtrip(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    expected = RowFilterSettings(hidden_fields=frozenset({"Oberthema", "Stundenziel"}))
    ui_preferences_store.save_row_filter_settings(expected)
    loaded = ui_preferences_store.load_row_filter_settings()

    assert loaded == expected


def test_load_row_filter_settings_returns_default_when_file_missing(tmp_path, monkeypatch):
    target = tmp_path / "nonexistent.json"
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    loaded = ui_preferences_store.load_row_filter_settings()

    assert loaded == RowFilterSettings()


def test_load_row_filter_settings_returns_default_for_corrupt_payload(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    target.write_text(json.dumps({"row_filter": "invalid"}), encoding="utf-8")
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    loaded = ui_preferences_store.load_row_filter_settings()

    assert loaded == RowFilterSettings()


def test_load_row_filter_settings_returns_default_for_missing_hidden_fields_key(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    target.write_text(json.dumps({"row_filter": {}}), encoding="utf-8")
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    loaded = ui_preferences_store.load_row_filter_settings()

    assert loaded == RowFilterSettings()


def test_save_row_filter_settings_preserves_existing_keys(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    target.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    ui_preferences_store.save_row_filter_settings(RowFilterSettings(hidden_fields=frozenset({"Oberthema"})))

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["theme"] == "dark"
    assert "Oberthema" in payload["row_filter"]["hidden_fields"]
