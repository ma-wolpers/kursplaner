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
