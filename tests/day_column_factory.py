"""Test-Hilfsfunktion zum Bauen von `DayColumn`-Instanzen mit sinnvollen Defaults.

`DayColumn` hat keine synthetischen "setze diesen abgeleiteten Wert direkt"-Parameter
(z. B. kein `is_cancel=True`) — abgeleitete Felder wie `is_cancel()`/`stunden()`
werden bewusst nur aus den rohen Feldern berechnet, nie eigenständig gesetzt.
Tests, die z. B. eine Ausfall-Zeile brauchen, setzen daher `thema_ausfall="X Grund"`
(oder `yaml={"Stundentyp": "Ausfall"}`), nicht ein `is_cancel`-Flag direkt.
"""

from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.course_rhythm import WeekdayRhythm
from kursplaner.core.domain.day_column import DayColumn


def make_day_column(
    *,
    row_index: int = 0,
    datum: str = "",
    inhalt: str = "",
    thema_ausfall: str = "",
    link: Path | None = None,
    yaml: dict[str, object] | None = None,
    group_name: str = "",
    rhythm: tuple[WeekdayRhythm, ...] = (),
    hidden_kinds_before: tuple[str, ...] = (),
) -> DayColumn:
    """Baut ein `DayColumn` mit sinnvollen Leer-Defaults; Tests überschreiben nur, was sie brauchen."""
    return DayColumn(
        row_index=row_index,
        datum=datum,
        inhalt=inhalt,
        thema_ausfall=thema_ausfall,
        link=link,
        yaml=dict(yaml) if yaml else {},
        group_name=group_name,
        rhythm=rhythm,
        hidden_kinds_before=hidden_kinds_before,
    )
