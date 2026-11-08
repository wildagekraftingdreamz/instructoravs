"""Block model back to canonical Markdown.

This is the storage format: whatever a version holds must parse back to the
same structure, so re-rendering an old version never changes its content.
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
)
from .numbering import SectionNumbers
from .prefs import Prefs


def render_markdown(blocks: list[Block], prefs: Prefs | None = None) -> str:
    prefs = prefs or Prefs()
    body = _render_blocks(blocks, prefs, numbers=SectionNumbers())
    return body.strip("\n") + "\n"


def inline_markdown(spans: list[Span]) -> str:
    out: list[str] = []
    for span in spans:
        text = span.text.replace("*", r"\*").replace("`", r"\`") if not span.code else span.text
        if span.code:
            piece = f"`{text}`"
        elif span.bold and span.italic:
            piece = f"***{text}***"
        elif span.bold:
            piece = f"**{text}**"
        elif span.italic:
            piece = f"*{text}*"
        else:
            piece = text
        if span.link:
            label = span.text.replace("]", r"\]")
            if span.link == "mailto:" + span.text:
                piece = f"<{span.link}>"
            else:
                piece = f"[{label}]({span.link})"
        out.append(piece)
    return "".join(out)


def _render_blocks(blocks: list[Block], prefs: Prefs, numbers: SectionNumbers) -> str:
    chunks: list[str] = []
    for block in blocks:
        if isinstance(block, Heading):
            # Numbers are a display choice for text/PDF only; stored Markdown keeps
            # headings clean so a round-trip cannot number them twice.
            text = inline_markdown(block.content)
            chunks.append(f"{'#' * block.level} {text}")
        elif isinstance(block, Paragraph):
            chunks.append(inline_markdown(block.content))
        elif isinstance(block, (BulletList, OrderedList)):
            chunks.append(_render_list(block, prefs, numbers))
        elif isinstance(block, CodeBlock):
            chunks.append(f"```{block.language}\n{block.text}\n```")
        elif isinstance(block, Quote):
            inner = _render_blocks(block.blocks, prefs, numbers)
            quoted = "\n".join(
                f"> {line}" if line else ">" for line in inner.split("\n")
            )
            chunks.append(quoted.rstrip())
        elif isinstance(block, Table):
            chunks.append(_render_table(block))
        elif isinstance(block, Rule):
            chunks.append("---")
    return "\n\n".join(chunk for chunk in chunks if chunk.strip())


def _render_list(block: BulletList | OrderedList, prefs: Prefs, numbers: SectionNumbers) -> str:
    lines: list[str] = []
    ordered = isinstance(block, OrderedList)
    for index, item in enumerate(block.items):
        if ordered:
            marker = f"{(block.start or 1) + index}."
        elif item.checked is not None:
            marker = f"- [{'x' if item.checked else ' '}]"
        else:
            marker = "-"
        text = inline_markdown(item.content)
        if not text and item.children:
            text = ""
        lines.append(f"{marker} {text}".rstrip())
        if item.children:
            indent = " " * (len(marker) + 1)
            child = _render_blocks(item.children, prefs, numbers)
            for line in child.split("\n"):
                lines.append(indent + line if line else "")
            lines.append("")
    # collapse the blank separator lines between top-level items
    cleaned: list[str] = []
    for line in lines:
        if line == "" and (not cleaned or cleaned[-1] == ""):
            continue
        cleaned.append(line)
    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    return "\n".join(cleaned)


def _render_table(block: Table) -> str:
    columns = block.columns
    header = "| " + " | ".join(inline_markdown(cell) or " " for cell in block.header) + " |"
    aligns = list(block.align) + ["left"] * (columns - len(block.align))
    separators = []
    for align in aligns[:columns]:
        separators.append({"center": ":---:", "right": "---:", "left": "---"}[align])
    sep = "| " + " | ".join(separators) + " |"
    rows = [
        "| " + " | ".join(inline_markdown(cell) or " " for cell in row) + " |"
        for row in block.rows
    ]
    return "\n".join([header, sep, *rows])


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:48] or "document"
