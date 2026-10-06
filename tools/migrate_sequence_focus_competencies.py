"""Einmalige Migration: Sequenzdateien von ``Leitkompetenz`` (Text) auf ``Leitkompetenzen`` (Liste).

Hard Cut: Die App kennt ab dieser Version ausschließlich ``Leitkompetenzen``
(YAML-Liste). Dieses Werkzeug ist der **einzige** Ort, der den alten Key noch
kennt; es wird nach dem bestätigten Upgrade-Lauf wieder entfernt (die
Git-Historie bewahrt es). Es ist kein Laufzeit-Kompatibilitätspfad.

Regeln (konservativ, verlustfrei):

* Altwert Text → genau **ein** Eintrag (kein Split an ``,``/``;``);
  ``""`` oder Key ohne Wert (``null``, so schreibt Obsidian ein geleertes Feld)
  → leere Liste; Liste aus Texten → Einträge unverändert.
* Jeder neue Eintrag muss die Listen-Invariante erfüllen (siehe
  ``kursplaner/core/domain/list_cell_text.py``) — es wird **nichts** getrimmt,
  verworfen oder umgedeutet.
* Konflikt (Datei bleibt unverändert, Exit-Code ≠ 0) bei: nicht unterstütztem
  Typ (bool, Zahl, Datum, Mapping, Liste mit Nicht-Texten), Invariantenverstoß,
  doppeltem ``Leitkompetenz``/``Leitkompetenzen``, beiden Keys zugleich,
  eingerücktem Key, nicht parsebarem Frontmatter oder einer Abweichung
  zwischen Zeilen-Scan und YAML-Struktur.
* Übersprungen (unverändert): Datei mit nur ``Leitkompetenzen`` („bereits
  migriert“) und Datei mit **keinem** der beiden Keys („nicht betroffen“ —
  es wird nichts eingefügt).

Absicherung: Doppelte Keys erkennt ein eigener PyYAML-Loader (PyYAML lässt
sonst stillschweigend den letzten Wert gewinnen). Vor dem Schreiben wird das
neue Frontmatter erneut geladen und muss exakt dem alten ohne
``Leitkompetenz`` plus ``Leitkompetenzen`` entsprechen. Ersetzt wird nur der
Block des alten Keys; Body, alle anderen Zeilen, Zeilenenden und ein BOM
bleiben byteweise erhalten.

Usage (vom Repo-Wurzelverzeichnis; vorher den Vault sichern)::

    python -m tools.migrate_sequence_focus_competencies [--dry-run] [--no-archive] [--unterricht-dir PFAD]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from kursplaner.core.domain.list_cell_text import list_entry_violation
from kursplaner.core.domain.sequence_planning import SEQUENCE_YAML_FOCUS_COMPETENCIES_KEY
from kursplaner.core.domain.yaml_scalars import yaml_double_quote
from tools.vault_courses import iter_course_dirs, iter_sequence_files, resolve_unterricht_dir

OLD_KEY = "Leitkompetenz"
NEW_KEY = SEQUENCE_YAML_FOCUS_COMPETENCIES_KEY
_BOM = b"\xef\xbb\xbf"
_TOP_LEVEL_KEY_RE = re.compile(r"^(?P<key>[^\s#:\-][^:]*?)[ \t]*:(?:[ \t]|$)")

MIGRATED = "MIGRIERT"
SKIPPED_ALREADY = "ÜBERSPRUNGEN (bereits migriert)"
SKIPPED_NOT_AFFECTED = "ÜBERSPRUNGEN (nicht betroffen)"
CONFLICT = "KONFLIKT"


class DuplicateKeyError(yaml.YAMLError):
    """Ein Mapping enthält denselben Key mehrfach."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader, der doppelte Mapping-Keys ablehnt statt „letzter gewinnt“."""

    def construct_mapping(self, node, deep=False):  # type: ignore[override]
        """Baut ein Mapping und wirft bei einem doppelten Key.

        Args:
            node: Der YAML-Mapping-Knoten.
            deep: Siehe `yaml.SafeLoader.construct_mapping`.

        Returns:
            Das konstruierte Dict.

        Raises:
            DuplicateKeyError: Wenn ein Key mehrfach vorkommt.
        """
        seen: set[object] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise DuplicateKeyError(f"Doppelter Key '{key}'")
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


@dataclass(frozen=True)
class MigrationResult:
    """Ergebnis für eine Datei.

    Attributes:
        status: Einer von `MIGRATED`, `SKIPPED_ALREADY`, `SKIPPED_NOT_AFFECTED`, `CONFLICT`.
        detail: Grund (bei Konflikt) bzw. neue Einträge (bei Migration).
    """

    status: str
    detail: str = ""


def _load_unique(text: str) -> object:
    """Lädt YAML mit Duplikat-Erkennung.

    Args:
        text: Der Frontmatter-Text ohne ``---``-Marker.

    Returns:
        Das geladene Objekt (``None`` bei leerem Frontmatter).
    """
    return yaml.load(text, Loader=_UniqueKeyLoader)  # noqa: S506 - SafeLoader-Subklasse


def _entries_from_old_value(value: object) -> tuple[list[str] | None, str]:
    """Übersetzt den Altwert in die neue Liste — oder liefert den Konfliktgrund.

    Args:
        value: Von PyYAML geladener Wert unter ``Leitkompetenz``.

    Returns:
        ``(einträge, "")`` bei Erfolg, sonst ``(None, grund)``.
    """
    if value is None or value == "":
        return [], ""
    if isinstance(value, str):
        candidates: list[object] = [value]
    elif isinstance(value, list):
        candidates = list(value)
    else:
        return None, f"Nicht unterstützter Typ {type(value).__name__} für {OLD_KEY}"
    entries: list[str] = []
    for item in candidates:
        if not isinstance(item, str):
            return None, f"Listeneintrag vom Typ {type(item).__name__} ist kein Text: {item!r}"
        reason = list_entry_violation(item)
        if reason is not None:
            return None, f"Eintrag {item!r} verletzt die Listen-Invariante: {reason}"
        entries.append(item)
    return entries, ""


def _block_end(lines: list[str], start: int) -> int:
    """Liefert den exklusiven Endindex des Key-Blocks, der bei `start` beginnt.

    Zum Block gehören die Folgezeilen, die eingerückt sind oder mit ``-``
    beginnen (Listeneinträge); Leerzeilen am Blockende gehören nicht dazu.

    Args:
        lines: Frontmatter-Zeilen.
        start: Index der Key-Zeile.

    Returns:
        Index der ersten Zeile nach dem Block.
    """
    end = start + 1
    last_content = start
    while end < len(lines):
        line = lines[end]
        if line.strip() == "":
            end += 1
            continue
        if line[0] in " \t-":
            last_content = end
            end += 1
            continue
        break
    return last_content + 1


def _new_block(entries: list[str]) -> list[str]:
    """Rendert den neuen ``Leitkompetenzen``-Block.

    Eine leere Liste wird als Key ohne Wert geschrieben: Der Projektparser
    liest das als leere Liste (``[]`` würde er als Text ``"[]"`` lesen).

    Args:
        entries: Die gültigen Einträge.

    Returns:
        Die Blockzeilen.
    """
    return [f"{NEW_KEY}:"] + [f"  - {yaml_double_quote(entry)}" for entry in entries]


def migrate_text(text: str) -> tuple[MigrationResult, str]:
    """Migriert den (BOM-freien) Dateitext; ändert nichts bei Konflikt/Skip.

    Args:
        text: Kompletter Dateiinhalt.

    Returns:
        ``(ergebnis, neuer_text)``; bei Konflikt oder Skip ist ``neuer_text == text``.
    """
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    if not lines or lines[0].strip() != "---":
        return MigrationResult(CONFLICT, "Kein YAML-Frontmatter am Dateianfang"), text
    close = next((idx for idx in range(1, len(lines)) if lines[idx].strip() == "---"), None)
    if close is None:
        return MigrationResult(CONFLICT, "YAML-Frontmatter nicht geschlossen"), text
    fm_lines = lines[1:close]

    try:
        data = _load_unique("\n".join(fm_lines))
    except yaml.YAMLError as exc:
        return MigrationResult(CONFLICT, f"Frontmatter nicht parsebar: {exc}"), text
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return MigrationResult(CONFLICT, "Frontmatter ist kein Mapping"), text

    scan: dict[str, list[int]] = {OLD_KEY: [], NEW_KEY: []}
    for idx, line in enumerate(fm_lines):
        match = _TOP_LEVEL_KEY_RE.match(line)
        if match and match.group("key") in scan:
            scan[match.group("key")].append(idx)
        elif re.match(rf"^[ \t]+(?:{OLD_KEY}|{NEW_KEY})[ \t]*:", line):
            return MigrationResult(CONFLICT, f"Eingerückter Key in Zeile {idx + 2}"), text
    for key, positions in scan.items():
        if len(positions) > 1:
            return MigrationResult(CONFLICT, f"Doppelter Key '{key}'"), text
        if bool(positions) != (key in data):
            return MigrationResult(CONFLICT, f"Key-Zeile und YAML-Struktur für '{key}' stimmen nicht überein"), text

    has_old, has_new = OLD_KEY in data, NEW_KEY in data
    if has_old and has_new:
        return MigrationResult(CONFLICT, f"Beide Keys '{OLD_KEY}' und '{NEW_KEY}' vorhanden"), text
    if has_new:
        return MigrationResult(SKIPPED_ALREADY), text
    if not has_old:
        return MigrationResult(SKIPPED_NOT_AFFECTED), text

    start = scan[OLD_KEY][0]
    end = _block_end(fm_lines, start)
    if any("\\" in line for line in fm_lines[start:end]):
        # Die alte App maskierte Backslashes nicht und las sie wörtlich; PyYAML
        # würde sie in gequoteten Werten als Escape deuten (z. B. "\b"). Nicht raten.
        return MigrationResult(CONFLICT, f"Backslash im Wert von '{OLD_KEY}' — bitte manuell prüfen"), text

    entries, reason = _entries_from_old_value(data[OLD_KEY])
    if entries is None:
        return MigrationResult(CONFLICT, reason), text

    new_fm = fm_lines[:start] + _new_block(entries) + fm_lines[end:]

    expected = {key: value for key, value in data.items() if key != OLD_KEY}
    expected[NEW_KEY] = entries if entries else None
    try:
        reloaded = _load_unique("\n".join(new_fm))
    except yaml.YAMLError as exc:
        return MigrationResult(CONFLICT, f"Strukturprüfung fehlgeschlagen: {exc}"), text
    if reloaded != expected:
        return MigrationResult(CONFLICT, "Strukturprüfung fehlgeschlagen: neues Frontmatter weicht ab"), text

    new_lines = [lines[0]] + new_fm + lines[close:]
    return MigrationResult(MIGRATED, repr(entries)), newline.join(new_lines)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Schreibt Bytes atomar (Temp-Datei + Replace), ohne Zeilenenden umzukodieren.

    `bw_libs.app_paths.atomic_write_text` schreibt im Textmodus und würde unter
    Windows ``\\n`` in ``\\r\\n`` umwandeln — die Migration muss aber alle nicht
    betroffenen Bytes unverändert lassen.

    Args:
        path: Zieldatei.
        payload: Vollständiger neuer Inhalt.
    """
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
        Path(temp_name).replace(path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def migrate_file(path: Path, *, dry_run: bool) -> MigrationResult:
    """Migriert eine Sequenzdatei (oder nur Auswertung bei ``dry_run``).

    Args:
        path: Sequenzdatei.
        dry_run: Wenn ``True``, wird nichts geschrieben.

    Returns:
        Das Ergebnis für diese Datei.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return MigrationResult(CONFLICT, f"Datei nicht lesbar: {exc}")
    bom = raw.startswith(_BOM)
    try:
        text = raw[len(_BOM) :].decode("utf-8") if bom else raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return MigrationResult(CONFLICT, f"Kein gültiges UTF-8: {exc}")

    result, new_text = migrate_text(text)
    if result.status == MIGRATED and not dry_run:
        _atomic_write_bytes(path, (_BOM if bom else b"") + new_text.encode("utf-8"))
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI-Einstiegspunkt.

    Args:
        argv: Argumente (Standard: ``sys.argv[1:]``).

    Returns:
        Exit-Code: 0 ohne Konflikte, sonst 1.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, keine Dateien schreiben.")
    parser.add_argument("--no-archive", action="store_true", help="Archivierte Kurse nicht migrieren.")
    parser.add_argument("--unterricht-dir", type=Path, default=None, help="Optionaler Override des Unterrichtsordners.")
    args = parser.parse_args(argv)

    unterricht_dir = resolve_unterricht_dir(args.unterricht_dir)
    if not unterricht_dir.is_dir():
        print(f"Unterrichtsordner nicht gefunden: {unterricht_dir}")
        return 1
    if args.dry_run:
        print("[dry-run] Es werden keine Dateien geschrieben.\n")

    counts: dict[str, int] = {MIGRATED: 0, SKIPPED_ALREADY: 0, SKIPPED_NOT_AFFECTED: 0, CONFLICT: 0}
    for course_dir in iter_course_dirs(unterricht_dir, include_archive=not args.no_archive):
        for path in iter_sequence_files(course_dir):
            result = migrate_file(path, dry_run=args.dry_run)
            counts[result.status] += 1
            suffix = f": {result.detail}" if result.detail else ""
            print(f"{path}: {result.status}{suffix}")

    print(
        f"\nZusammenfassung: {counts[MIGRATED]} migriert, {counts[SKIPPED_ALREADY]} bereits migriert, "
        f"{counts[SKIPPED_NOT_AFFECTED]} nicht betroffen, {counts[CONFLICT]} Konflikt(e)."
    )
    return 1 if counts[CONFLICT] else 0


if __name__ == "__main__":
    sys.exit(main())
