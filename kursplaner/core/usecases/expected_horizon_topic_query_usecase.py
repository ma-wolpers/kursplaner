"""Ermittelt die wählbaren Oberthemen für einen Kompetenzhorizont (KH) samt Vorbelegung.

Application-Schicht: Das Ergebnis ist eine Abfrage für genau einen Export
(Kandidaten, Vorbelegung, Warnungen) und kein fachliches Domain-Objekt. Die
fachlichen Bausteine (`HorizonCutoff`, `DayColumn.oberthema_state`) liegen in
der Domain.

Regeln:

* **Stichtag** aus dem Stundentyp der Anker-Spalte: LZK → `HorizonCutoff.before`,
  Unterricht → `HorizonCutoff.up_to_and_including`.
* **Kandidaten**: alle Oberthemen mit mindestens einer datierten
  Unterrichtsstunde, die der Stichtag zulässt (`raw_day_columns`, damit
  ausgeblendete Spalten nicht fehlen).
* **Chronologisch** heißt: sortiert nach dem ersten Auftreten im relevanten
  Zeitraum, d. h. nach ``(frühestes zugelassenes Datum, dessen row_index)``.
* **Vorbelegung**: bei einer LZK ihre gespeicherte Themenliste ∩ Kandidaten,
  sonst (oder bei leerer Liste) das Haupt-Oberthema der Anker-Spalte, falls
  es ein Kandidat ist.
* **Gespeichert, aber nicht verfügbar**: gültige gespeicherte Themen ohne
  Kandidat — nicht vorselektiert, als Warnung gemeldet, beim Export entfernt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.expected_horizon_cutoff import HorizonCutoff
from kursplaner.core.domain.oberthema_values import normalize_oberthemen
from kursplaner.core.domain.plan_table import parse_plan_row_date

_EXPORT_UNIT_TYPE = "Unterricht"
_ANCHOR_TYPES = {"Unterricht", "LZK"}


@dataclass(frozen=True)
class ExpectedHorizonTopicOption:
    """Ein wählbares Oberthema mit Zeitraum im relevanten Zeitraum.

    Args:
        oberthema: Entschlüsselter Thementext.
        first_date: Datum der ersten zugelassenen Unterrichtsstunde.
        last_date: Datum der letzten zugelassenen Unterrichtsstunde.
        unit_count: Anzahl zugelassener Unterrichtsstunden.
    """

    oberthema: str
    first_date: date
    last_date: date
    unit_count: int


@dataclass(frozen=True)
class ExpectedHorizonTopicOptions:
    """Ergebnis der Kandidatenabfrage für einen KH-Export.

    Args:
        anchor_row_index: Zeilenindex der Anker-Einheit.
        is_lzk_anchor: ``True``, wenn der Anker eine LZK ist (Auswahl wird dort gespeichert).
        cutoff: Stichtag des KH.
        options: Wählbare Themen in chronologischer Reihenfolge.
        preselected: Vorbelegte Themen (Teilmenge von ``options``, chronologisch).
        stored: Bei einer LZK die gespeicherte, bereinigte Themenliste; sonst leer.
        unavailable_stored: Gespeicherte, gültige Themen ohne Kandidat.
        invalid_unit_count: Zugelassene Unterrichtsstunden mit ungültigem Oberthema
            (nicht angeboten, als Warnung gemeldet).
    """

    anchor_row_index: int
    is_lzk_anchor: bool
    cutoff: HorizonCutoff
    options: tuple[ExpectedHorizonTopicOption, ...]
    preselected: tuple[str, ...]
    stored: tuple[str, ...]
    unavailable_stored: tuple[str, ...]
    invalid_unit_count: int

    @property
    def option_topics(self) -> tuple[str, ...]:
        """Die Themen aller Optionen in chronologischer Reihenfolge."""
        return tuple(option.oberthema for option in self.options)

    def ordered_selection(self, selection: Iterable[str]) -> tuple[str, ...]:
        """Normalisiert eine Auswahl: duplikatfrei, nur Kandidaten, chronologisch sortiert.

        Args:
            selection: Rohe Auswahl (z. B. aus dem Dialog).

        Returns:
            Die bereinigte Auswahl in der Reihenfolge von `options`; das erste
            Element ist damit das Haupt-Oberthema.
        """
        chosen = set(normalize_oberthemen(selection, ""))
        return tuple(topic for topic in self.option_topics if topic in chosen)


@dataclass
class _TopicSpan:
    first_date: date
    first_row_index: int
    last_date: date
    unit_count: int


class ExpectedHorizonTopicQueryUseCase:
    """Berechnet Stichtag, Kandidaten und Vorbelegung für einen KH-Export."""

    @staticmethod
    def _find_anchor(raw_day_columns: list[DayColumn], anchor_row_index: int) -> DayColumn:
        for day in raw_day_columns:
            if isinstance(day, DayColumn) and day.row_index == anchor_row_index:
                return day
        raise RuntimeError("Es ist keine gültige Einheit ausgewählt.")

    @staticmethod
    def _cutoff_for_anchor(anchor: DayColumn) -> HorizonCutoff:
        if anchor.stundentyp not in _ANCHOR_TYPES:
            raise RuntimeError("Ein Kompetenzhorizont ist nur für Unterrichts- oder LZK-Einheiten verfügbar.")
        anchor_date = parse_plan_row_date(anchor.datum)
        if anchor_date is None:
            raise RuntimeError("Die ausgewählte Einheit hat kein Datum; der Stichtag ist unbestimmt.")
        if anchor.is_lzk():
            return HorizonCutoff.before(anchor_date)
        return HorizonCutoff.up_to_and_including(anchor_date)

    @staticmethod
    def _collect_spans(raw_day_columns: list[DayColumn], cutoff: HorizonCutoff) -> tuple[dict[str, _TopicSpan], int]:
        spans: dict[str, _TopicSpan] = {}
        invalid_units = 0
        for day in raw_day_columns:
            if not isinstance(day, DayColumn) or day.stundentyp != _EXPORT_UNIT_TYPE:
                continue
            lesson_date = parse_plan_row_date(day.datum)
            if not cutoff.admits(lesson_date):
                continue
            assert lesson_date is not None  # admits() lässt datumslose Stunden nie zu
            if day.oberthema_state().is_invalid:
                invalid_units += 1
                continue
            for topic in day.oberthemen():
                span = spans.get(topic)
                if span is None:
                    spans[topic] = _TopicSpan(lesson_date, day.row_index, lesson_date, 1)
                    continue
                if (lesson_date, day.row_index) < (span.first_date, span.first_row_index):
                    span.first_date, span.first_row_index = lesson_date, day.row_index
                span.last_date = max(span.last_date, lesson_date)
                span.unit_count += 1
        return spans, invalid_units

    def query(self, *, raw_day_columns: list[DayColumn], anchor_row_index: int) -> ExpectedHorizonTopicOptions:
        """Liefert Kandidaten, Vorbelegung und Warnungen für die gewählte Anker-Einheit.

        Args:
            raw_day_columns: Vollständige, unprojizierte Tagesliste.
            anchor_row_index: Stabiler Zeilenindex der gewählten Einheit.

        Raises:
            RuntimeError: Bei ungültigem Anker (Typ, fehlendes Datum, ungültiges
                LZK-Oberthema) oder wenn es keine Kandidaten gibt.
        """
        anchor = self._find_anchor(raw_day_columns, anchor_row_index)
        cutoff = self._cutoff_for_anchor(anchor)
        is_lzk = anchor.is_lzk()
        anchor_state = anchor.oberthema_state()
        if is_lzk and anchor_state.is_invalid:
            raise RuntimeError("Das Oberthema der LZK hat ein ungültiges Format; bitte zuerst korrigieren.")

        spans, invalid_units = self._collect_spans(raw_day_columns, cutoff)
        if not spans:
            raise RuntimeError("Vor dem Stichtag gibt es keine datierten Unterrichtsstunden mit Oberthema.")
        ordered = sorted(spans.items(), key=lambda item: (item[1].first_date, item[1].first_row_index))
        options = tuple(
            ExpectedHorizonTopicOption(topic, span.first_date, span.last_date, span.unit_count)
            for topic, span in ordered
        )
        option_topics = {option.oberthema for option in options}

        stored = anchor_state.topics if is_lzk else ()
        preferred = stored or (anchor.oberthema(),)
        preselected = tuple(o.oberthema for o in options if o.oberthema in set(preferred))
        unavailable = tuple(topic for topic in stored if topic not in option_topics)

        return ExpectedHorizonTopicOptions(
            anchor_row_index=anchor_row_index,
            is_lzk_anchor=is_lzk,
            cutoff=cutoff,
            options=options,
            preselected=preselected,
            stored=tuple(stored),
            unavailable_stored=unavailable,
            invalid_unit_count=invalid_units,
        )
