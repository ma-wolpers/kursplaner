"""Maskierung und Rückwandlung doppelt gequoteter YAML-Skalare (projekteigener Parser).

Der projekteigene Frontmatter-Parser (`yaml_registry.parse_yaml_frontmatter`)
und alle Schreibstellen (`yaml_registry.render_yaml_frontmatter`,
`plan_repository`, `sequence_plan_repository`) teilen sich hier **eine**
Definition davon, wie ein Text als doppelt gequoteter YAML-Skalar geschrieben
und wieder gelesen wird.

Hintergrund: Früher setzten die Schreibstellen Werte entweder ganz ohne
Maskierung in Anführungszeichen (Listeneinträge in `render_yaml_frontmatter`
→ ein ``"`` im Eintrag erzeugte ungültiges YAML) oder maskierten nur ``"`` als
``\\"`` (`_yaml_quote` der Repositories), während der Parser nur die äußeren
Anführungszeichen abschnitt und ``\\"`` *nicht* zurückwandelte. Ein ``"`` im
Wert wuchs dadurch bei jedem Speichern um einen weiteren Backslash.

Unterstützter Escape-Umfang (bewusst minimal, symmetrisch zum Schreiben):
``\\\\`` → ``\\`` und ``\\"`` → ``"``. Andere Backslash-Folgen (z. B. ``\\U``
in einem Windows-Pfad aus Altbestand) bleiben unverändert stehen, damit
bisher geschriebene Werte ohne Maskierung ihre Bedeutung behalten.
"""

from __future__ import annotations


def yaml_double_quote(text: str) -> str:
    """Schreibt einen Text als doppelt gequoteten YAML-Skalar.

    Maskiert zuerst ``\\`` (zu ``\\\\``) und danach ``"`` (zu ``\\"``). Die
    Reihenfolge ist wichtig: Würde ``"`` zuerst maskiert, würde der dabei
    eingefügte Backslash anschließend selbst verdoppelt.

    Args:
        text: Der zu schreibende Klartext.

    Returns:
        Der Text in doppelten Anführungszeichen, bereit für eine YAML-Zeile.

    Example::

        yaml_double_quote('AB "Brüche" \\\\ Teil 2')
        # -> '"AB \\\\"Brüche\\\\" \\\\\\\\ Teil 2"'
    """
    escaped = str(text).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def decode_yaml_scalar(raw: str) -> str:
    """Wandelt einen (bereits getrimmten) rohen YAML-Skalar in Klartext zurück.

    Ist `raw` vollständig in doppelte Anführungszeichen eingeschlossen, wird
    der Inhalt dazwischen über `_unescape_double_quoted` zurückgewandelt
    (Gegenstück zu `yaml_double_quote`). Sonst gilt das bisherige
    Parser-Verhalten unverändert (``raw.strip('"')``), damit ungequotete
    Altbestands-Werte genauso gelesen werden wie vor dieser Änderung.

    Args:
        raw: Der rohe Wert rechts vom ``:`` bzw. hinter dem ``-`` eines
            Listeneintrags, ohne umgebenden Whitespace.

    Returns:
        Der Klartext des Werts.

    Example::

        decode_yaml_scalar('"a \\\\"b\\\\" \\\\\\\\ c"')
        # -> 'a "b" \\\\ c'
    """
    if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
        return _unescape_double_quoted(raw[1:-1])
    return raw.strip('"')


def _unescape_double_quoted(inner: str) -> str:
    """Löst ``\\\\`` und ``\\"`` in einem gequoteten Skalarinhalt auf.

    Läuft zeichenweise, damit ``\\\\"`` korrekt als maskierter Backslash
    gefolgt von einem (unmaskierten) Anführungszeichen gelesen wird und nicht
    als Backslash + maskiertes Anführungszeichen. Ein Backslash vor einem
    anderen Zeichen bleibt samt Folgezeichen stehen (siehe Modul-Docstring).

    Args:
        inner: Der Text zwischen den äußeren Anführungszeichen.

    Returns:
        Der zurückgewandelte Klartext.
    """
    result: list[str] = []
    index = 0
    while index < len(inner):
        char = inner[index]
        if char == "\\" and index + 1 < len(inner) and inner[index + 1] in ("\\", '"'):
            result.append(inner[index + 1])
            index += 2
            continue
        result.append(char)
        index += 1
    return "".join(result)
