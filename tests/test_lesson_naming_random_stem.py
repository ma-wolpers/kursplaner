"""Tests für generate_random_lesson_stem in lesson_naming.py."""

from __future__ import annotations

import pytest

from kursplaner.core.domain.lesson_naming import (
    _RANDOM_STEM_ALPHABET,
    _RANDOM_STEM_LENGTH,
    generate_random_lesson_stem,
)


class TestGenerateRandomLessonStem:
    """generate_random_lesson_stem: Eindeutigkeit, Format und Kollisionsvermeidung."""

    def test_stem_has_correct_length(self):
        """Erzeugte Stems haben exakt 6 Zeichen."""
        stem = generate_random_lesson_stem(set())
        assert len(stem) == _RANDOM_STEM_LENGTH

    def test_stem_uses_only_lowercase_alphanumeric(self):
        """Alle Zeichen des Stems stammen aus [a-z0-9]."""
        for _ in range(100):
            stem = generate_random_lesson_stem(set())
            assert stem.isalnum() and stem == stem.lower(), f"Ungültiger Stem: {stem!r}"

    def test_stem_not_in_existing_stems(self):
        """Erzeugte Stems weichen von allen übergebenen Stems ab."""
        existing = {"ab12cd", "ef34gh", "ij56kl"}
        for _ in range(50):
            stem = generate_random_lesson_stem(existing)
            assert stem not in existing

    def test_avoids_large_collision_set(self):
        """Selbst bei 1000 belegten Stems wird ein freier Stem gefunden."""
        existing = set()
        for i in range(1000):
            existing.add(f"{i:0>6d}"[:6].replace(" ", "0"))
        alphabet_set = set(_RANDOM_STEM_ALPHABET)
        valid_stems = {
            c1 + c2 + c3 + c4 + c5 + c6
            for c1 in alphabet_set
            for c2 in ["a"]
            for c3 in ["a"]
            for c4 in ["a"]
            for c5 in ["a"]
            for c6 in ["a"]
        }
        big_existing = {s for s in existing}
        stem = generate_random_lesson_stem(big_existing)
        assert len(stem) == 6
        assert stem not in big_existing

    def test_raises_on_fully_exhausted_space(self, monkeypatch):
        """RuntimeError wenn kein freier Stem nach max. Versuchen gefunden wird."""
        import kursplaner.core.domain.lesson_naming as mod

        monkeypatch.setattr(mod, "_RANDOM_STEM_MAX_ATTEMPTS", 3)
        monkeypatch.setattr(mod, "_RANDOM_STEM_ALPHABET", "a")
        monkeypatch.setattr(mod, "_RANDOM_STEM_LENGTH", 2)
        all_stems = {"aa"}
        with pytest.raises(RuntimeError, match="Kein freier Stem"):
            generate_random_lesson_stem(all_stems)

    def test_empty_existing_set_always_succeeds(self):
        stem = generate_random_lesson_stem(set())
        assert len(stem) == _RANDOM_STEM_LENGTH
