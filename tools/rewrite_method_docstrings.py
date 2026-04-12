from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


GENERIC_MARKERS = (
    "Führt ",
    "Eingabeparameter",
    "Fachlicher Eingabewert für diesen Verarbeitungsschritt.",
    "Eingabewert für diesen Verarbeitungsschritt.",
    "Rückgabewert der fachlichen Verarbeitung.",
    "Wird bei ungültigen Eingaben",
)


def split_name(name: str) -> list[str]:
    parts: list[str] = []
    chunk = ""
    for char in name:
        if char == "_":
            if chunk:
                parts.append(chunk)
                chunk = ""
            continue
        if char.isupper() and chunk and (not chunk[-1].isupper()):
            parts.append(chunk)
            chunk = char
        else:
            chunk += char
    if chunk:
        parts.append(chunk)
    return [part for part in parts if part]


def human_label(name: str) -> str:
    return " ".join(split_name(name))


def method_summary(func_name: str, class_name: str | None) -> str:
    class_part = human_label(class_name) if class_name else "dem Modul"
    name = func_name.lower()

    if func_name == "__init__":
        if class_name:
            return f"Initialisiert eine neue Instanz von {class_part}."
        return "Initialisiert den zugrunde liegenden Verarbeitungskontext."

    if name in {"execute", "run"}:
        return f"Führt den zentralen Ablauf in {class_part} aus."
    if name.startswith("load"):
        return f"Lädt die benötigten Daten für {class_part}."
    if name.startswith("save") or name.startswith("persist"):
        return f"Speichert den aktuellen Zustand für {class_part}."
    if name.startswith("list"):
        return f"Ermittelt eine Liste relevanter Einträge für {class_part}."
    if name.startswith("find") or name.startswith("resolve"):
        return f"Bestimmt den passenden Zielwert im Kontext von {class_part}."
    if name.startswith("build") or name.startswith("create"):
        return f"Erzeugt die benötigte Struktur für {class_part}."
    if name.startswith("update") or name.startswith("set"):
        return f"Aktualisiert den fachlichen Zustand in {class_part}."
    if name.startswith("merge"):
        return f"Führt die Zusammenführung im Kontext von {class_part} durch."
    if name.startswith("split"):
        return f"Teilt den ausgewählten Inhalt im Kontext von {class_part} auf."
    if name.startswith("convert"):
        return f"Konvertiert den Zustand in {class_part} in das gewünschte Zielformat."
    if name.startswith("apply"):
        return f"Wendet die vorbereiteten Änderungen in {class_part} an."
    if name.startswith("clear"):
        return f"Entfernt den aktuellen Inhalt im Kontext von {class_part}."
    if name.startswith("can_") or name.startswith("has_") or name.startswith("is_"):
        return f"Prüft eine fachliche Bedingung in {class_part}."
    if name.startswith("_"):
        return f"Unterstützt interne Verarbeitungsschritte in {class_part}."

    method_part = human_label(func_name)
    return f"Verarbeitet den Schritt {method_part} im Kontext von {class_part}."


def parse_param_name(arg_name: str) -> str:
    return arg_name


def describe_param(name: str) -> str:
    lowered = name.lower().lstrip("_")
    if lowered in {"table", "plan_table"}:
        return "Planungstabelle, auf der die Operation ausgeführt wird."
    if lowered in {"row_index", "idx", "index"}:
        return "Zeilenindex innerhalb der aktuellen Tabelle."
    if "path" in lowered:
        return "Dateipfad für den betroffenen Lese-/Schreibvorgang."
    if "dir" in lowered or "folder" in lowered:
        return "Verzeichnis, das als Quelle oder Ziel verwendet wird."
    if lowered in {"label", "title", "name"}:
        return "Bezeichner für die auszuführende Aktion."
    if lowered in {"before", "after", "state", "states"}:
        return "Zustandsdaten vor bzw. nach einer Änderung."
    if lowered in {"content", "text", "reason_text"}:
        return "Inhaltstext, der fachlich weiterverarbeitet wird."
    if lowered in {"decision", "resolution"}:
        return "Entscheidung zur Konfliktbehandlung oder Ablaufsteuerung."
    if lowered in {"widget", "event", "_event"}:
        return "UI-Kontextobjekt aus dem aktuellen Interaktionsablauf."
    if lowered in {"deltas", "delta"}:
        return "Änderungsdeltas, die auf Dateien angewendet werden."
    if lowered in {"use_before", "proceed"}:
        return "Steuerflag für den gewählten Ablaufpfad."
    return "Eingabewert für diesen Verarbeitungsschritt."


def build_docstring(
    func_name: str,
    class_name: str | None,
    param_names: list[str],
    has_return: bool,
) -> list[str]:
    lines: list[str] = [method_summary(func_name, class_name)]

    if param_names:
        lines.append("")
        lines.append("Args:")
        for name in param_names:
            lines.append(f"    {name}: {describe_param(name)}")

    if has_return:
        lines.append("")
        lines.append("Returns:")
        lines.append("    Fachliches Ergebnis der Verarbeitung.")

    return lines


def has_non_none_return(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if node.returns is not None:
        if isinstance(node.returns, ast.Constant) and node.returns.value is None:
            return False
        return True

    for child in ast.walk(node):
        if isinstance(child, ast.Return) and child.value is not None:
            return True
    return False


def collect_param_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    names: list[str] = []

    all_args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    for arg in all_args:
        if arg.arg in {"self", "cls"}:
            continue
        names.append(parse_param_name(arg.arg))

    if node.args.vararg is not None:
        names.append(parse_param_name(node.args.vararg.arg))
    if node.args.kwarg is not None:
        names.append(parse_param_name(node.args.kwarg.arg))

    return names


def rewrite_file(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    lines = source.splitlines()
    edits: list[tuple[int, int, list[str]]] = []

    def visit(body: list[ast.stmt], class_name: str | None = None) -> None:
        for stmt in body:
            if isinstance(stmt, ast.ClassDef):
                visit(stmt.body, class_name=stmt.name)
                continue

            if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not stmt.body:
                continue

            first = stmt.body[0]
            if not (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                continue

            current_doc = first.value.value.strip()
            if not any(marker in current_doc for marker in GENERIC_MARKERS):
                continue

            indent = " " * (stmt.col_offset + 4)
            param_names = collect_param_names(stmt)
            has_return = has_non_none_return(stmt)
            doc_lines = build_docstring(stmt.name, class_name, param_names, has_return)

            replacement = [f'{indent}"""{doc_lines[0]}']
            for line in doc_lines[1:]:
                replacement.append(f"{indent}{line}")
            replacement.append(f'{indent}"""')

            start = first.lineno - 1
            end = first.end_lineno - 1
            edits.append((start, end, replacement))

            visit(stmt.body, class_name=class_name)

    visit(tree.body)

    if not edits:
        return False

    for start, end, replacement in sorted(edits, key=lambda item: item[0], reverse=True):
        lines[start : end + 1] = replacement

    trailing_newline = "\n" if source.endswith("\n") else ""
    path.write_text("\n".join(lines) + trailing_newline, encoding="utf-8")
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
    print(f"Methoden-Docstrings aktualisiert in {changed} Datei(en).")


if __name__ == "__main__":
    main()
