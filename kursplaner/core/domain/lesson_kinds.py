"""Schlüssel der Terminarten einer Tagesspalte – einzige Quelle.

Ein Schlüssel ist der kleingeschriebene Stundentyp (`lesson_yaml_policy.LessonType`).
Welcher Typ eine Spalte hat, entscheidet allein `DayColumn.lesson_type()` (Rangfolge
Ausfall > Hospitation > LZK > YAML-Typ); `DayColumn.lesson_kind()` liefert den Schlüssel.
Zeilenmodi (`RowDisplayModeUseCase.MODE_*`), Spaltenausblendung
(`ColumnVisibilityProjectionUseCase.KIND_*`), Farbtöne (`lesson_kind_tints`),
Sprossenarten der Sequenzleiter (`RungKind`) und der Tageslog-Status verwenden genau
diese Werte.
"""

from __future__ import annotations

KIND_UNTERRICHT = "unterricht"
KIND_LZK = "lzk"
KIND_AUSFALL = "ausfall"
KIND_HOSPITATION = "hospitation"
