"""Lay the block model onto pages and hand it to the PDF canvas.

Typography is chosen for printed help guides and CVs: generous leading, a
single accent colour, hairline table rules and no colour behind body text.
Page breaks happen inside paragraphs and table rows, never inside a heading.
"""

from __future__ import annotations

import re

from .blocks import (
    Block,
    BulletList,
    CodeBlock,
    Heading,
    OrderedList,
    Paragraph,
    Quote,
    Rule,
    Span,
    Table,
    inline_text,
)
from .numbering import SectionNumbers
from .pdf import PdfCanvas, text_width
from .prefs import Prefs, accent_rgb

INK = (0.07, 0.10, 0.16)
BODY = (0.15, 0.18, 0.24)
MUTED = (0.42, 0.46, 0.54)
HAIRLINE = (0.84, 0.87, 0.91)
WASH = (0.95, 0.96, 0.98)
CODE_WASH = (0.12, 0.16, 0.22)
CODE_INK = (0.87, 0.91, 0.96)


def render_pdf(
    blocks: list[Block],
    title: str,
    prefs: Prefs | None = None,
    *,
    subject: str = "",
) -> bytes:
    return _PdfRenderer(blocks, title, prefs or Prefs(), subject).build()


def strip_inline(spans: list[Span]) -> str:
    return inline_text(spans)


class _PdfRenderer:
    def __init__(self, blocks: list[Block], title: str, prefs: Prefs, subject: str) -> None:
        self.blocks = blocks
        self.title = title
        self.prefs = prefs
        self.scale = prefs.font_scale
        self.body_size = 10.0 * self.scale
        self.leading = self.body_size * 1.52
        self.accent = accent_rgb(prefs.accent)
        self.canvas = PdfCanvas(
            prefs.page_size,
            title=title,
            author=prefs.author,
            subject=subject,
        )
        self.canvas.header = title
        self.left = self.canvas.margin_left
        self.width = self.canvas.content_width
        self.numbers = SectionNumbers()
        self.prefs_numbering = prefs.number_headings

    # -- text helpers -------------------------------------------------------
    def _font(self, span: Span) -> str:
        if span.code:
            return "F6" if span.bold else "F5"
        if span.bold and span.italic:
            return "F4"
        if span.bold:
            return "F2"
        if span.italic:
            return "F3"
        return "F1"

    def _wrap(
        self,
        spans: list[Span],
        size: float,
        width: float,
        *,
        bold_all: bool = False,
        font: str = "F1",
        colour: tuple[float, float, float] = BODY,
    ) -> list[list[tuple[str, str, tuple[float, float, float]]]]:
        """Greedy wrap into lines of (text, font, colour) runs."""
        tokens: list[tuple[str, str, tuple[float, float, float]]] = []
        for span in spans:
            run_font = font if bold_all else self._font(span)
            for part in re.split(r"(\s+)", span.text):
                if part:
                    tokens.append((part, run_font, colour))

        lines: list[list[tuple[str, str, tuple[float, float, float]]]] = []
        current: list[tuple[str, str, tuple[float, float, float]]] = []
        used = 0.0
        for text, run_font, run_colour in tokens:
            piece = text_width(text, run_font, size)
            if text.isspace():
                if current:
                    current.append((text, run_font, run_colour))
                    used += piece
                continue
            if current and used + piece > width:
                while current and current[-1][0].isspace():
                    current.pop()
                lines.append(current)
                current, used = [], 0.0
            if piece > width:
                # a single unbreakable token: hard-split it
                buffer = ""
                for char in text:
                    step = text_width(buffer + char, run_font, size)
                    if buffer and step > width:
                        lines.append([(buffer, run_font, run_colour)])
                        buffer = char
                    else:
                        buffer += char
                if buffer:
                    current = [(buffer, run_font, run_colour)]
                    used = text_width(buffer, run_font, size)
                continue
            current.append((text, run_font, run_colour))
            used += piece
        if current:
            while current and current[-1][0].isspace():
                current.pop()
            lines.append(current)
        return lines or [[]]

    def _draw_runs(
        self,
        runs: list[tuple[str, str, tuple[float, float, float]]],
        x: float,
        baseline: float,
        size: float,
    ) -> float:
        cursor = x
        for text, font, colour in runs:
            self.canvas.draw_text(cursor, baseline, text, font, size, colour)
            cursor += text_width(text, font, size)
        return cursor

    # -- block layout -------------------------------------------------------
    def build(self) -> bytes:
        for block in self.blocks:
            if isinstance(block, Heading):
                self.heading(block)
            elif isinstance(block, Paragraph):
                self.paragraph(block.content)
            elif isinstance(block, (BulletList, OrderedList)):
                self.list_block(block)
            elif isinstance(block, CodeBlock):
                self.code_block(block)
            elif isinstance(block, Quote):
                self.quote_block(block)
            elif isinstance(block, Table):
                self.table_block(block)
            elif isinstance(block, Rule):
                self.rule()
        return self.canvas.to_bytes()

    def heading(self, block: Heading) -> None:
        text = strip_inline(block.content)
        if self.prefs_numbering:
            text = f"{self.numbers.label(block.level)}  {text}"
        if self.prefs.caps_headings and block.level <= 3:
            text = text.upper()
        size = {1: 23.0, 2: 15.5, 3: 12.0}.get(block.level, 10.8) * self.scale
        before = {1: 6.0, 2: 20.0, 3: 15.0}.get(block.level, 11.0) * self.scale
        after = {1: 14.0, 2: 8.0, 3: 5.0}.get(block.level, 3.0) * self.scale
        colour = self.accent if block.level == 2 else INK
        if block.level == 1:
            colour = INK

        if self.canvas.y > self.canvas.margin_top:
            self.canvas.y += before
        self.canvas.need(size * 1.6 + after)

        spans = [Span(text, bold=True)]
        lines = self._wrap(spans, size, self.width, bold_all=True, font="F2", colour=colour)
        for line in lines:
            self.canvas.need(size * 1.4)
            self._draw_runs(line, self.left, self.canvas.y + size * 0.92, size)
            self.canvas.y += size * 1.28

        if block.level <= 2:
            weight = 1.6 if block.level == 1 else 0.9
            rule_colour = self.accent if block.level == 1 else HAIRLINE
            self.canvas.y += 2.0
            self.canvas.draw_line(self.left, self.canvas.y, self.left + self.width, self.canvas.y, weight, rule_colour)
            self.canvas.y += 4.0
        self.canvas.y += after

    def paragraph(
        self,
        content: list[Span],
        *,
        indent: float = 0.0,
        size: float | None = None,
        space_after: float = 7.0,
        colour: tuple[float, float, float] = BODY,
        italic: bool = False,
    ) -> None:
        size = size or self.body_size
        spans = [Span(s.text, s.bold, s.italic or italic, s.code, s.link) for s in content]
        lines = self._wrap(spans, size, self.width - indent, colour=colour)
        lead = size * 1.5
        for line in lines:
            self.canvas.need(lead)
            self._draw_runs(line, self.left + indent, self.canvas.y + size * 0.9, size)
            self.canvas.y += lead
        self.canvas.y += space_after

    def list_block(self, block: BulletList | OrderedList, depth: int = 0) -> None:
        ordered = isinstance(block, OrderedList)
        indent = 4.0 + depth * 15.0
        hang = 17.0
        size = self.body_size * (0.97 if depth else 1.0)
        lead = size * 1.48
        for index, item in enumerate(block.items):
            if ordered:
                marker = f"{(block.start or 1) + index}."
            elif item.checked is not None:
                marker = ""
            else:
                marker = "\u2022"
            lines = self._wrap(item.content, size, self.width - indent - hang)
            self.canvas.need(lead * len(lines) + 2)
            marker_y = self.canvas.y
            baseline = self.canvas.y + size * 0.9
            if item.checked is not None:
                box = size * 0.62
                self.canvas.rect(
                    self.left + indent + 1.5,
                    baseline - box * 0.86,
                    box,
                    box,
                    fill=(1, 1, 1),
                    stroke=MUTED,
                    line_width=0.7,
                )
                if item.checked:
                    self.canvas.draw_line(
                        self.left + indent + 2.6,
                        baseline - box * 0.45,
                        self.left + indent + box * 0.45,
                        baseline - box * 0.8,
                        1.1,
                        self.accent,
                    )
                    self.canvas.draw_line(
                        self.left + indent + box * 0.45,
                        baseline - box * 0.8,
                        self.left + indent + box * 1.05,
                        baseline - box * 0.2,
                        1.1,
                        self.accent,
                    )
            else:
                self.canvas.draw_text(
                    self.left + indent,
                    marker_y + size * 0.9,
                    marker,
                    "F2" if ordered else "F1",
                    size,
                    self.accent if ordered else MUTED,
                )
            for line in lines:
                self._draw_runs(line, self.left + indent + hang, baseline, size)
                baseline += lead
                self.canvas.y += lead
            for child in item.children:
                if isinstance(child, Paragraph):
                    self.paragraph(
                        child.content,
                        indent=indent + hang,
                        size=self.body_size * 0.96,
                        space_after=3.0,
                        colour=MUTED,
                    )
                elif isinstance(child, (BulletList, OrderedList)):
                    self.list_block(child, depth + 1)
                elif isinstance(child, CodeBlock):
                    self.code_block(child, indent=indent + hang)
                elif isinstance(child, Table):
                    self.table_block(child)
            self.canvas.y += 3.0
        self.canvas.y += 4.0

    def code_block(self, block: CodeBlock, indent: float = 0.0) -> None:
        size = 8.2 * self.scale
        lead = size * 1.5
        pad = 8.0
        self.canvas.y += 4.0
        for line in block.text.split("\n") or [""]:
            chunks = self._wrap([Span(line)], size, self.width - indent - pad * 2, font="F5", colour=CODE_INK)
            for chunk in chunks:
                self.canvas.need(lead + pad)
                self.canvas.rect(
                    self.left + indent,
                    self.canvas.y,
                    self.width - indent,
                    lead + pad * 0.6,
                    fill=CODE_WASH,
                )
                self._draw_runs(chunk, self.left + indent + pad, self.canvas.y + pad * 0.5 + size * 0.82, size)
                self.canvas.y += lead
        self.canvas.y += 10.0

    def quote_block(self, block: Quote) -> None:
        bar_height_before = self.canvas.y
        inner = block.blocks
        text_rows: list[tuple[list[Span], float]] = []
        for node in inner:
            if isinstance(node, Paragraph):
                text_rows.append((node.content, 0.0))
            elif isinstance(node, Heading):
                text_rows.append(([Span(strip_inline(node.content), bold=True)], 2.0))
            elif isinstance(node, (BulletList, OrderedList)):
                for item in node.items:
                    text_rows.append(([Span("\u2022 ", False), *item.content], 0.0))
        self.canvas.y += 4.0
        self.canvas.need(30.0)
        start_y = self.canvas.y
        for spans, extra in text_rows:
            self.canvas.y += extra
            self.paragraph(
                spans,
                indent=20.0,
                size=self.body_size * 0.96,
                space_after=3.0,
                colour=MUTED,
                italic=True,
            )
        end_y = self.canvas.y
        self.canvas.draw_line(self.left + 4, start_y, self.left + 4, max(start_y + 12, end_y - 4), 2.2, self.accent)
        self.canvas.y += 8.0
        del bar_height_before

    def table_block(self, block: Table) -> None:
        columns = block.columns
        if not columns:
            return
        size = self.body_size * 0.9
        pad_x, pad_y = 5.0, 4.0
        lead = size * 1.42

        natural: list[float] = []
        for index in range(columns):
            widest = text_width(strip_inline(block.header[index]) if index < len(block.header) else "", "F2", size)
            for row in block.rows:
                if index < len(row):
                    widest = max(widest, text_width(strip_inline(row[index]), "F1", size))
            natural.append(min(max(widest, 38.0), self.width * 0.55))
        total = sum(natural)
        budget = self.width - pad_x * columns
        widths = natural
        if total > budget:
            factor = budget / total
            widths = [max(34.0, value * factor) for value in natural]
            excess = sum(widths) - budget
            while excess > 0:
                widest = widths.index(max(widths))
                widths[widest] -= min(excess, 6.0)
                excess -= 6.0
                if widths[widest] <= 34.0:
                    break

        self.canvas.y += 4.0
        self._table_row(
            [strip_inline(cell) for cell in block.header] + [""] * (columns - len(block.header)),
            widths, size, pad_x, pad_y, lead, header=True,
        )
        for row in block.rows:
            cells = [strip_inline(cell) for cell in row] + [""] * (columns - len(row))
            self._table_row(cells, widths, size, pad_x, pad_y, lead, header=False)
        self.canvas.y += 8.0

    def _table_row(
        self,
        cells: list[str],
        widths: list[float],
        size: float,
        pad_x: float,
        pad_y: float,
        lead: float,
        *,
        header: bool,
    ) -> None:
        wrapped = [
            self._wrap(
                [Span(cell, bold=header)],
                size,
                widths[index] - pad_x * 2,
                bold_all=header,
                font="F2" if header else "F1",
                colour=INK if header else BODY,
            )
            for index, cell in enumerate(cells)
        ]
        height = max(len(lines) for lines in wrapped) * lead + pad_y * 2
        self.canvas.need(height)
        if header:
            self.canvas.rect(self.left, self.canvas.y, self.width, height, fill=WASH)
        baseline = self.canvas.y + pad_y + size * 0.92
        cursor = self.left
        for index, lines in enumerate(wrapped):
            for offset, line in enumerate(lines):
                self._draw_runs(line, cursor + pad_x, baseline + offset * lead, size)
            cursor += widths[index]
        self.canvas.y += height
        self.canvas.draw_line(self.left, self.canvas.y, self.left + self.width, self.canvas.y, 0.5, HAIRLINE)

    def rule(self) -> None:
        self.canvas.y += 8.0
        self.canvas.need(8.0)
        self.canvas.draw_line(self.left, self.canvas.y, self.left + self.width, self.canvas.y, 0.6, HAIRLINE)
        self.canvas.y += 10.0
