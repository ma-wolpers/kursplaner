from __future__ import annotations


def parse_list_section(body: str, title: str) -> list[str]:
    """Liest Bullet-Einträge unter einer Markdown-Section ``## <title>``."""
    marker = f"## {title}".lower()
    lines = body.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip().lower() == marker:
            start = idx + 1
            break
    if start is None:
        return []

    result: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("## "):
            break
        if stripped.startswith("-"):
            item = stripped[1:].strip()
            if item:
                result.append(item)
    return result


def parse_reflection(body: str) -> str:
    """Liest den Reflexionstext zwischen ``# Reflexion`` und der naechsten ``##`` Section."""
    lines = body.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip().lower() == "# reflexion":
            start = idx + 1
            break
    if start is None:
        return ""

    chunks: list[str] = []
    for line in lines[start:]:
        if line.strip().startswith("## "):
            break
        chunks.append(line)
    return "\n".join(chunks).strip()


def text_to_list_entries(text: str) -> list[str]:
    """Konvertiert mehrzeiligen UI-Text in Bullet-Einträge (eine Zeile = ein Eintrag)."""
    result: list[str] = []
    for line in str(text or "").splitlines():
        item = line.strip()
        if not item:
            continue
        if item.startswith("-"):
            item = item[1:].strip()
        if item:
            result.append(item)
    return result
