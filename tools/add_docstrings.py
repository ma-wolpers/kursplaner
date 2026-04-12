from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]


def humanize(name: str) -> str:
    """Verarbeitet den Schritt humanize im Kontext von dem Modul.

    Args:
        name: Bezeichner für die auszuführende Aktion.

    Returns:
        Fachliches Ergebnis der Verarbeitung.
    """
    text = name.strip("_").replace("_", " ").strip()
    return text or name


def returns_value(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Verarbeitet den Schritt returns value im Kontext von dem Modul.

    Args:
        node: Eingabewert für diesen Verarbeitungsschritt.

    Returns:
        Fachliches Ergebnis der Verarbeitung.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Return) and sub.value is not None:
            if isinstance(sub.value, ast.Constant) and sub.value.value is None:
                continue
            return True
    return False


def build_function_doc(node: ast.FunctionDef | ast.AsyncFunctionDef, class_name: str | None) -> list[str]:
    """Erzeugt die benötigte Struktur für dem Modul.

    Args:
        node: Eingabewert für diesen Verarbeitungsschritt.
        class_name: Eingabewert für diesen Verarbeitungsschritt.

    Returns:
        Fachliches Ergebnis der Verarbeitung.
    """
    action = humanize(node.name)
    context = f" der Klasse `{class_name}`" if class_name else ""
    lines: list[str] = [f"Führt {action}{context} aus.", ""]

    arg_names: list[str] = []
    for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
        if arg.arg in {"self", "cls"}:
            continue
        arg_names.append(arg.arg)

    if node.args.vararg is not None:
        arg_names.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg is not None:
        arg_names.append(f"**{node.args.kwarg.arg}")

    if arg_names:
        lines.append("Args:")
        for arg in arg_names:
            arg_clean = arg.lstrip("*")
            lines.append(f"    {arg}: Eingabeparameter `{arg_clean}` für diesen Verarbeitungsschritt.")
        lines.append("")

    if returns_value(node):
        lines.append("Returns:")
        lines.append("    Rückgabewert der fachlichen Verarbeitung.")
        lines.append("")

    lines.append("Raises:")
    lines.append("    Exception: Wird bei ungültigen Eingaben oder I/O-/Verarbeitungsfehlern ausgelöst.")
    return lines


def build_class_doc(node: ast.ClassDef) -> list[str]:
    """Erzeugt die benötigte Struktur für dem Modul.

    Args:
        node: Eingabewert für diesen Verarbeitungsschritt.

    Returns:
        Fachliches Ergebnis der Verarbeitung.
    """
    purpose = humanize(node.name)
    return [
        f"Kapselt die Verantwortlichkeiten für {purpose}.",
        "",
        "Die Klasse bündelt zusammengehörige Logik und stellt eine klar abgegrenzte Schnittstelle bereit.",
    ]


def module_py_files() -> Iterable[Path]:
    """Verarbeitet den Schritt module py files im Kontext von dem Modul.

    Returns:
        Fachliches Ergebnis der Verarbeitung.
    """
    for path in ROOT.rglob("*.py"):
        if any(part in {".venv", "__pycache__"} for part in path.parts):
            continue
        yield path


def apply_docstrings(path: Path) -> bool:
    """Wendet die vorbereiteten Änderungen in dem Modul an.

    Args:
        path: Dateipfad für den betroffenen Lese-/Schreibvorgang.

    Returns:
        Fachliches Ergebnis der Verarbeitung.
    """
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    lines = source.splitlines()
    inserts: list[tuple[int, list[str]]] = []

    def enqueue_doc(node: ast.AST, doc_lines: list[str], indent: str):
        """Verarbeitet den Schritt enqueue doc im Kontext von dem Modul.

        Args:
            node: Eingabewert für diesen Verarbeitungsschritt.
            doc_lines: Eingabewert für diesen Verarbeitungsschritt.
            indent: Eingabewert für diesen Verarbeitungsschritt.
        """
        if not hasattr(node, "body"):
            return
        body = getattr(node, "body")
        if not body:
            return
        first_stmt = body[0]
        if (
            isinstance(first_stmt, ast.Expr)
            and isinstance(getattr(first_stmt, "value", None), ast.Constant)
            and isinstance(first_stmt.value.value, str)
        ):
            return

        insertion_line = first_stmt.lineno - 1
        quoted = [f'{indent}"""{doc_lines[0]}']
        for line in doc_lines[1:]:
            quoted.append(f"{indent}{line}")
        quoted.append(f'{indent}"""')
        inserts.append((insertion_line, quoted))

    class_stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        """Stellt die Kernfunktionalität von Visitor bereit.

        Die Klasse fasst zusammengehörige Operationen zu einem klar abgegrenzten Baustein zusammen.
        """

        def visit_ClassDef(self, node: ast.ClassDef):
            """Verarbeitet den Schritt visit Class Def im Kontext von Visitor.

            Args:
                node: Eingabewert für diesen Verarbeitungsschritt.
            """
            indent = " " * (node.col_offset + 4)
            enqueue_doc(node, build_class_doc(node), indent)
            class_stack.append(node.name)
            self.generic_visit(node)
            class_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef):
            """Verarbeitet den Schritt visit Function Def im Kontext von Visitor.

            Args:
                node: Eingabewert für diesen Verarbeitungsschritt.
            """
            indent = " " * (node.col_offset + 4)
            current_class = class_stack[-1] if class_stack else None
            enqueue_doc(node, build_function_doc(node, current_class), indent)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            """Verarbeitet den Schritt visit Async Function Def im Kontext von Visitor.

            Args:
                node: Eingabewert für diesen Verarbeitungsschritt.
            """
            indent = " " * (node.col_offset + 4)
            current_class = class_stack[-1] if class_stack else None
            enqueue_doc(node, build_function_doc(node, current_class), indent)
            self.generic_visit(node)

    Visitor().visit(tree)

    if not inserts:
        return False

    for index, block in sorted(inserts, key=lambda item: item[0], reverse=True):
        lines[index:index] = block

    path.write_text("\n".join(lines) + ("\n" if source.endswith("\n") else ""), encoding="utf-8")
    return True


def main() -> None:
    """Verarbeitet den Schritt main im Kontext von dem Modul."""
    changed = 0
    for path in module_py_files():
        if apply_docstrings(path):
            changed += 1
    print(f"Docstrings ergänzt in {changed} Datei(en).")


if __name__ == "__main__":
    main()
