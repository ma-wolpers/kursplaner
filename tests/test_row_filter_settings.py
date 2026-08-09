import json

import pytest

from kursplaner.core.config import ui_preferences_store
from kursplaner.core.usecases.row_display_mode_usecase import RowDisplayModeUseCase, RowFilterSettings


def test_default_row_filter_settings_uses_standard_mode_membership():
    use_case = RowDisplayModeUseCase()
    settings = RowFilterSettings()

    assert use_case.effective_modes_for_field("Oberthema", settings) == use_case.default_modes_for_field(
        "Oberthema"
    )
    assert use_case.effective_modes_for_field("inhalt", settings) == use_case.default_modes_for_field("inhalt")


def test_field_mode_override_replaces_default_membership():
    use_case = RowDisplayModeUseCase()
    settings = RowFilterSettings(field_mode_overrides={"Oberthema": frozenset({RowDisplayModeUseCase.MODE_AUSFALL})})

    assert use_case.effective_modes_for_field("Oberthema", settings) == frozenset({RowDisplayModeUseCase.MODE_AUSFALL})


def test_field_without_override_keeps_default_even_when_other_fields_are_overridden():
    use_case = RowDisplayModeUseCase()
    settings = RowFilterSettings(field_mode_overrides={"Oberthema": frozenset()})

    assert use_case.effective_modes_for_field("Stundenthema", settings) == use_case.default_modes_for_field(
        "Stundenthema"
    )


def test_row_filter_settings_is_immutable():
    settings = RowFilterSettings(field_mode_overrides={"Oberthema": frozenset()})

    with pytest.raises((AttributeError, TypeError)):
        settings.field_mode_overrides = {}


def test_save_and_load_row_filter_settings_roundtrip(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    expected = RowFilterSettings(
        field_mode_overrides={
            "Oberthema": frozenset({RowDisplayModeUseCase.MODE_AUSFALL}),
            "Stundenziel": frozenset(),
        }
    )
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


def test_load_row_filter_settings_returns_default_for_empty_payload(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    target.write_text(json.dumps({"row_filter": {}}), encoding="utf-8")
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    loaded = ui_preferences_store.load_row_filter_settings()

    assert loaded == RowFilterSettings()


def test_load_row_filter_settings_migrates_legacy_hidden_fields_format(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    target.write_text(
        json.dumps({"row_filter": {"hidden_fields": ["Oberthema", "Stundenziel"]}}), encoding="utf-8"
    )
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    loaded = ui_preferences_store.load_row_filter_settings()

    use_case = RowDisplayModeUseCase()
    assert use_case.effective_modes_for_field("Oberthema", loaded) == frozenset()
    assert use_case.effective_modes_for_field("Stundenziel", loaded) == frozenset()
    assert use_case.effective_modes_for_field("Stundenthema", loaded) == use_case.default_modes_for_field(
        "Stundenthema"
    )


def test_save_row_filter_settings_preserves_existing_keys(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    target.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    ui_preferences_store.save_row_filter_settings(
        RowFilterSettings(field_mode_overrides={"Oberthema": frozenset()})
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["theme"] == "dark"
    assert payload["row_filter"]["field_mode_overrides"]["Oberthema"] == []
