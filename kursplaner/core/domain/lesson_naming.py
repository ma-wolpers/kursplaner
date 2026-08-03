from __future__ import annotations

import random
import string
from datetime import datetime

from kursplaner.core.domain.plan_table import PlanTableData, sanitize_hour_title

_RANDOM_STEM_ALPHABET = string.digits + string.ascii_lowercase
_RANDOM_STEM_LENGTH = 6
_RANDOM_STEM_MAX_ATTEMPTS = 10_000


def parse_mmdd(date_text: str) -> str:
    """Konvertiert bekannte Datumsformate in den Dateiname-Token `mm-dd`."""
    raw = str(date_text or "").strip()
    if not raw:
        return "00-00"

    for pattern in ("%Y-%m-%d", "%d-%m-%y", "%d-%m-%Y", "%d.%m.%y", "%d.%m.%Y"):
        try:
            parsed = datetime.strptime(raw, pattern)
            return parsed.strftime("%m-%d")
        except ValueError:
            continue

    return "00-00"


def row_mmdd(table: PlanTableData, row_index: int) -> str:
    """Leitet fuer eine Tabellenzeile den `mm-dd`-Token aus der Datumsspalte ab."""
    header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
    idx_datum = header_map.get("datum")
    if idx_datum is None or not (0 <= row_index < len(table.rows)):
        return "00-00"
    row = table.rows[row_index]
    if idx_datum >= len(row):
        return "00-00"
    return parse_mmdd(row[idx_datum])


def generate_random_lesson_stem(existing_stems: set[str]) -> str:
    """Erzeugt einen eindeutigen 6-stelligen Zufalls-Stem für eine Stundendatei.

    Der Stem besteht ausschließlich aus Kleinbuchstaben und Ziffern (Alphabet:
    ``[a-z0-9]``, 36 Zeichen).  Bei 6 Stellen ergeben sich 36^6 ≈ 2,17 Mrd.
    mögliche Werte – selbst bei Tausenden bestehender Einheiten ist die
    Kollisionswahrscheinlichkeit vernachlässigbar gering.

    Kleinbuchstaben statt Großbuchstaben werden verwendet, weil Obsidian
    Wiki-Links case-sensitiv sein können und Kleinbuchstaben auf allen
    Dateisystemen (Linux, macOS, Windows) eindeutig sortiert werden.

    Args:
        existing_stems: Menge aller bereits vergebenen Stems (ohne Dateiendung),
            z. B. aus ``{p.stem for p in einheiten_dir.glob("*.md")}``.

    Returns:
        Stem-String der Form ``"md38md"`` (6 Zeichen aus ``[a-z0-9]``).

    Raises:
        RuntimeError: Wenn nach :data:`_RANDOM_STEM_MAX_ATTEMPTS` Versuchen
            kein freier Stem gefunden wurde (praktisch nicht erreichbar).

    Example::

        stem = generate_random_lesson_stem({"ab12cd", "ef34gh"})
        assert len(stem) == 6
        assert stem.isalnum() and stem == stem.lower()
        assert stem not in {"ab12cd", "ef34gh"}
    """
    for _ in range(_RANDOM_STEM_MAX_ATTEMPTS):
        candidate = "".join(random.choices(_RANDOM_STEM_ALPHABET, k=_RANDOM_STEM_LENGTH))
        if candidate not in existing_stems:
            return candidate
    raise RuntimeError(
        f"Kein freier Stem nach {_RANDOM_STEM_MAX_ATTEMPTS} Versuchen. "
        "Zu viele Einheiten im Ordner?"
    )


def build_lesson_stem(group_name: str, date_mmdd: str, content_title: str) -> str:
    """Baut den kanonischen Dateistamm ``Lerngruppe mm-dd Inhalt``."""
    group = sanitize_hour_title(group_name) or "gruppe"
    mmdd = sanitize_hour_title(date_mmdd) or "00-00"
    content = sanitize_hour_title(content_title) or "einheit"
    return f"{group} {mmdd} {content}".strip()
