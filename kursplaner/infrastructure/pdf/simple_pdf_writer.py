from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PdfPage:
    width: int
    height: int
    stream: str


class SimplePdfWriter:
    """Kleiner stdlib-only PDF-Writer fuer Text/Linien ohne externe Abhaengigkeiten."""

    def __init__(self):
        self._pages: list[PdfPage] = []

    @staticmethod
    def _escape_text(value: str) -> str:
        text = str(value or "")
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def add_page(self, *, width: int, height: int, stream_commands: list[str]) -> None:
        stream = "\n".join(stream_commands)
        self._pages.append(PdfPage(width=width, height=height, stream=stream))

    @classmethod
    def text_command(cls, *, x: float, y: float, text: str, size: float, font_key: str = "F1") -> str:
        escaped = cls._escape_text(text)
        return f"BT /{font_key} {size:.2f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({escaped}) Tj ET"

    @staticmethod
    def line_command(*, x1: float, y1: float, x2: float, y2: float, width: float = 1.0) -> str:
        return f"{width:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S"

    def write_to(self, output_path: Path) -> None:
        if not self._pages:
            raise RuntimeError("PDF hat keine Seiten.")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        page_count = len(self._pages)
        font_regular_id = 3
        font_bold_id = 4
        first_page_id = 5

        object_entries: list[bytes] = []

        # 1: Catalog (Pages-Objekt ist 2)
        object_entries.append(b"<< /Type /Catalog /Pages 2 0 R >>")

        # 2: Pages
        page_ids = [first_page_id + index * 2 for index in range(page_count)]
        kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
        object_entries.append(f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode("latin-1"))

        # 3-4: Fonts
        object_entries.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        object_entries.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

        for index, page in enumerate(self._pages):
            page_id = first_page_id + index * 2
            content_id = page_id + 1

            page_obj = (
                "<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {page.width} {page.height}] "
                "/Resources << /Font << "
                f"/F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R"
                " >> >> "
                f"/Contents {content_id} 0 R >>"
            )
            object_entries.append(page_obj.encode("latin-1"))

            stream_bytes = page.stream.encode("latin-1", errors="replace")
            content_obj = (
                f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("latin-1") + stream_bytes + b"\nendstream"
            )
            object_entries.append(content_obj)

        pdf_bytes = bytearray()
        pdf_bytes.extend(b"%PDF-1.4\n")

        offsets = [0]
        for object_id, payload in enumerate(object_entries, start=1):
            offsets.append(len(pdf_bytes))
            pdf_bytes.extend(f"{object_id} 0 obj\n".encode("latin-1"))
            pdf_bytes.extend(payload)
            pdf_bytes.extend(b"\nendobj\n")

        xref_offset = len(pdf_bytes)
        object_count = len(object_entries)
        pdf_bytes.extend(f"xref\n0 {object_count + 1}\n".encode("latin-1"))
        pdf_bytes.extend(b"0000000000 65535 f \n")
        for object_id in range(1, object_count + 1):
            pdf_bytes.extend(f"{offsets[object_id]:010d} 00000 n \n".encode("latin-1"))

        trailer = f"trailer\n<< /Size {object_count + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
        pdf_bytes.extend(trailer.encode("latin-1"))

        output_path.write_bytes(bytes(pdf_bytes))
