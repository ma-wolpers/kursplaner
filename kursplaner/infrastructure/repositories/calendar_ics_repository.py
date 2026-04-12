from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path


def _classify_calendar_file(path: Path) -> tuple[str | None, int | None]:
    """Klassifiziert einen ICS-Dateinamen in Typ (Ferien/Feiertag) und Jahr."""
    name = path.name.lower()
    if "ferien" in name:
        kind = "ferien"
    elif "feiertag" in name:
        kind = "feiertag"
    else:
        kind = None

    year_match = re.search(r"(20\d{2})\.ics$", name)
    year = int(year_match.group(1)) if year_match else None
    return kind, year


def find_ics_files_for_years(calendar_dir: Path, years: set[int]) -> tuple[list[Path], list[str]]:
    """Lädt passende ICS-Dateien für gegebene Jahre und liefert Coverage-Warnungen."""
    if not calendar_dir.exists() or not calendar_dir.is_dir():
        raise FileNotFoundError(f"Kalenderordner fehlt oder ist ungültig: {calendar_dir}")

    files: list[Path] = []
    coverage = {(kind, year): False for kind in ("ferien", "feiertag") for year in years}

    for path in calendar_dir.iterdir():
        if path.suffix.lower() != ".ics":
            continue

        kind, year = _classify_calendar_file(path)
        if not kind or year is None:
            continue

        if year in years:
            files.append(path)
            coverage[(kind, year)] = True

    if not files:
        raise FileNotFoundError(f"Keine passenden ICS-Dateien in {calendar_dir} für Jahre {sorted(years)} gefunden.")

    warnings: list[str] = []
    now_year = date.today().year
    if now_year in years:
        has_current_year = any(re.search(rf"{now_year}\.ics$", file.name.lower()) for file in files)
        if not has_current_year:
            warnings.append(f"Warnung: Kein aktueller Ferien-/Feiertagskalender für {now_year} gefunden.")

    for year in sorted(years):
        if not coverage[("ferien", year)]:
            warnings.append(f"Warnung: Ferienkalender {year} fehlt.")
        if not coverage[("feiertag", year)]:
            warnings.append(f"Warnung: Feiertagskalender {year} fehlt.")

    return files, warnings


def load_events_from_ics_files(paths: list[Path]) -> tuple[dict[date, str], list[tuple[str, date, date]]]:
    """Parst Ereignisse und Ferien-/Feiertagsblöcke aus ICS-Dateien."""
    events: dict[date, str] = {}
    blocks: list[tuple[str, date, date]] = []

    for path in paths:
        with open(path, encoding="utf-8") as file:
            start = end = name = None

            for line in file:
                line = line.strip()

                if line.startswith("SUMMARY"):
                    name = line.split(":", 1)[1]

                elif line.startswith("DTSTART"):
                    start = datetime.strptime(line.split(":")[1][:8], "%Y%m%d").date()

                elif line.startswith("DTEND"):
                    end = datetime.strptime(line.split(":")[1][:8], "%Y%m%d").date()

                elif line == "END:VEVENT" and start and end and name:
                    blocks.append((name, start, end))
                    current = start
                    while current < end:
                        if current not in events:
                            events[current] = name
                        current += timedelta(days=1)
                    start = end = name = None

    return events, blocks
