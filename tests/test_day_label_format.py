"""Kurzes Tageslabel: eine Darstellungsregel für Grid-Kopf und Sequenzleiter."""

from __future__ import annotations

import pytest

from kursplaner.core.usecases.day_label_format import short_day_label


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("18-02-26", "Mi 18.02."),
        ("2026-11-03", "Di 03.11."),
        ("03.11.2026", "Di 03.11."),
        ("", ""),
        ("kaputt", "kaputt"),
    ],
)
def test_short_day_label(raw, expected):
    assert short_day_label(raw) == expected
