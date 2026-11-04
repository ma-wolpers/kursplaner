"""Farbtöne der Einheitstypen (Ausfall, LZK, Hospitation) – einzige Quelle.

Grid-Spaltenköpfe, Zellen, ausgeblendete-Spalten-Marker, Auswahl-Kopfzeilen und
die Sequenzleiter färben Termine eines Typs identisch. Die Werte gehen als
Token/Seed an die bw-gui-Tint-Helfer (kein Hex im Consumer); ein Theme-Wechsel
färbt dadurch automatisch um.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from bw_gui.theming import canvas_tinted_fill, theme_label_tinted, theme_text_tinted

from kursplaner.adapters.gui.ui_theme import HOSPITATION_SEED

KIND_AUSFALL = "ausfall"
KIND_LZK = "lzk"
KIND_HOSPITATION = "hospitation"


@dataclass(frozen=True)
class LessonKindTint:
    """Tint eines Einheitstyps.

    Attributes:
        color_tint: Token oder Seed-Farbe, die eingemischt wird.
        degree: Stärke der Tönung.
        base_token: Neutrale Basis.
        fg_token: Schrift-Token (``None`` = Standard-Kontrast der bw-gui-Helfer).
        label: Kurzes Typ-Label für Beschriftungen (z. B. in der Sequenzleiter).
    """

    color_tint: str
    degree: float
    base_token: str
    fg_token: str | None
    label: str

    def muted(self) -> LessonKindTint:
        """Gleicher Farbton mit gedämpfter Schrift (gesperrte/maskierte Zellen)."""
        return replace(self, fg_token="fg_muted")


LESSON_KIND_TINTS: dict[str, LessonKindTint] = {
    KIND_AUSFALL: LessonKindTint("warning_soft", 0.72, "panel_strong", "fg_muted", "Ausfall"),
    KIND_LZK: LessonKindTint("success_soft", 0.72, "panel_strong", None, "LZK"),
    KIND_HOSPITATION: LessonKindTint(HOSPITATION_SEED, 0.38, "panel_strong", None, "Hosp."),
}


def _fg(tint: LessonKindTint) -> dict[str, str]:
    return {"fg_token": tint.fg_token} if tint.fg_token else {}


def apply_label_tint(label: Any, tint: LessonKindTint) -> None:
    """Färbt ein Label im Typ-Farbton."""
    theme_label_tinted(label, tint.color_tint, degree=tint.degree, base_token=tint.base_token, **_fg(tint))


def apply_text_tint(widget: Any, tint: LessonKindTint) -> None:
    """Färbt ein Text-Widget im Typ-Farbton."""
    theme_text_tinted(widget, tint.color_tint, degree=tint.degree, base_token=tint.base_token, **_fg(tint))


def apply_canvas_tint(canvas: Any, item_id: int, tint: LessonKindTint) -> None:
    """Füllt ein Canvas-Item im Typ-Farbton."""
    canvas_tinted_fill(canvas, item_id, color_tint=tint.color_tint, degree=tint.degree, base_token=tint.base_token)
