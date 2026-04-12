from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def split_name(name: str) -> list[str]:
    parts: list[str] = []
    chunk = ""
    for char in name:
        if char.isupper() and chunk and (not chunk[-1].isupper()):
            parts.append(chunk)
            chunk = char
        else:
            chunk += char
    if chunk:
        parts.append(chunk)
    return [p for p in parts if p]


def human_label(name: str) -> str:
    return " ".join(split_name(name)).replace("Use Case", "Use-Case")


def build_class_doc(name: str, bases: list[str]) -> list[str]:
    label = human_label(name)
    lowered = name.lower()
    base_text = " ".join(bases).lower()
    tokens = {token.lower() for token in split_name(name)}

    if lowered.startswith("filesystem") and lowered.endswith("repository"):
        return [
            f"Implementiert persistente Dateioperationen für {label}.",
            "",
            "Die Klasse erfüllt ein Repository-Interface und kapselt Markdown-/Dateisystemzugriffe.",
        ]

    if "protocol" in base_text or lowered.endswith("repository"):
        return [
            f"Definiert den Vertrag für {label}.",
            "",
            "Die konkrete Implementierung wird in der Infrastructure-Schicht bereitgestellt.",
        ]

    if lowered.endswith("usecase") or lowered.endswith("use_case"):
        return [
            f"Orchestriert den fachlichen Ablauf für {label}.",
            "",
            "Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.",
        ]

    if lowered.endswith("request") or lowered.endswith("input"):
        return [
            f"Repräsentiert Eingabeparameter für {label}.",
            "",
            "Die Instanz bündelt validierte Nutzereingaben für einen fachlichen Verarbeitungsschritt.",
        ]

    if (
        lowered.endswith("result")
        or lowered.endswith("entry")
        or lowered.endswith("delta")
        or lowered.endswith("data")
        or lowered.endswith("schema")
    ):
        return [
            f"Beschreibt die Datenstruktur für {label}.",
            "",
            "Die Instanz transportiert strukturierte Fachdaten zwischen Schichten und Verarbeitungsschritten.",
        ]

    if lowered.endswith("plan"):
        return [
            f"Beschreibt den Ausführungsplan für {label}.",
            "",
            "Die Instanz hält vorberechnete Schritte und Zielwerte für eine nachgelagerte Aktion.",
        ]

    if lowered.endswith("item"):
        return [
            f"Beschreibt einen einzelnen Anzeigeeintrag für {label}.",
            "",
            "Die Instanz bündelt Felder für Listen- oder Übersichtsansichten im UI und in Reports.",
        ]

    if lowered.endswith("resolution"):
        return [
            f"Beschreibt die Konfliktauflösung für {label}.",
            "",
            "Die Instanz hält Benutzerentscheidung und optionale Zielzeile für den Konfliktfall.",
        ]

    if "clipboard" in tokens:
        return [
            f"Hält Zwischenablageinformationen für {label}.",
            "",
            "Die Instanz beschreibt Quelle und Inhalt einer kopierten Stunde für spätere Einfügeaktionen.",
        ]

    if "tooltip" in lowered or {"tool", "tip"}.issubset(tokens):
        return [
            f"Zeigt kontextbezogene Hinweise für {label}.",
            "",
            "Die Klasse verwaltet Ein-/Ausblendung eines kleinen Hilfefensters an einem Widget.",
        ]

    if lowered.endswith("window") or lowered.endswith("dialog") or lowered.endswith("app"):
        return [
            f"Stellt die GUI-Komponente {label} bereit.",
            "",
            "Die Klasse kapselt Bedienlogik und delegiert fachliche Entscheidungen an Use Cases.",
        ]

    if "error" in tokens:
        return [
            f"Kennzeichnet Fehlerzustände über {label}.",
            "",
            "Die Klasse macht fachlich erwartbare Validierungsprobleme als eigenen Fehlertyp unterscheidbar.",
        ]

    if "validator" in tokens:
        return [
            f"Bündelt Prüfregeln für {label}.",
            "",
            "Die Klasse liefert zentrale Validierungslogik für Eingaben und Regelkonformität.",
        ]

    if "store" in tokens:
        return [
            f"Kapselt Lese-/Schreibzugriffe für {label}.",
            "",
            "Die Klasse verwaltet persistierte Konfigurationen und deren stabile Ablage.",
        ]

    if lowered.endswith("paths") or lowered.endswith("issue"):
        return [
            f"Beschreibt Konfigurationsdaten für {label}.",
            "",
            "Die Klasse bündelt Pfad- und Prüfwerte in einem stabilen Datentyp.",
        ]

    return [
        f"Stellt die Kernfunktionalität von {label} bereit.",
        "",
        "Die Klasse fasst zusammengehörige Operationen zu einem klar abgegrenzten Baustein zusammen.",
    ]


def rewrite_file(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    lines = source.splitlines()
    edits: list[tuple[int, int, list[str]]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not node.body:
            continue

        first = node.body[0]
        if not (
            isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str)
        ):
            continue

        indent = " " * (node.col_offset + 4)
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)

        doc_lines = build_class_doc(node.name, bases)
        replacement = [f'{indent}"""{doc_lines[0]}']
        for line in doc_lines[1:]:
            replacement.append(f"{indent}{line}")
        replacement.append(f'{indent}"""')

        start = first.lineno - 1
        end = first.end_lineno - 1
        edits.append((start, end, replacement))

    if not edits:
        return False

    for start, end, replacement in sorted(edits, key=lambda item: item[0], reverse=True):
        lines[start : end + 1] = replacement

    path.write_text("\n".join(lines) + ("\n" if source.endswith("\n") else ""), encoding="utf-8")
    return True


def iter_python_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.py"):
        if any(part in {".venv", "__pycache__"} for part in path.parts):
            continue
        files.append(path)
    return files


def main() -> None:
    changed = 0
    for path in iter_python_files():
        if rewrite_file(path):
            changed += 1
    print(f"Klassen-Docstrings aktualisiert in {changed} Datei(en).")


if __name__ == "__main__":
    main()
