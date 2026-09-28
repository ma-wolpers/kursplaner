"""Stichtag eines Kompetenzhorizonts (KH): welche Unterrichtsstunden zeitlich einfließen.

Die fachliche Semantik "vor" vs. "bis einschließlich" steht hier explizit im
Code, statt in einem losen ``include_cutoff: bool`` an der Aufrufstelle:

* Ein KH zu einer **LZK** umfasst nur Stunden *vor* der LZK
  (`HorizonCutoff.before`) — die LZK selbst prüft ja erst ab.
* Ein KH ab einer **Unterrichtsspalte** ("Exportieren als…") umfasst die
  Stunden *bis einschließlich* dieser Stunde (`HorizonCutoff.up_to_and_including`).

**Datumslose Unterrichtsstunden** fließen nie ein (`admits(None)` ist
``False``): Ein KH ist zeitlich verankert, eine Stunde ohne Datum lässt sich
keinem Zeitraum zuordnen. Das ist bewusste Exportsemantik.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class HorizonCutoff:
    """Zeitliche Grenze eines Kompetenzhorizonts.

    Nicht direkt konstruieren, sondern über `before` bzw. `up_to_and_including`,
    damit die Semantik an der Aufrufstelle lesbar bleibt.

    Args:
        day: Das Datum der Anker-Einheit (LZK bzw. Unterrichtsstunde).
        includes_day: Ob Stunden genau an ``day`` noch einfließen.
    """

    day: date
    includes_day: bool

    @classmethod
    def before(cls, day: date) -> HorizonCutoff:
        """Nur Stunden strikt vor ``day`` (Anker ist eine LZK)."""
        return cls(day=day, includes_day=False)

    @classmethod
    def up_to_and_including(cls, day: date) -> HorizonCutoff:
        """Stunden bis einschließlich ``day`` (Anker ist eine Unterrichtsstunde)."""
        return cls(day=day, includes_day=True)

    def admits(self, lesson_date: date | None) -> bool:
        """Prüft, ob eine Stunde mit diesem Datum in den KH einfließt.

        Args:
            lesson_date: Datum der Stunde oder ``None`` (datumslos).

        Returns:
            ``False`` für datumslose Stunden, sonst der Vergleich mit dem Stichtag.
        """
        if lesson_date is None:
            return False
        if self.includes_day:
            return lesson_date <= self.day
        return lesson_date < self.day
