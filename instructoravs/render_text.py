"""Plain-text renderer: fixed width, ASCII tables, hanging indents.

This is what people paste into tickets and email, so markup is stripped rather
than rewritten, and every block gets a reading shape that survives a monospace
font.
"""

from __future__ import annotations

import textwrap

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
    inline_plain,
    inline_text,
)
from .numbering import SectionNumbers
from .prefs import Prefs


def render_text(blocks: list[Block], prefs: Prefs | None = None) -> str:
    renderer = _TextRenderer(prefs or Prefs())
    renderer.render(blocks)
    return renderer.finish()


class _TextRenderer:
    def __init__(self, prefs: Prefs) -> None:
        self.prefs = prefs
        self.width = prefs.text_width
        self.lines: list[str] = []
        self.numbers = SectionNumbers()

    # -- output plumbing ----------------------------------------------------
    def add(self, line: str = "") -> None:
        self.lines.append(line.rstrip())

    def blank(self) -> None:
        if self.lines and self.lines[-1] != "":
            self.add("")

    def paragraph(self, text: str, indent: str = "", hang: str = "") -> None:
        if not text:
            return
        available = max(20, self.width - len(indent))
        wrapped = textwrap.wrap(
            text,
            width=available,
            initial_indent=indent,
            subsequent_indent=hang or indent,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [indent]
        for line in wrapped:
            self.add(line)

    # -- inline -------------------------------------------------------------
    def inline(self, spans: list[Span]) -> str:
        parts: list[str] = []
        for span in spans:
            text = span.text
            if span.bold and self.prefs.text_emphasis == "stars":
                text = f"**{text}**"
            elif span.bold and self.prefs.text_emphasis == "caps":
                text = text.upper()
            if span.italic and self.prefs.text_emphasis == "stars":
                text = f"*{text}*"
            parts.append(text)
            if span.link and span.link not in (span.text, "mailto:" + span.text):
                parts.append(f" ({span.link})")
        return "".join(parts)

    # -- blocks -------------------------------------------------------------
    def render(self, blocks: list[Block], indent: str = "") -> None:
        for block in blocks:
            if isinstance(block, Heading):
                self.heading(block, indent)
            elif isinstance(block, Paragraph):
                self.paragraph(self.inline(block.content), indent=indent)
                self.blank()
            elif isinstance(block, (BulletList, OrderedList)):
                self.list_block(block, indent)
            elif isinstance(block, CodeBlock):
                self.code_block(block, indent)
            elif isinstance(block, Quote):
                self.quote_block(block, indent)
            elif isinstance(block, Table):
                self.table_block(block, indent)
            elif isinstance(block, Rule):
                self.blank()
                self.add(indent + "-" * min(self.width - len(indent), 72))
                self.blank()

    def heading(self, block: Heading, indent: str) -> None:
        text = self.inline(block.content)
        if self.prefs.number_headings:
            text = f"{self.numbers.label(block.level)} {text}"
        if self.prefs.caps_headings or block.level == 1:
            text = text.upper()
        self.blank()
        if block.level == 1:
            self.add(indent + text)
            self.add(indent + "=" * min(len(text), max(8, self.width - len(indent))))
        elif block.level == 2:
            self.add(indent + text)
            self.add(indent + "-" * min(len(text), max(8, self.width - len(indent))))
        elif block.level == 3:
            self.add(indent + text)
        else:
            self.paragraph(text, indent=indent + "  ")
        self.blank()

    def list_block(self, block: BulletList | OrderedList, indent: str) -> None:
        ordered = isinstance(block, OrderedList)
        for index, item in enumerate(block.items):
            if ordered:
                marker = f"{(block.start or 1) + index}."
            elif item.checked is not None:
                marker = "[x]" if item.checked else "[ ]"
            else:
                marker = "-"
            prefix = f"{indent}{marker} "
            text = self.inline(item.content)
            self.paragraph(text, indent=prefix, hang=" " * len(prefix))
            for child in item.children:
                if isinstance(child, Paragraph):
                    self.paragraph(
                        self.inline(child.content),
                        indent=indent + " " * len(marker) + "   ",
                    )
                else:
                    self.render([child], indent=indent + " " * (len(marker) + 3))
        self.blank()

    def code_block(self, block: CodeBlock, indent: str) -> None:
        self.blank()
        pad = indent + "    "
        for line in block.text.split("\n"):
            if len(line) + len(pad) <= self.width:
                self.add(pad + line)
            else:
                chunks = textwrap.wrap(
                    line,
                    width=max(20, self.width - len(pad)),
                    subsequent_indent="  ",
                    break_long_words=True,
                )
                for chunk in chunks:
                    self.add(pad + chunk)
        self.blank()

    def quote_block(self, block: Quote, indent: str) -> None:
        self.blank()
        captured: list[str] = self.lines
        self.lines = []
        self.render(block.blocks)
        inner = self.lines
        self.lines = captured
        prefix = indent + "| "
        for line in inner:
            if not line:
                self.add(prefix.rstrip())
                continue
            for chunk in textwrap.wrap(
                line,
                width=max(20, self.width - len(prefix)),
                break_long_words=False,
            ):
                self.add(prefix + chunk)
        self.blank()

    def table_block(self, block: Table, indent: str) -> None:
        columns = block.columns
        if columns == 0:
            return
        header = [inline_text(cell) for cell in block.header]
        header += [""] * (columns - len(header))
        rows = [[inline_text(cell) for cell in row] for row in block.rows]
        for row in rows:
            row += [""] * (columns - len(row))

        widths = [
            max([len(header[i])] + [len(row[i]) for row in rows]) if rows else len(header[i])
            for i in range(columns)
        ]
        budget = self.width - len(indent) - (3 * columns + 1)
        while sum(widths) > budget and max(widths) > 8:
            widest = widths.index(max(widths))
            widths[widest] -= 1

        def cell_lines(value: str, width: int) -> list[str]:
            if not value:
                return [""]
            return textwrap.wrap(value, width=max(4, width), break_long_words=True) or [""]

        border = indent + "+" + "+".join("-" * (width + 2) for width in widths) + "+"

        def emit_row(cells: list[str], bold: bool = False) -> None:
            wrapped = [cell_lines(cells[i], widths[i]) for i in range(columns)]
            height = max(len(part) for part in wrapped)
            for line in range(height):
                parts = []
                for i in range(columns):
                    text = wrapped[i][line] if line < len(wrapped[i]) else ""
                    parts.append(" " + text.ljust(widths[i]) + " ")
                self.add(indent + "|" + "|".join(parts) + "|")

        self.blank()
        self.add(border)
        emit_row(header)
        self.add(border)
        for row in rows:
            emit_row(row)
            self.add(border)
        self.blank()

    def finish(self) -> str:
        cleaned: list[str] = []
        for line in self.lines:
            if line == "" and cleaned and cleaned[-1] == "":
                continue
            cleaned.append(line)
        while cleaned and cleaned[0] == "":
            cleaned.pop(0)
        while cleaned and cleaned[-1] == "":
            cleaned.pop()
        return "\n".join(cleaned) + "\n"
