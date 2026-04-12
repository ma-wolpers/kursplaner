from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnVisibilitySettings:
    """Globale Anzeigeeinstellungen für Sichtbarkeit und Marker je Spaltenart."""

    hide_unterricht: bool = False
    hide_lzk: bool = False
    hide_ausfall: bool = False
    hide_hospitation: bool = False
    hide_leer: bool = False
    hint_unterricht: bool = False
    hint_lzk: bool = False
    hint_ausfall: bool = False
    hint_hospitation: bool = False
    hint_leer: bool = False


@dataclass(frozen=True)
class ColumnVisibilityProjectionResult:
    """Ergebnis der Projektion für die Detailansicht."""

    visible_day_columns: list[dict[str, object]]


class ColumnVisibilityProjectionUseCase:
    """Projiziert geladene Tages-Spalten anhand von Sichtbarkeitsregeln."""

    KIND_UNTERRICHT = "unterricht"
    KIND_LZK = "lzk"
    KIND_AUSFALL = "ausfall"
    KIND_HOSPITATION = "hospitation"
    KIND_LEER = "leer"

    def project(
        self,
        *,
        day_columns: list[dict[str, object]],
        settings: ColumnVisibilitySettings,
    ) -> ColumnVisibilityProjectionResult:
        """Filtert Spaltenarten und markiert ausgeblendete Läufe für die Anzeige."""
        visible: list[dict[str, object]] = []
        pending_hidden_kinds: list[str] = []

        for day in day_columns:
            kind = self._kind_for_day(day)
            if self._is_hidden(kind, settings):
                if self._show_hint(kind, settings) and kind not in pending_hidden_kinds:
                    pending_hidden_kinds.append(kind)
                continue

            projected_day = dict(day)
            projected_day["hidden_kinds_before"] = tuple(pending_hidden_kinds)
            pending_hidden_kinds = []
            visible.append(projected_day)

        return ColumnVisibilityProjectionResult(visible_day_columns=visible)

    @classmethod
    def _kind_for_day(cls, day: dict[str, object]) -> str:
        if bool(day.get("is_cancel", False)):
            return cls.KIND_AUSFALL
        if bool(day.get("is_hospitation", False)):
            return cls.KIND_HOSPITATION
        if bool(day.get("is_lzk", False)):
            return cls.KIND_LZK
        if cls._is_empty_day(day):
            return cls.KIND_LEER
        return cls.KIND_UNTERRICHT

    @staticmethod
    def _is_empty_day(day: dict[str, object]) -> bool:
        inhalt = str(day.get("inhalt", "")).strip()
        has_link = day.get("link") is not None
        yaml_obj = day.get("yaml")
        has_yaml_payload = isinstance(yaml_obj, dict) and bool(yaml_obj)
        return not inhalt and not has_link and not has_yaml_payload

    @classmethod
    def _is_hidden(cls, kind: str, settings: ColumnVisibilitySettings) -> bool:
        if kind == cls.KIND_UNTERRICHT:
            return settings.hide_unterricht
        if kind == cls.KIND_LZK:
            return settings.hide_lzk
        if kind == cls.KIND_AUSFALL:
            return settings.hide_ausfall
        if kind == cls.KIND_HOSPITATION:
            return settings.hide_hospitation
        if kind == cls.KIND_LEER:
            return settings.hide_leer
        return False

    @classmethod
    def _show_hint(cls, kind: str, settings: ColumnVisibilitySettings) -> bool:
        if kind == cls.KIND_UNTERRICHT:
            return settings.hint_unterricht
        if kind == cls.KIND_LZK:
            return settings.hint_lzk
        if kind == cls.KIND_AUSFALL:
            return settings.hint_ausfall
        if kind == cls.KIND_HOSPITATION:
            return settings.hint_hospitation
        if kind == cls.KIND_LEER:
            return settings.hint_leer
        return False
