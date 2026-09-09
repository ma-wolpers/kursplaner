from __future__ import annotations

import colorsys
from collections.abc import Iterable

_PRIMARY_SATURATION = 0.55
_PRIMARY_VALUE_LIGHT = 0.62
_PRIMARY_VALUE_DARK = 0.82

_MUTED_SATURATION = 0.28
_MUTED_VALUE_LIGHT = 0.85
_MUTED_VALUE_DARK = 0.45


def assign_bereich_hues(bereich_ids: Iterable[str]) -> dict[str, float]:
    """Weist jeder Bereichs-ID einen festen Farbton (0-360°) zu -- Gruppierungshilfe, keine Eindeutigkeitsgarantie.

    Deterministisch nach sortierter ID-Reihenfolge gleichmäßig über den
    Farbkreis verteilt. Absichtlich einfach gehalten: Ziel ist eine
    grobe visuelle Gruppierung ("das gehört zusammen"), kein Anspruch
    auf für beliebig viele Bereiche eindeutig unterscheidbare Farben.

    Muss über **alle** `snapshot.bereiche`-IDs (nicht nur die aktuell
    sichtbaren) aufgerufen werden, damit ein Bereich beim Filtern nie
    die Farbe wechselt -- siehe `KompetenzGraphUiState.bereich_hues`.

    Args:
        bereich_ids: Alle Bereichs-IDs des aktuellen Snapshots.

    Returns:
        Bereichs-ID → Farbton in Grad [0, 360).
    """
    sorted_ids = sorted(bereich_ids)
    count = len(sorted_ids)
    if count == 0:
        return {}
    return {bereich_id: (index / count) * 360.0 for index, bereich_id in enumerate(sorted_ids)}


def _hsv_to_hex(hue_degrees: float, saturation: float, value: float) -> str:
    hue_fraction = (hue_degrees % 360.0) / 360.0
    red, green, blue = colorsys.hsv_to_rgb(hue_fraction, saturation, value)
    return f"#{round(red * 255):02X}{round(green * 255):02X}{round(blue * 255):02X}"


def hue_to_color_pair(hue: float, *, muted: bool = False) -> tuple[str, str]:
    """Wandelt einen Farbton in ein (Hell-Theme-Hex, Dunkel-Theme-Hex)-Paar für `canvas_domain_fill`/`canvas_domain_outline`.

    `muted=True` liefert eine deutlich blassere/entsättigte Variante --
    gedacht für Kontextknoten-Rahmen und die Bereichs-Hub-Füllung, damit
    die kräftige (Default-)Variante ausschließlich für Primärtreffer-
    Rahmen und Bereichs-Hub-Rahmen reserviert bleibt und die bestehende
    Kontext-Kennzeichnung (gedimmte Füllung/Text) nicht verwässert wird.

    Args:
        hue: Farbton in Grad [0, 360), z. B. aus `assign_bereich_hues`.
        muted: Ob die gedämpfte statt der kräftigen Variante geliefert
            werden soll.

    Returns:
        `(light_hex, dark_hex)` -- direkt als `light_color`/`dark_color`
        an `bw_gui.theming.canvas_domain_fill`/`canvas_domain_outline`
        übergebbar, die selbst die aktuelle Theme-Auswahl übernehmen.
    """
    saturation = _MUTED_SATURATION if muted else _PRIMARY_SATURATION
    light_value = _MUTED_VALUE_LIGHT if muted else _PRIMARY_VALUE_LIGHT
    dark_value = _MUTED_VALUE_DARK if muted else _PRIMARY_VALUE_DARK
    return _hsv_to_hex(hue, saturation, light_value), _hsv_to_hex(hue, saturation, dark_value)
