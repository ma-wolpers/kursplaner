from pathlib import Path

from kursplaner.adapters.bootstrap import build_cli_dependencies
from kursplaner.core.config.path_store import CALENDAR_DIR_KEY, load_path_values, resolve_path_value
from kursplaner.core.config.settings import WEEKDAY_SHORT_OPTIONS
from kursplaner.core.domain.validators import (
    ValidationError,
    normalize_day_rhythm,
    parse_period_input,
)


def _ask(prompt: str) -> str:
    """Zeigt eine CLI-Frage und liefert die bereinigte Eingabe zurück."""
    print(prompt)
    return input("> ").strip()


_WEEK_CHOICES: dict[str, tuple[int | None, ...]] = {"": (None,), "g": (0,), "u": (1,), "gu": (0, 1)}
_PARITY_LABELS: dict[int | None, str] = {None: "", 0: "gerade KW", 1: "ungerade KW"}


def _ask_week_parities(short_label: str) -> tuple[int | None, ...]:
    """Fragt den Wochenmodus eines Tages ab, bis eine gueltige Eingabe vorliegt.

    Eingaben werden mit ``strip().lower()`` normalisiert: leer = jede Woche,
    ``g`` = gerade KW, ``u`` = ungerade KW, ``gu`` = A/B-Tag (beide Wochen mit
    eigener Startzeit/Stundenzahl).

    Returns:
        Die Paritaeten fuer ``normalize_day_rhythm`` (``None`` = jede Woche).
    """
    while True:
        choice = _ask(f"{short_label} Woche (leer = jede, g, u, gu):").lower()
        if choice in _WEEK_CHOICES:
            return _WEEK_CHOICES[choice]
        print("Ungültige Eingabe - bitte leer lassen oder g, u bzw. gu eingeben.")


def _confirm_fs_change(action: str, details: str = "") -> bool:
    """Fragt in der CLI eine explizite Bestätigung für Dateisystemänderungen ab."""
    print("\n[Dateisystem-Änderung]")
    print(action)
    if details.strip():
        print()
        print(details.strip())
    answer = input("Änderung wirklich durchführen? [j/N]: ").strip().lower()
    return answer in {"j", "ja", "y", "yes"}


def main():
    """Führt den interaktiven CLI-Flow zum Erstellen eines Terminplans aus."""
    try:
        dependencies = build_cli_dependencies()
        calendar_repo = dependencies.calendar_repo
        create_plan_usecase = dependencies.create_plan_usecase
        path_values = load_path_values()
        default_calendar_dir = resolve_path_value(path_values[CALENDAR_DIR_KEY])

        period_raw = _ask("Halbjahr ODER Startdatum (z. B. 26-1 oder 2026-02-20):")
        term, start_date, is_date_mode = parse_period_input(period_raw)

        day_rhythm_input: dict[tuple[int, int | None], tuple[str, str]] = {}
        print("Rhythmus pro Tag (Mo-Fr), Stunden leer lassen = kein Termin:")
        for short_label, weekday in WEEKDAY_SHORT_OPTIONS:
            parities = _ask_week_parities(short_label)
            for parity in parities:
                label = short_label if len(parities) == 1 else f"{short_label} {_PARITY_LABELS[parity]}"
                hours_value = _ask(f"{label} Stunden (1-4):")
                start_value = _ask(f"{label} Startzeit (HH:MM):") if hours_value.strip() else ""
                day_rhythm_input[(weekday, parity)] = (start_value, hours_value)
        rhythm = normalize_day_rhythm(day_rhythm_input)

        target_file_raw = _ask("Markdown-Zieldatei (voller Pfad oder relativ):")
        target_markdown = Path(target_file_raw).expanduser().resolve()

        calendar_raw = _ask(f"Kalenderordner mit ICS-Dateien (Enter für Default: {default_calendar_dir}):")
        calendar_dir = resolve_path_value(calendar_raw) if calendar_raw else default_calendar_dir

        if is_date_mode:
            if start_date is None:
                raise ValidationError("Startdatum fehlt.")
            term = calendar_repo.infer_term_from_date(start_date, calendar_dir)
            stop_at_next_break = True
            takeover_start = start_date
        else:
            if term is None:
                raise ValidationError("Halbjahr fehlt.")
            stop_at_next_break = False
            takeover_start = None

        result = create_plan_usecase.execute(
            target_markdown=target_markdown,
            term=term,
            rhythm=rhythm,
            calendar_dir=calendar_dir,
            takeover_start=takeover_start,
            stop_at_next_break=stop_at_next_break,
            confirm_change=_confirm_fs_change,
        )

    except (ValidationError, FileNotFoundError, RuntimeError) as exc:
        raise SystemExit(f"Fehler: {exc}")

    print("Terminplan wurde angehängt.")
    print(f"Halbjahr: {term}")
    print(f"Zeitraum: {result.range_start} bis {result.range_end}")
    print(f"Zeilen: {result.rows_count}")
    if result.warnings:
        print("Warnungen:")
        for warning in result.warnings:
            print(f"- {warning}")
