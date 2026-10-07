"""CLI-Abfrage des Wochenmodus (`_ask_week_parities`)."""

from __future__ import annotations

import builtins

import pytest

from kursplaner.adapters.cli import planer_cli


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("", (None,)), ("g", (0,)), (" U ", (1,)), ("GU", (0, 1))],
)
def test_week_choice_is_normalized(monkeypatch, answer, expected):
    monkeypatch.setattr(builtins, "input", lambda _prompt="": answer)
    assert planer_cli._ask_week_parities("Mo") == expected


def test_invalid_week_choice_is_asked_again(monkeypatch, capsys):
    answers = iter(["x", "ug", "u"])
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    assert planer_cli._ask_week_parities("Mo") == (1,)
    assert capsys.readouterr().out.count("Ungültige Eingabe") == 2
