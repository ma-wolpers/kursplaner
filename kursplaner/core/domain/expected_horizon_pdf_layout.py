"""Layout-Optionen des PDF-Kompetenzhorizonts (pro Export im Themendialog gewählt).

Reine Darstellungswahl ohne fachliche Wirkung auf Sections/Zeilen: Der
Markdown-Export ignoriert sie (er hat mit ``Aufg`` ohnehin eine Aufgaben-Spalte).
Die Grenzen der Schriftgröße liegen hier, damit Dialog (Zahlbox) und Renderer
dieselben Werte verwenden.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_FONT_SIZE = 9.5
"""Bisherige feste Schriftgröße der Tabellenzellen (pt) — Vorbelegung im Dialog."""

MIN_FONT_SIZE = 6.0
MAX_FONT_SIZE = 16.0
FONT_SIZE_STEP = 0.5


def clamp_font_size(value: float) -> float:
    """Begrenzt eine Schriftgröße auf den erlaubten Bereich.

    Args:
        value: Gewünschte Schriftgröße in pt.

    Returns:
        ``value`` auf ``[MIN_FONT_SIZE, MAX_FONT_SIZE]`` begrenzt.
    """
    return min(MAX_FONT_SIZE, max(MIN_FONT_SIZE, float(value)))


@dataclass(frozen=True)
class ExpectedHorizonPdfLayout:
    """Darstellungsoptionen für das KH-PDF.

    Attributes:
        with_task_column: Hängt ganz rechts eine leere Spalte „Aufgaben“ an,
            breit genug für handschriftliche Einträge.
        font_size: Schriftgröße der Tabellenzellen in pt; Kopf- und
            Abschnittszeilen skalieren proportional mit. Wird beim Erzeugen
            auf den erlaubten Bereich begrenzt.
    """

    with_task_column: bool = False
    font_size: float = DEFAULT_FONT_SIZE

    def __post_init__(self) -> None:
        """Begrenzt ``font_size`` auf den erlaubten Bereich (frozen → via ``object.__setattr__``)."""
        object.__setattr__(self, "font_size", clamp_font_size(self.font_size))

    @property
    def scale(self) -> float:
        """Faktor gegenüber der Standardgröße (1.0 = bisheriges Layout)."""
        return self.font_size / DEFAULT_FONT_SIZE
