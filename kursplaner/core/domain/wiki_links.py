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


def build_dataview_lesson_link(stem: str) -> str:
    """Builds a Dataview inline-query link showing an Einheit's live Stundenthema.

    Renders `` `= link("stem", [[stem]].Stundenthema)` `` — a backtick-fenced
    Dataview inline query. `link(path, display)` builds a clickable Obsidian
    link to `path` using `display` as the visible text; `[[stem]].Stundenthema`
    reads the `Stundenthema` frontmatter field of the linked Einheit-file live,
    so the visible label always tracks the file's current title without a
    second, potentially stale copy of it living in the plan table.

    This is the ONE place that builds this string — the counterpart to
    `build_wiki_link` for linking the `Inhalt` column of the plan table to an
    Einheit-file. Do not build ad-hoc dataview-link string literals elsewhere;
    call this function instead. The `Thema/Ausfall` column's Themenfolge-link
    (`sync_thema_ausfall_to_plan_row`) is unrelated and keeps using
    `build_wiki_link`.

    Reuses `_normalize_component` like `build_wiki_link` (strips stray
    brackets/newlines). Additionally strips backticks: a backtick inside the
    stem would prematurely close the surrounding inline-query fence and break
    the syntax. No quote-escaping is needed since `"` is already excluded from
    Einheit-Dateistems by `sanitize_hour_title`.

    Args:
        stem: Dateistem der verlinkten Einheit (ohne `.md`-Endung).

    Returns:
        Die fertige Inline-Query, oder ein leerer String bei leerem `stem`.

    Example::

        build_dataview_lesson_link("ab12cd")
        # -> '`= link("ab12cd", [[ab12cd]].Stundenthema)`'
    """
    normalized = _normalize_component(stem).replace("`", "")
    if not normalized:
        return ""
    return f'`= link("{normalized}", [[{normalized}]].Stundenthema)`'


def strip_wiki_link(raw: str) -> str:
    """Extracts plain text from raw wiki-link-ish text by removing wrapper brackets."""
    text = str(raw or "").strip()
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2]
    return text.replace("[[", "").replace("]]", "").strip()


def extract_wiki_link_target(text: str) -> str:
    """Extrahiert aus `[[...]]` den primären Zieldateinamen ohne Pfad/Endung.

    Zentrale Fassung der zuvor unabhängig duplizierten Link-Extraktion
    (`LoadPlanDetailUseCase._extract_primary_link_target`,
    `QueryUbPlanUseCase._extract_primary_link_target`). Bevorzugt bei
    Alias-Links (`[[ziel|alias]]`) das Ziel vor dem Alias, entfernt eine
    ``.md``-Endung sowie einen ggf. vorhandenen Pfadanteil.

    Example::

        extract_wiki_link_target("[[Einheiten/ab12cd.md|Bruchrechnung]]")
        # -> "ab12cd"
    """
    match = re.search(r"\[\[([^\]]+)\]\]", str(text or ""))
    if not match:
        return ""
    raw = match.group(1).strip()
    if "|" in raw:
        raw = raw.split("|", 1)[0].strip()
    if raw.lower().endswith(".md"):
        raw = raw[:-3].strip()
    if "/" in raw or "\\" in raw:
        raw = raw.replace("\\", "/").split("/")[-1].strip()
    return raw


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
