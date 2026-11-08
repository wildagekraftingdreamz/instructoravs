"""A small PDF writer built on the standard library alone.

Only what a document needs is here: base-14 fonts (so nothing is embedded),
flate-compressed content streams, a real xref table, and a top-down coordinate
system (``y`` is measured from the top edge) because that is how text layout
is reasoned about.  No reportlab, no external binary, no per-platform wheel.
"""

from __future__ import annotations

import zlib
from datetime import datetime

PAGE_SIZES = {"a4": (595.28, 841.89), "letter": (612.0, 792.0)}

FONTS = (
    ("F1", "Helvetica"),
    ("F2", "Helvetica-Bold"),
    ("F3", "Helvetica-Oblique"),
    ("F4", "Helvetica-BoldOblique"),
    ("F5", "Courier"),
    ("F6", "Courier-Bold"),
)

# Helvetica AFM widths for ASCII 32..126, in 1/1000 em.
_HELVETICA = (
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
)
_HELVETICA_BOLD = (
    278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
    975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
    333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
    611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584,
)

_WIDTH_TABLES = {
    "F1": _HELVETICA,
    "F2": _HELVETICA_BOLD,
    "F3": _HELVETICA,
    "F4": _HELVETICA_BOLD,
    "F5": None,  # Courier is fixed pitch
    "F6": None,
}


def text_width(text: str, font: str = "F1", size: float = 11.0) -> float:
    """Width of a string in points, using the base-14 metrics."""
    table = _WIDTH_TABLES.get(font)
    if table is None:
        return 0.6 * size * len(text)
    total = 0
    for char in text:
        code = ord(char)
        total += table[code - 32] if 32 <= code <= 126 else 556
    return total * size / 1000.0


def encode_text(text: str) -> str:
    """Map text to the WinAnsi byte range and escape it for a PDF string."""
    out: list[str] = []
    for byte in text.encode("cp1252", "replace"):
        if byte in (0x28, 0x29, 0x5C):  # ( ) backslash
            out.append("\\")
        out.append(chr(byte))
    return "".join(out)


def pdf_date(moment: datetime | None = None) -> str:
    moment = moment or datetime.now()
    offset = moment.astimezone().strftime("%z") or "+0000"
    return moment.strftime("D:%Y%m%d%H%M%S") + offset[:3] + "'" + offset[3:] + "'"


class PdfCanvas:
    """Pages of raw content-stream operators, plus the document wrapper."""

    def __init__(
        self,
        page_size: str = "a4",
        margins: tuple[float, float, float, float] = (56.0, 56.0, 54.0, 58.0),
        title: str = "",
        author: str = "Instructoravs",
        subject: str = "",
    ) -> None:
        self.page_size = page_size if page_size in PAGE_SIZES else "a4"
        self.width, self.height = PAGE_SIZES[self.page_size]
        self.margin_left, self.margin_right, self.margin_top, self.margin_bottom = margins
        self.title = title
        self.author = author
        self.subject = subject
        self.header = ""
        self.footer_left = "Instructoravs"
        self.pages: list[list[str]] = [[]]
        self.y = self.margin_top

    # -- geometry -----------------------------------------------------------
    @property
    def content_width(self) -> float:
        return self.width - self.margin_left - self.margin_right

    @property
    def right_edge(self) -> float:
        return self.width - self.margin_right

    @property
    def has_content(self) -> bool:
        return bool(self.pages[-1])

    def space_left(self) -> float:
        return self.height - self.margin_bottom - self.y

    def need(self, height: float) -> bool:
        if self.y + height > self.height - self.margin_bottom and self.has_content:
            self.new_page()
            return True
        return False

    def new_page(self) -> None:
        self.pages.append([])
        self.y = self.margin_top

    # -- drawing primitives -------------------------------------------------
    def draw_text(
        self,
        x: float,
        y: float,
        text: str,
        font: str = "F1",
        size: float = 11.0,
        color: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        if not text:
            return
        self.pages[-1].append(
            "BT /{} {:.2f} Tf {:.3f} {:.3f} {:.3f} rg 1 0 0 1 {:.2f} {:.2f} Tm ({}) Tj ET".format(
                font, size, *color, x, self.height - y, encode_text(text)
            )
        )

    def draw_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        width: float = 0.6,
        color: tuple[float, float, float] = (0.75, 0.78, 0.84),
    ) -> None:
        self.pages[-1].append(
            "{:.3f} {:.3f} {:.3f} RG {:.2f} w {:.2f} {:.2f} m {:.2f} {:.2f} l S".format(
                *color, width, x1, self.height - y1, x2, self.height - y2
            )
        )

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        fill: tuple[float, float, float] | None = None,
        stroke: tuple[float, float, float] | None = None,
        line_width: float = 0.6,
    ) -> None:
        base = f"{x:.2f} {self.height - y - height:.2f} {width:.2f} {height:.2f} re"
        if fill is not None:
            self.pages[-1].append("{:.3f} {:.3f} {:.3f} rg {} f".format(*fill, base))
        if stroke is not None:
            self.pages[-1].append(
                "{:.3f} {:.3f} {:.3f} RG {:.2f} w {} S".format(*stroke, line_width, base)
            )

    # -- furniture ----------------------------------------------------------
    def _furniture(self, page_index: int, total: int) -> list[str]:
        ops: list[str] = []
        baseline = 24.0
        if page_index > 0 and self.header:
            self._push(ops, "F1", 8.5, (0.45, 0.48, 0.55), self.margin_left, 34.0, self.header)
            self._push(
                ops, "F1", 8.5, (0.45, 0.48, 0.55),
                self.right_edge - text_width(f"Instructoravs / {self.title}", "F1", 8.5),
                34.0, f"Instructoravs / {self.title}",
            )
            ops.append(
                "{:.3f} {:.3f} {:.3f} RG 0.5 w {:.2f} {:.2f} m {:.2f} {:.2f} l S".format(
                    0.85, 0.88, 0.92,
                    self.margin_left, self.height - 43.0,
                    self.right_edge, self.height - 43.0,
                )
            )
        if self.footer_left:
            self._push(
                ops, "F1", 8.5, (0.45, 0.48, 0.55),
                self.margin_left, self.height - baseline, self.footer_left,
            )
        label = f"Page {page_index + 1} of {total}"
        self._push(
            ops, "F1", 8.5, (0.45, 0.48, 0.55),
            self.right_edge - text_width(label, "F1", 8.5),
            self.height - baseline,
            label,
        )
        return ops

    def _push(
        self,
        ops: list[str],
        font: str,
        size: float,
        color: tuple[float, float, float],
        x: float,
        y_from_top: float,
        text: str,
    ) -> None:
        ops.append(
            "BT /{} {:.2f} Tf {:.3f} {:.3f} {:.3f} rg 1 0 0 1 {:.2f} {:.2f} Tm ({}) Tj ET".format(
                font, size, *color, x, self.height - y_from_top, encode_text(text)
            )
        )

    # -- output -------------------------------------------------------------
    def to_bytes(self) -> bytes:
        total = len(self.pages)
        streams: list[bytes] = []
        for index, ops in enumerate(self.pages):
            body = list(ops)
            body.extend(self._furniture(index, total))
            streams.append(zlib.compress("\n".join(body).encode("latin-1", "replace")))

        count = len(streams)
        page_start = 3
        content_start = page_start + count
        font_start = content_start + count
        info_number = font_start + len(FONTS)
        objects: list[bytes | None] = [None] * (info_number + 1)

        kids = " ".join(f"{page_start + i} 0 R" for i in range(count))
        objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
        objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {count} >>".encode()

        font_refs = " ".join(
            f"/{name} {font_start + index} 0 R" for index, (name, _) in enumerate(FONTS)
        )
        resources = (
            f"<< /Font << {font_refs} >> /ProcSet [/PDF /Text] >>"
        )
        for index in range(count):
            objects[page_start + index] = (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.width:.2f} {self.height:.2f}]"
                f" /Resources {resources} /Contents {content_start + index} 0 R >>"
            ).encode()

        for index, data in enumerate(streams):
            objects[content_start + index] = (
                b"<< /Length " + str(len(data)).encode() + b" /Filter /FlateDecode >>\nstream\n"
                + data + b"\nendstream"
            )

        for index, (name, base) in enumerate(FONTS):
            objects[font_start + index] = (
                f"<< /Type /Font /Subtype /Type1 /BaseFont /{base}"
                f" /Encoding /WinAnsiEncoding >>"
            ).encode()

        info = (
            f"<< /Title ({encode_text(self.title)}) /Author ({encode_text(self.author)})"
            f" /Subject ({encode_text(self.subject)}) /Producer (Instructoravs)"
            f" /Creator (Instructoravs) /CreationDate ({pdf_date()}) >>"
        )
        objects[info_number] = info.encode("latin-1", "replace")

        out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0] * len(objects)
        for number in range(1, len(objects)):
            payload = objects[number]
            assert payload is not None
            offsets[number] = len(out)
            out += f"{number} 0 obj\n".encode() + payload + b"\nendobj\n"

        xref_at = len(out)
        out += f"xref\n0 {len(objects)}\n".encode()
        out += b"0000000000 65535 f \n"
        for number in range(1, len(objects)):
            out += f"{offsets[number]:010d} 00000 n \n".encode()
        out += (
            f"trailer\n<< /Size {len(objects)} /Root 1 0 R /Info {info_number} 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n"
        ).encode()
        return bytes(out)

    def save(self, path) -> int:
        data = self.to_bytes()
        with open(path, "wb") as handle:
            handle.write(data)
        return len(data)
