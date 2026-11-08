"""Block constructors that take Markdown-ish strings.

Guide and CV producers read better with ``h(2, "Before you begin")`` than with
a dataclass literal, and the inline parser is the single place that turns
``**bold**`` into spans.
"""

from __future__ import annotations

from .blocks import (
    Block,
    BulletList,
    CodeBlock,
    Heading,
    ListItem,
    OrderedList,
    Paragraph,
    Quote,
    Rule,
    Table,
)
from .markdown import parse_inline


def h(level: int, text: str) -> Heading:
    return Heading(level=max(1, min(6, level)), content=parse_inline(text))


def p(text: str = "") -> Paragraph:
    return Paragraph(content=parse_inline(text))


def _item(text: str, checked: bool | None = None) -> ListItem:
    return ListItem(content=parse_inline(text), checked=checked)


def bullets(items: list[str], checked: bool | None = None) -> BulletList:
    return BulletList(items=[_item(t, checked) for t in items])


def checklist(items: list[str], done: bool = False) -> BulletList:
    return BulletList(items=[_item(t, done) for t in items])


def steps(items: list[str | tuple[str, str]]) -> OrderedList:
    """Ordered steps; a ``(title, detail)`` pair becomes a titled child block."""
    out: list[ListItem] = []
    for item in items:
        if isinstance(item, tuple):
            title, detail = item
            node = _item(title)
            if detail:
                node.children.append(p(detail))
            out.append(node)
        else:
            out.append(_item(item))
    return OrderedList(items=out)


def code(text: str, language: str = "") -> CodeBlock:
    return CodeBlock(text=text.strip("\n"), language=language)


def quote(*blocks: Block) -> Quote:
    return Quote(blocks=list(blocks))


def rule() -> Rule:
    return Rule()


def table(header: list[str], rows: list[list[str]], align: list[str] | None = None) -> Table:
    return Table(
        header=[parse_inline(cell) for cell in header],
        rows=[[parse_inline(cell) for cell in row] for row in rows],
        align=align or [],
    )


def kv_table(pairs: list[tuple[str, str]]) -> Table:
    """A two-column key/value table, the shape document control blocks use."""
    return table(["Field", "Value"], [[k, v] for k, v in pairs])
