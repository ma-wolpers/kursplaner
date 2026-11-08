"""Textvertrag listenwertiger Felder im Grid (Anzeige, Eingabe, Gültigkeit).

Drei Ebenen, damit die Regeln nicht verwechselt werden:

* **Datei**: Listenfelder stehen als echte YAML-Liste im Frontmatter (eine
  ``- "…"``-Zeile je Eintrag, Obsidian-nativ). Dieses Modul ändert daran nichts.
* **Grid-Anzeige**: Einträge werden untereinander, getrennt durch eine Zeile
  ``--``, dargestellt (`format_list_cell`); ein ``;`` im Eintrag erscheint
  maskiert als ``\\;``.
* **Grid-Eingabe**: Beim Speichern trennt eine Zeile aus mindestens zwei ``-``
  sowie ein ``;`` (Schnelltrenner, z. B. ``K1; K2``) die Einträge
  (`parse_list_cell`). Ein einzelnes ``-``, eine Leerzeile oder ein ``|``
  trennen **nicht** — ``|`` gehört z. B. zu Alias-Links ``[[ziel|alias]]``.

**Escape-Regel (einzige):** ``\\;`` steht für ein wörtliches Semikolon und
trennt nicht; jeder andere Backslash bleibt wörtlich (z. B. ``ℤ\\{0}``). Die
Anzeige setzt vor jedes ``;`` genau einen Backslash, die Eingabe entfernt genau
diesen — so übersteht auch ein wörtliches ``\\;`` den Rundweg (Anzeige
``\\\\;``). Die Datei selbst enthält nie ein Escape; das Kompetenznetz liefert
z. B. Titel wie „f(x)=x^n; n∈ℤ\\{0}“.

Daraus folgt die **Invariante eines gültigen Listeneintrags**: Ein Text, der
nicht leer ist, keinen führenden/nachgestellten Whitespace hat, einzeilig ist
und nicht nur aus Strichen besteht. Nur für solche Einträge ist
``parse_list_cell(format_list_cell(entries)) == entries`` garantiert.
Verletzungen werden nie still korrigiert, sondern mit einer verständlichen
Erklärung gemeldet:

* zur Laufzeit hart (`ListFieldViolationError`, siehe `raise_on_violation`),
  z. B. beim Laden einer Stunden-Datei in `canonicalize_lesson_yaml`;
* im Upgrade-Prüftool gesammelt (`tools/check_list_field_entries.py`).

Beide nutzen `list_field_violations` als einzige Regelquelle.

Die frühere Nummerierungs-Heuristik (``[1] …``, ``1) …``) entfällt: Sie war nie
dokumentiert/getestet und beschädigte legitime Einträge wie
„2. Binomische Formel“.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

LIST_CELL_SEPARATOR = "--"
"""Trennzeile zwischen zwei Einträgen in der Grid-Anzeige."""

QUICK_SEPARATOR = ";"
"""Zusätzlicher Eingabe-Trenner innerhalb einer Zeile (``K1; K2``)."""

ESCAPED_QUICK_SEPARATOR = "\\" + QUICK_SEPARATOR
"""Maskiertes, wörtliches Semikolon in der Grid-Zelle (``\\;``); trennt nicht."""

_QUICK_SPLIT_RE = re.compile(r"(?<!\\)" + re.escape(QUICK_SEPARATOR))
_SEPARATOR_LINE_RE = re.compile(r"^[ \t]*-{2,}[ \t]*$")
_ONLY_DASHES_RE = re.compile(r"^-{2,}$")


class ListFieldViolationError(RuntimeError):
    """Ein Listenfeld enthält einen Eintrag, der die Listen-Invariante verletzt.

    Wird an Ladegrenzen geworfen (Stunden-Datei, Sequenzdatei), damit ungültige
    Daten nie still getrimmt, verworfen oder umgedeutet werden. Die Meldung
    nennt Quelle, Feld, Eintrag und eine verständliche Ursache.

    Attributes:
        field: Name des YAML-Felds (z. B. ``"Material"``).
        entry: Der beanstandete Rohwert.
        reason: Erklärtext aus `list_entry_violation`.
        source_label: Datei bzw. Herkunft (darf leer sein).
    """

    def __init__(self, *, field: str, entry: object, reason: str, source_label: str = "") -> None:
        """Baut die vollständige, nutzerlesbare Fehlermeldung.

        Args:
            field: Name des betroffenen YAML-Felds.
            entry: Der beanstandete Rohwert.
            reason: Erklärtext aus `list_entry_violation`.
            source_label: Dateipfad o. Ä.; leer, wenn unbekannt.
        """
        self.field = field
        self.entry = entry
        self.reason = reason
        self.source_label = source_label
        source = f" in {source_label}" if source_label else ""
        super().__init__(f"Ungültiger Listeneintrag{source}\nFeld: {field}\nEintrag: {entry!r}\nGrund: {reason}")


def list_entry_violation(entry: object) -> str | None:
    """Prüft einen **rohen** Listeneintrag gegen die Listen-Invariante.

    Es wird nichts vorher getrimmt oder umgewandelt — genau das, was in der
    Datei steht, wird geprüft. Die Reihenfolge der Prüfungen bestimmt nur,
    welche Erklärung bei mehreren gleichzeitigen Verstößen erscheint.

    Args:
        entry: Der Rohwert eines Listeneintrags (normalerweise ``str``).

    Returns:
        Ein verständlicher Erklärtext (inkl. Lösungshinweis) oder ``None``,
        wenn der Eintrag gültig ist.

    Example::

        list_entry_violation("Modellieren")       # -> None
        list_entry_violation("x^n; n∈ℤ")           # -> None (';' wird im Grid maskiert)
        list_entry_violation(" Modellieren")      # -> "Eintrag beginnt oder endet …"
    """
    if not isinstance(entry, str):
        return (
            f"Eintrag ist kein Text (YAML-Typ {type(entry).__name__}). "
            'Bitte als Text schreiben, z. B. in Anführungszeichen: - "…".'
        )
    if entry == "":
        return "Eintrag ist leer. Leere Listeneinträge bitte entfernen."
    if not entry.strip():
        return "Eintrag besteht nur aus Leerzeichen. Bitte entfernen."
    if "\n" in entry or "\r" in entry:
        return (
            "Eintrag enthält einen Zeilenumbruch. Im Kursplaner ist jeder Listeneintrag einzeilig — "
            "bitte auf mehrere Listeneinträge aufteilen."
        )
    if entry != entry.strip():
        return "Eintrag beginnt oder endet mit Leerzeichen. Bitte die Leerzeichen am Rand entfernen."
    if _ONLY_DASHES_RE.fullmatch(entry):
        return (
            "Eintrag besteht nur aus Strichen. Eine solche Zeile ist im Kursplaner ein Listentrenner — "
            "bitte entfernen oder durch Text ersetzen."
        )
    return None


def list_field_violations(value: object, *, allow_scalar: bool = True) -> list[tuple[object, str]]:
    """Liefert **alle** Invarianten-Verstöße eines rohen Listenfeld-Werts.

    Einzige Regelquelle für Laufzeit (bricht beim ersten Verstoß ab, siehe
    `raise_on_violation`) und Upgrade-Prüftool (meldet alle gesammelt).

    Feldform (wie vom Parser geliefert): eine Liste oder ``None``/``""``
    (= keine Einträge). Ein einzelner nicht leerer Text gilt nur bei
    ``allow_scalar=True`` als ein Eintrag — das ist das bestehende Verhalten
    der Stunden-Listenfelder (Altbestand ``Material: AB``). Felder mit reinem
    Listenvertrag (``Leitkompetenzen``) prüfen mit ``allow_scalar=False``;
    dort ist ein Skalar selbst ein Verstoß und wird nicht umgedeutet. Jede
    andere Form (Zahl, Mapping, …) ist immer ein Verstoß.

    Args:
        value: Roher Feldwert aus dem Frontmatter.
        allow_scalar: Ob ein einzelner Text als ein Eintrag zulässig ist.

    Returns:
        Liste von ``(eintrag, erklärung)`` in Dateireihenfolge; leer, wenn alles
        gültig ist.
    """
    if value is None or value == "":
        return []
    if isinstance(value, str) and not allow_scalar:
        return [(value, 'Feld ist ein einzelner Text statt einer Liste. Bitte als YAML-Liste schreiben (- "…").')]
    if isinstance(value, str):
        items: Sequence[object] = [value]
    elif isinstance(value, list):
        items = value
    else:
        return [(value, f"Feld ist keine Liste (YAML-Typ {type(value).__name__}). Bitte als Liste schreiben.")]
    violations: list[tuple[object, str]] = []
    for item in items:
        reason = list_entry_violation(item)
        if reason is not None:
            violations.append((item, reason))
    return violations


def raise_on_violation(field: str, value: object, *, source_label: str = "", allow_scalar: bool = True) -> list[str]:
    """Validiert ein rohes Listenfeld und liefert es als Liste gültiger Einträge.

    Gemeinsamer Ladegrenzen-Helfer: erst prüfen (über `list_field_violations`),
    bei Verstoß hart abbrechen, erst danach übernehmen — ohne Trimmen oder
    Filtern, damit kein problematischer Eintrag vorher verschwindet.

    Args:
        field: Name des YAML-Felds (für die Fehlermeldung).
        value: Roher Feldwert (Liste, Text oder ``None``).
        source_label: Datei bzw. Herkunft für die Fehlermeldung.
        allow_scalar: Siehe `list_field_violations`.

    Returns:
        Die Einträge unverändert als ``list[str]``.

    Raises:
        ListFieldViolationError: Beim ersten ungültigen Eintrag.
    """
    violations = list_field_violations(value, allow_scalar=allow_scalar)
    if violations:
        entry, reason = violations[0]
        raise ListFieldViolationError(field=field, entry=entry, reason=reason, source_label=source_label)
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    # Nach der Prüfung ist `value` garantiert eine Liste aus gültigen `str`
    # (jede andere Form wurde oben bereits als Verstoß gemeldet).
    assert isinstance(value, list)
    return [item for item in value if isinstance(item, str)]


def format_list_cell(entries: Sequence[str]) -> str:
    """Formatiert Listeneinträge für die Grid-Anzeige (Trennzeile ``--``).

    Args:
        entries: Gültige Listeneinträge.

    Returns:
        Die Einträge (``;`` maskiert als ``\\;``), verbunden mit ``"\\n--\\n"``;
        ``""`` bei keiner Eingabe.

    Raises:
        ValueError: Wenn ein Eintrag die Invariante verletzt — sonst würde die
            Anzeige beim nächsten Speichern still zu anderen Einträgen geparst.

    Example::

        format_list_cell(["Modellieren", "x^n; n∈ℤ"])
        # -> "Modellieren\\n--\\nx^n\\\\; n∈ℤ"
    """
    for entry in entries:
        reason = list_entry_violation(entry)
        if reason is not None:
            raise ValueError(f"Listeneintrag {entry!r} kann nicht verlustfrei dargestellt werden: {reason}")
    escaped = (entry.replace(QUICK_SEPARATOR, ESCAPED_QUICK_SEPARATOR) for entry in entries)
    return f"\n{LIST_CELL_SEPARATOR}\n".join(escaped)


def parse_list_cell(text: str) -> list[str]:
    """Parst den Text einer Grid-Listenzelle in Listeneinträge.

    Ablauf: Zeilenenden vereinheitlichen → an Zeilen aus ≥ 2 Strichen trennen
    → die Zeilen eines Abschnitts mit einem Leerzeichen verbinden → an jedem
    nicht maskierten ``;`` trennen → trimmen, leere verwerfen → ``\\;`` zu
    ``;`` auflösen. Das Ergebnis erfüllt die Invariante per Konstruktion
    (einzeilig, getrimmt, nie nur Striche, weil solche Zeilen Trenner sind).

    Args:
        text: Roher Zelltext aus dem Grid-Editor.

    Returns:
        Die Einträge in Eingabereihenfolge.

    Example::

        parse_list_cell("K1; K2\\n--\\n[[AB.pdf|AB 1]]\\n--\\nx^n\\\\; n∈ℤ")
        # -> ["K1", "K2", "[[AB.pdf|AB 1]]", "x^n; n∈ℤ"]
    """
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    chunks: list[list[str]] = [[]]
    for line in normalized.split("\n"):
        if _SEPARATOR_LINE_RE.fullmatch(line):
            chunks.append([])
        else:
            chunks[-1].append(line)

    entries: list[str] = []
    for chunk_lines in chunks:
        joined = " ".join(line.strip() for line in chunk_lines if line.strip())
        for part in _QUICK_SPLIT_RE.split(joined):
            # Nur am Rand trimmen: Leerraum *innerhalb* eines Eintrags bleibt
            # erhalten, sonst wäre der Roundtrip z. B. für "a  b" gebrochen.
            candidate = part.strip().replace(ESCAPED_QUICK_SEPARATOR, QUICK_SEPARATOR)
            if candidate and not _ONLY_DASHES_RE.fullmatch(candidate):
                entries.append(candidate)
    return entries
