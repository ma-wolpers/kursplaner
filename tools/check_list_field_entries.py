"""Prüftool (nur lesend): meldet Listeneinträge, die den Listenvertrag verletzen.

Der Kursplaner zeigt Listenfelder im Grid mit ``--``-Trennzeilen an und trennt
bei der Eingabe zusätzlich an ``;`` (siehe ``kursplaner/core/domain/list_cell_text.py``).
Damit Anzeige und Speichern verlustfrei bleiben, muss jeder gespeicherte
Listeneintrag einzeilig, nicht leer, ohne Leerzeichen am Rand und ohne ``;``
sein und darf nicht nur aus Strichen bestehen. Eine Stunde mit einem
ungültigen Eintrag ist in der App **nicht ladbar** (mit Erklärung).

Dieses Tool findet solche Einträge **vor** dem Upgrade, und zwar gesammelt
(alle Verstöße aller Dateien), während die App beim ersten Verstoß abbricht.
Regelquelle ist für beide dieselbe Funktion: ``list_field_violations``.

Geprüft werden:

* jede Stundendatei (``Einheiten``/``Alteinheiten``, ``.md``/``.ebw``): alle
  Listenfelder, die für ihren Stundentyp gelten (wie in der App),
* jede Sequenzdatei (``Sequenzen``): das Feld ``Leitkompetenzen`` (reine Liste).

Dateien, die sich gar nicht lesen lassen (z. B. fehlendes Frontmatter oder
fehlende Pflichtfelder), werden ebenfalls gemeldet.

Usage (vom Repo-Wurzelverzeichnis)::

    python -m tools.check_list_field_entries [--no-archive] [--unterricht-dir PFAD]

Exit-Code 0, wenn alles gültig ist, sonst 1. Es wird nie geschrieben.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.lesson_yaml_policy import LIST_FIELDS, allowed_keys_for_type, infer_stundentyp
from kursplaner.core.domain.list_cell_text import list_field_violations
from kursplaner.core.domain.sequence_planning import SEQUENCE_YAML_FOCUS_COMPETENCIES_KEY
from kursplaner.core.domain.yaml_registry import LESSON_SCHEMA, SEQUENCE_PLAN_SCHEMA, YamlSchema, parse_yaml_frontmatter
from tools.vault_courses import iter_course_dirs, iter_lesson_files, iter_sequence_files, resolve_unterricht_dir


@dataclass(frozen=True)
class Finding:
    """Ein gemeldeter Verstoß.

    Attributes:
        path: Betroffene Datei.
        field: YAML-Feld; leer bei einer nicht lesbaren Datei.
        entry: Der beanstandete Rohwert (``None`` bei nicht lesbarer Datei).
        reason: Verständliche Erklärung inkl. Lösungshinweis.
    """

    path: Path
    field: str
    entry: object
    reason: str


def _read_frontmatter(path: Path, schema: YamlSchema) -> tuple[dict[str, object] | None, Finding | None]:
    """Liest das Frontmatter einer Datei mit dem regulären Projektparser.

    Args:
        path: Zu lesende Datei.
        schema: Schema der Datei (wie in der App).

    Returns:
        ``(daten, None)`` bei Erfolg, sonst ``(None, Finding)`` mit dem Lesefehler.
    """
    try:
        data, _ = parse_yaml_frontmatter(path.read_text(encoding="utf-8"), schema, source_label=str(path))
    except (OSError, RuntimeError, UnicodeDecodeError) as exc:
        return None, Finding(path=path, field="", entry=None, reason=f"Datei nicht lesbar: {exc}")
    return data, None


def check_lesson_file(path: Path) -> list[Finding]:
    """Meldet alle Verstöße in den Listenfeldern einer Stundendatei.

    Es werden genau die Listenfelder geprüft, die die App für den Stundentyp
    der Datei übernimmt (`allowed_keys_for_type` ∩ `LIST_FIELDS`) — Felder,
    die die App ohnehin verwirft, machen die Stunde nicht unladbar.

    Args:
        path: Stundendatei.

    Returns:
        Alle Verstöße in Dateireihenfolge (leer, wenn alles gültig ist).
    """
    data, error = _read_frontmatter(path, LESSON_SCHEMA)
    if error is not None or data is None:
        return [error] if error is not None else []
    relevant = [key for key in allowed_keys_for_type(infer_stundentyp(data)) if key in LIST_FIELDS and key in data]
    findings: list[Finding] = []
    for key in relevant:
        for entry, reason in list_field_violations(data[key]):
            findings.append(Finding(path=path, field=key, entry=entry, reason=reason))
    return findings


def check_sequence_file(path: Path) -> list[Finding]:
    """Meldet alle Verstöße im Feld ``Leitkompetenzen`` einer Sequenzdatei.

    Args:
        path: Sequenzdatei.

    Returns:
        Alle Verstöße (leer, wenn alles gültig ist oder das Feld fehlt — ein
        fehlendes Pflichtfeld meldet bereits die Schema-Prüfung beim Lesen).
    """
    data, error = _read_frontmatter(path, SEQUENCE_PLAN_SCHEMA)
    if error is not None or data is None:
        return [error] if error is not None else []
    key = SEQUENCE_YAML_FOCUS_COMPETENCIES_KEY
    if key not in data:
        return []
    return [
        Finding(path=path, field=key, entry=entry, reason=reason)
        for entry, reason in list_field_violations(data[key], allow_scalar=False)
    ]


def scan(unterricht_dir: Path, *, include_archive: bool) -> list[Finding]:
    """Prüft alle Stunden- und Sequenzdateien aller Kurse.

    Args:
        unterricht_dir: Wurzel der aktiven Kurse.
        include_archive: Ob archivierte Kurse mitgeprüft werden.

    Returns:
        Alle Verstöße über alle Dateien.
    """
    findings: list[Finding] = []
    for course_dir in iter_course_dirs(unterricht_dir, include_archive=include_archive):
        for lesson_path in iter_lesson_files(course_dir):
            findings.extend(check_lesson_file(lesson_path))
        for sequence_path in iter_sequence_files(course_dir):
            findings.extend(check_sequence_file(sequence_path))
    return findings


def format_findings(findings: list[Finding]) -> str:
    """Formatiert die Verstöße gruppiert nach Datei für die Konsolenausgabe.

    Args:
        findings: Ergebnis von `scan`.

    Returns:
        Mehrzeiliger Bericht (leer bei keinen Funden).
    """
    lines: list[str] = []
    current: Path | None = None
    for finding in findings:
        if finding.path != current:
            current = finding.path
            lines.append(str(finding.path))
        if finding.field:
            lines.append(f"  Feld {finding.field}: {finding.entry!r}")
            lines.append(f"    -> {finding.reason}")
        else:
            lines.append(f"  {finding.reason}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI-Einstiegspunkt.

    Args:
        argv: Argumente (Standard: ``sys.argv[1:]``).

    Returns:
        Exit-Code: 0 ohne Funde, 1 bei Funden oder fehlendem Unterrichtsordner.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-archive", action="store_true", help="Archivierte Kurse nicht prüfen.")
    parser.add_argument(
        "--unterricht-dir",
        type=Path,
        default=None,
        help="Optionaler Override des Unterrichtsordners (Standard: konfigurierter Pfad).",
    )
    args = parser.parse_args(argv)

    unterricht_dir = resolve_unterricht_dir(args.unterricht_dir)
    if not unterricht_dir.is_dir():
        print(f"Unterrichtsordner nicht gefunden: {unterricht_dir}")
        return 1

    findings = scan(unterricht_dir, include_archive=not args.no_archive)
    if not findings:
        print("Alle Listeneinträge sind gültig.")
        return 0
    print(format_findings(findings))
    files = len({finding.path for finding in findings})
    print(f"\n{len(findings)} Verstoß/Verstöße in {files} Datei(en). Bitte in Obsidian korrigieren.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
