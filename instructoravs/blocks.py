"""The document model every renderer reads.

Markdown is the storage format, but layout decisions (page breaks, hanging
indents, table column widths) need structure, so Markdown is parsed into these
blocks first and each renderer walks that tree.  Keeping one model is what lets
a stored ``content.md`` be re-rendered to PDF years later without drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator, Sequence


@dataclass(frozen=True)
class Span:
    """A run of text with one style. Links carry their target separately."""

    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    link: str | None = None


Inline = list[Span]


def inline_text(spans: Sequence[Span]) -> str:
    """The visible characters of an inline run, with no markup at all."""
    return "".join(span.text for span in spans)


def inline_plain(spans: Sequence[Span]) -> str:
    """Visible text, with link targets written out for plain-text readers."""
    out: list[str] = []
    for span in spans:
        out.append(span.text)
        if span.link and span.link not in (span.text, "mailto:" + span.text):
            out.append(f" ({span.link})")
    return "".join(out)


class Block:
    """Marker base class so the union below stays readable."""


@dataclass
class Heading(Block):
    level: int
    content: Inline = field(default_factory=list)


@dataclass
class Paragraph(Block):
    content: Inline = field(default_factory=list)


@dataclass
class ListItem:
    content: Inline = field(default_factory=list)
    children: list["Block"] = field(default_factory=list)
    checked: bool | None = None


@dataclass
class BulletList(Block):
    items: list[ListItem] = field(default_factory=list)


@dataclass
class OrderedList(Block):
    items: list[ListItem] = field(default_factory=list)
    start: int = 1


@dataclass
class CodeBlock(Block):
    text: str = ""
    language: str = ""


@dataclass
class Quote(Block):
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Table(Block):
    header: list[Inline] = field(default_factory=list)
    rows: list[list[Inline]] = field(default_factory=list)
    align: list[str] = field(default_factory=list)

    @property
    def columns(self) -> int:
        return max([len(self.header)] + [len(row) for row in self.rows] + [0])


@dataclass
class Rule(Block):
    """A horizontal rule, used as a visual break between sections."""


BlockLike = Heading | Paragraph | BulletList | OrderedList | CodeBlock | Quote | Table | Rule


def iter_blocks(blocks: Iterable[Block]) -> Iterator[Block]:
    """Depth-first walk over a document, including nested list/quote content."""
    for block in blocks:
        yield block
        if isinstance(block, (BulletList, OrderedList)):
            for item in block.items:
                yield from iter_blocks(item.children)
        elif isinstance(block, Quote):
            yield from iter_blocks(block.blocks)


def collect_headings(blocks: Iterable[Block]) -> list[tuple[int, str]]:
    return [(b.level, inline_text(b.content)) for b in iter_blocks(blocks) if isinstance(b, Heading)]


def word_count(blocks: Iterable[Block]) -> int:
    total = 0
    for block in iter_blocks(blocks):
        if isinstance(block, Heading):
            total += len(inline_text(block.content).split())
        elif isinstance(block, Paragraph):
            total += len(inline_text(block.content).split())
        elif isinstance(block, (BulletList, OrderedList)):
            for item in block.items:
                total += len(inline_text(item.content).split())
        elif isinstance(block, CodeBlock):
            total += len(block.text.split())
        elif isinstance(block, Table):
            for cell in block.header:
                total += len(inline_text(cell).split())
            for row in block.rows:
                for cell in row:
                    total += len(inline_text(cell).split())
    return total
