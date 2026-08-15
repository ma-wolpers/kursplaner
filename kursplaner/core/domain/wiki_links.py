from __future__ import annotations

import re


def _normalize_component(value: str) -> str:
    """Normalizes a wiki-link component so malformed bracket input cannot break syntax."""
    text = str(value or "").replace("[", " ").replace("]", " ")
    text = text.replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def build_wiki_link(target: str, alias: str | None = None) -> str:
    """Builds an Obsidian wiki-link in one place (`[[target]]` or `[[target|alias]]`)."""
    normalized_target = _normalize_component(target)
    if not normalized_target:
        return ""

    normalized_alias = _normalize_component(alias or "")
    if normalized_alias:
        return f"[[{normalized_target}|{normalized_alias}]]"
    return f"[[{normalized_target}]]"


def strip_wiki_link(raw: str) -> str:
    """Extracts plain text from raw wiki-link-ish text by removing wrapper brackets."""
    text = str(raw or "").strip()
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2]
    return text.replace("[[", "").replace("]]", "").strip()


def strip_group_prefixed_link(raw: str, group_name: str) -> str:
    """Entschlüsselt einen ggf. wiki-verlinkten, gruppen-präfigierten Text.

    Zentrale Stelle für "Wiki-Link dekodieren + optionalen führenden
    Gruppennamen-Token abschneiden": wandelt einen Wert wie
    ``"[[11.1 EFl1 Potenzfunktionen]]"`` in den reinen Anzeige-/
    Vergleichstext ``"EFl1 Potenzfunktionen"`` um. Bereits unverlinkter Text
    (kein ``[[...]]``) wird unverändert (nur getrimmt) zurückgegeben — er
    gilt bereits als reiner Anzeigewert. Nutzer:innen können ein Feld wie
    das YAML-``Oberthema`` einer Stunden-Datei bewusst als Wiki-Link
    speichern (damit es in Obsidian verlinkt); diese Funktion liefert dafür
    einheitlich den entschlüsselten Wert für Anzeige/Vergleich, ohne die
    Speicherung selbst zu verändern.

    Args:
        raw: Roher Text, wiki-verlinkt oder bereits Klartext.
        group_name: Lerngruppen-Bezeichnung; darf selbst als Wiki-Link
            vorliegen (z. B. ``"[[li2]]"``) und wird automatisch bereinigt.

    Returns:
        Der entschlüsselte Text.

    Example::

        strip_group_prefixed_link("[[11.1 EFl1 Potenzfunktionen]]", "11.1")
        # -> "EFl1 Potenzfunktionen"
        strip_group_prefixed_link("EFl1 Potenzfunktionen", "11.1")
        # -> "EFl1 Potenzfunktionen"
    """
    text = str(raw or "").strip()
    if not text:
        return ""
    if not (text.startswith("[[") and text.endswith("]]")):
        return text

    inner = strip_wiki_link(text)
    group_plain = strip_wiki_link(str(group_name or "").strip())
    if group_plain and inner.lower().startswith(group_plain.lower()):
        remainder = inner[len(group_plain) :].strip()
        if remainder:
            return remainder
    return inner
