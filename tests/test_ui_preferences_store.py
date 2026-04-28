import json
from datetime import time

from kursplaner.core.config import ui_preferences_store
from kursplaner.core.usecases.column_visibility_projection_usecase import ColumnVisibilitySettings


def test_theme_save_keeps_existing_column_visibility_payload(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    target.write_text(
        json.dumps(
            {
                "column_visibility": {
                    "hide_ausfall": True,
                    "hint_ausfall": True,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    ui_preferences_store.save_theme_key("forest")

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["theme"] == "forest"
    assert payload["column_visibility"]["hide_ausfall"] is True
    assert payload["column_visibility"]["hint_ausfall"] is True


def test_save_and_load_column_visibility_settings_roundtrip(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    expected = ColumnVisibilitySettings(
        hide_unterricht=True,
        hide_lzk=False,
        hide_ausfall=True,
        hide_hospitation=False,
        hide_leer=True,
        hint_unterricht=True,
        hint_lzk=False,
        hint_ausfall=True,
        hint_hospitation=False,
        hint_leer=True,
    )

    ui_preferences_store.save_column_visibility_settings(expected)
    loaded = ui_preferences_store.load_column_visibility_settings()

    assert loaded == expected


def test_load_column_visibility_settings_returns_defaults_for_invalid_payload(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    target.write_text(json.dumps({"column_visibility": "invalid"}), encoding="utf-8")
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    loaded = ui_preferences_store.load_column_visibility_settings()

    assert loaded == ColumnVisibilitySettings()


def test_save_and_load_ub_past_cutoff_time_roundtrip(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    ui_preferences_store.save_ub_past_cutoff_time(time(hour=16, minute=30))
    loaded = ui_preferences_store.load_ub_past_cutoff_time()

    assert loaded == time(hour=16, minute=30)


def test_load_ub_past_cutoff_time_falls_back_for_invalid_payload(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    target.write_text(json.dumps({"ub_past_cutoff_time": "invalid"}), encoding="utf-8")
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    loaded = ui_preferences_store.load_ub_past_cutoff_time()

    assert loaded == time(hour=15, minute=0)


def test_save_and_load_lesson_builder_field_settings_roundtrip(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    expected = ui_preferences_store.LessonBuilderFieldSettings(
        show_kompetenzen=False,
        show_stundenziel=True,
    )
    ui_preferences_store.save_lesson_builder_field_settings(expected)
    loaded = ui_preferences_store.load_lesson_builder_field_settings()

    assert loaded == expected


def test_load_lesson_builder_field_settings_defaults_for_invalid_payload(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    target.write_text(json.dumps({"lesson_builder_fields": "invalid"}), encoding="utf-8")
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)

    loaded = ui_preferences_store.load_lesson_builder_field_settings()

    assert loaded == ui_preferences_store.LessonBuilderFieldSettings()
