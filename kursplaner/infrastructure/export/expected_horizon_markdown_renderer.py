from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.usecases.export_expected_horizon_usecase import ExpectedHorizonDocument


@dataclass(frozen=True)
class _ExistingEhRow:
    datum: str
    ich_kann: str
    afb: str
    aufg: str
    pkte: str


class ExpectedHorizonMarkdownRenderer:
    """Rendert den Kompetenzhorizont als Markdown-Tabelle."""

    _COLUMN_HEADER = "| Datum | Die SuS können ... | AFB | Aufg | Pkte |"

    @staticmethod
    def _escape_cell(value: str) -> str:
        return str(value or "").replace("|", "\\|").replace("\n", " ").strip()

    @staticmethod
    def _bold(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return f"**{text}**"

    @staticmethod
    def _split_row(line: str) -> list[str]:
        text = str(line or "").strip()
        if not text.startswith("|"):
            return []
        return [cell.strip() for cell in text.strip("|").split("|")]

    @staticmethod
    def _strip_markdown_wrappers(value: str) -> str:
        text = str(value or "").strip()
        changed = True
        while changed and text:
            changed = False
            for marker in ("**", "~~"):
                if text.startswith(marker) and text.endswith(marker) and len(text) >= 2 * len(marker):
                    text = text[len(marker) : -len(marker)].strip()
                    changed = True
        return text

    @classmethod
    def _normalize_key(cls, datum: str, ich_kann: str) -> tuple[str, str]:
        normalized_datum = re.sub(r"\s+", " ", cls._strip_markdown_wrappers(datum)).strip()
        normalized_goal = re.sub(r"\s+", " ", cls._strip_markdown_wrappers(ich_kann)).strip()
        return normalized_datum, normalized_goal

    @classmethod
    def _load_existing_rows(cls, output_path: Path) -> list[_ExistingEhRow]:
        if not output_path.exists() or not output_path.is_file():
            return []

        try:
            text = output_path.read_text(encoding="utf-8")
        except Exception:
            return []

        lines = text.splitlines()
        header_index = -1
        for index, line in enumerate(lines):
            cells = cls._split_row(line)
            if len(cells) < 5:
                continue
            if cells[0] == "Datum" and cells[1].startswith("Die SuS können"):
                header_index = index
                break

        if header_index < 0 or (header_index + 1) >= len(lines):
            return []

        existing: list[_ExistingEhRow] = []
        for line in lines[header_index + 2 :]:
            if not str(line).strip().startswith("|"):
                continue
            cells = cls._split_row(line)
            if len(cells) < 5:
                continue
            existing.append(
                _ExistingEhRow(
                    datum=cells[0],
                    ich_kann=cells[1],
                    afb=cells[2],
                    aufg=cells[3],
                    pkte=cells[4],
                )
            )
        return existing

    @classmethod
    def _as_deleted_goal(cls, value: str) -> str:
        cleaned = cls._strip_markdown_wrappers(value)
        if not cleaned:
            return ""
        return f"~~{cleaned}~~"

    @classmethod
    def _merge_with_existing(
        cls,
        *,
        document: ExpectedHorizonDocument,
        output_path: Path,
    ) -> list[tuple[str, str, bool, str, str, str]]:
        existing_rows = cls._load_existing_rows(output_path)
        by_key: dict[tuple[str, str], list[int]] = {}
        for index, old in enumerate(existing_rows):
            key = cls._normalize_key(old.datum, old.ich_kann)
            by_key.setdefault(key, []).append(index)

        planned_rows: list[dict[str, object]] = []
        for row in document.rows:
            key = cls._normalize_key(row.datum, row.ich_kann)
            old_index: int | None = None
            old_index_matches = by_key.get(key, [])
            if old_index_matches:
                old_index = old_index_matches.pop(0)

            carry_afb = ""
            carry_aufg = ""
            carry_pkte = ""
            if old_index is not None:
                old = existing_rows[old_index]
                carry_afb = old.afb
                carry_aufg = old.aufg
                carry_pkte = old.pkte
            planned_rows.append(
                {
                    "old_index": old_index,
                    "row": (row.datum, row.ich_kann, row.is_main_goal, carry_afb, carry_aufg, carry_pkte),
                }
            )

        # New rows are anchored before the next matched old row, so old rows stay in place.
        before_old: dict[int, list[tuple[str, str, bool, str, str, str]]] = {}
        tail_new: list[tuple[str, str, bool, str, str, str]] = []
        for pos, entry in enumerate(planned_rows):
            if entry["old_index"] is not None:
                continue

            anchor: int | None = None
            for later in planned_rows[pos + 1 :]:
                later_old_index = later["old_index"]
                if isinstance(later_old_index, int):
                    anchor = later_old_index
                    break

            row_tuple = entry["row"]
            if anchor is None:
                tail_new.append(row_tuple)
            else:
                before_old.setdefault(anchor, []).append(row_tuple)

        matched_by_old_index: dict[int, tuple[str, str, bool, str, str, str]] = {}
        for entry in planned_rows:
            old_index = entry["old_index"]
            if isinstance(old_index, int):
                matched_by_old_index[old_index] = entry["row"]

        merged: list[tuple[str, str, bool, str, str, str]] = []
        for old_index, old in enumerate(existing_rows):
            merged.extend(before_old.get(old_index, []))

            replacement = matched_by_old_index.get(old_index)
            if replacement is not None:
                merged.append(replacement)
                continue

            has_right_values = any(str(cell).strip() for cell in (old.afb, old.aufg, old.pkte))
            if not has_right_values:
                continue

            merged.append(
                (
                    cls._strip_markdown_wrappers(old.datum),
                    cls._as_deleted_goal(old.ich_kann),
                    False,
                    old.afb,
                    old.aufg,
                    old.pkte,
                )
            )

        merged.extend(tail_new)
        return merged

    def render(self, document: ExpectedHorizonDocument, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        merged_rows = self._merge_with_existing(document=document, output_path=output_path)

        lines = [
            f"# {document.title}",
            "",
            document.subtitle,
            "",
            self._COLUMN_HEADER,
            "| --- | --- | --- | --- | --- |",
        ]

        for datum_value, goal_value, is_main_goal, afb, aufg, pkte in merged_rows:
            datum = self._escape_cell(datum_value)
            ich_kann = self._escape_cell(goal_value)
            if is_main_goal:
                datum = self._bold(datum)
                ich_kann = self._bold(ich_kann)
            lines.append(
                "| "
                + " | ".join(
                    [
                        datum,
                        ich_kann,
                        self._escape_cell(afb),
                        self._escape_cell(aufg),
                        self._escape_cell(pkte),
                    ]
                )
                + " |"
            )

        output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
