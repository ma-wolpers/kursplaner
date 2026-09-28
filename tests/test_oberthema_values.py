"""Tests für das zentrale Oberthema-Wertemodell (Parsen, Normalisieren, Lesen, Schreib-Invariante)."""

from __future__ import annotations

import pytest

from kursplaner.core.domain.oberthema_values import (
    OberthemaRepairRequired,
    UnsupportedOberthemaValue,
    canonical_oberthema_value,
    encode_oberthemen,
    ensure_oberthema_write_allowed,
    normalize_oberthemen,
    parse_oberthema_field,
    read_oberthema_state,
    read_yaml_oberthemen,
)
from kursplaner.core.domain.plan_table import read_yaml_oberthema
from kursplaner.core.domain.yaml_registry import RawYamlBlock


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, []),
        ("", []),
        ("   ", []),
        ("Potenzen", ["Potenzen"]),
        ("[[11.1 Potenzen]]", ["[[11.1 Potenzen]]"]),
        (["A", "B"], ["A", "B"]),
        ([], []),
    ],
)
def test_parse_accepts_supported_types(raw, expected):
    assert parse_oberthema_field(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        RawYamlBlock(("  foo: bar",)),
        "{foo: bar}",
        "[A, B]",
        ["A", 3],
        ["A", ["B"]],
        {"foo": "bar"},
        42,
        True,
    ],
)
def test_parse_rejects_unsupported_types_without_reinterpreting(raw):
    with pytest.raises(UnsupportedOberthemaValue):
        parse_oberthema_field(raw)


def test_normalize_decodes_links_trims_and_removes_empty_and_duplicates():
    entries = ["[[11.1 Potenzen]]", "  Potenzen ", "", "Exponential   funktionen", "[[11.1 Exponential funktionen]]"]

    assert normalize_oberthemen(entries, "[[11.1]]") == ["Potenzen", "Exponential funktionen"]


def test_encode_writes_group_prefixed_wiki_links_and_round_trips():
    encoded = encode_oberthemen(["Potenzen", "Potenzen", "Exponential"], "[[11.1]]")

    assert encoded == ["[[11.1 Potenzen]]", "[[11.1 Exponential]]"]
    assert normalize_oberthemen(encoded, "11.1") == ["Potenzen", "Exponential"]


def test_canonical_value_converts_legacy_scalar_to_list():
    assert canonical_oberthema_value("Potenzen", "11.1") == ["[[11.1 Potenzen]]"]
    assert canonical_oberthema_value("[[11.1 Potenzen]]", "11.1") == ["[[11.1 Potenzen]]"]
    assert canonical_oberthema_value("", "11.1") == []


def test_canonical_value_raises_for_unsupported_type():
    with pytest.raises(UnsupportedOberthemaValue):
        canonical_oberthema_value(RawYamlBlock(("  a: b",)), "11.1")


def test_state_distinguishes_empty_from_invalid():
    empty = read_oberthema_state({"Oberthema": []}, "11.1")
    invalid = read_oberthema_state({"Oberthema": RawYamlBlock(("  foo: bar",))}, "11.1")

    assert empty.topics == () and not empty.is_invalid
    assert invalid.topics == () and invalid.is_invalid
    assert invalid.invalid_raw == RawYamlBlock(("  foo: bar",))


def test_legacy_single_value_helper_returns_primary_topic():
    yaml_data = {"Oberthema": ["[[11.1 A]]", "[[11.1 B]]"]}

    assert read_yaml_oberthemen(yaml_data, "11.1") == ["A", "B"]
    assert read_yaml_oberthema(yaml_data, "11.1") == "A"
    assert read_yaml_oberthema({"Oberthema": RawYamlBlock(("  x: y",))}, "11.1") == ""


def test_write_guard_allows_everything_for_valid_on_disk_value():
    ensure_oberthema_write_allowed(["[[11.1 A]]"], [], repair=False)


def test_write_guard_allows_unchanged_invalid_value():
    block = RawYamlBlock(("  foo: bar",))

    ensure_oberthema_write_allowed(block, RawYamlBlock(("  foo: bar",)), repair=False)


def test_write_guard_blocks_silent_replacement_of_invalid_value():
    with pytest.raises(OberthemaRepairRequired):
        ensure_oberthema_write_allowed(RawYamlBlock(("  foo: bar",)), [], repair=False)


def test_write_guard_allows_explicit_repair():
    ensure_oberthema_write_allowed(RawYamlBlock(("  foo: bar",)), ["[[11.1 A]]"], repair=True)
