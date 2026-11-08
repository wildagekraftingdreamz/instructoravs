"""Markdown in, block model out.

Only the subset the engine itself emits is supported: ATX/setext headings,
paragraphs, bullet/ordered/check lists (nested), fenced code, pipe tables,
block quotes, rules and the usual inline emphasis, code spans and links.
Anything else is treated as text rather than dropped, so an imported README
still produces a usable document.
"""

from __future__ import annotations

import re

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
    Span,
    Table,
)

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([^`~]*)$")
_BULLET = re.compile(r"^(\s*)([-*+])\s+(.*)$")
_ORDERED = re.compile(r"^(\s*)(\d{1,3})[.)]\s+(.*)$")
_HR = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_SETEXT = re.compile(r"^\s*(=+|-+)\s*$")
_QUOTE = re.compile(r"^\s*>\s?(.*)$")
_CHECK = re.compile(r"^\[([ xX])\]\s+(.*)$")
_SEP_CELL = re.compile(r"^:?-{2,}:?$")

_MASK = {
    "\\\\": "\ue000",
    "\\*": "\ue001",
    "\\_": "\ue002",
    "\\`": "\ue003",
    "\\[": "\ue004",
    "\\]": "\ue005",
    "\\(": "\ue006",
    "\\)": "\ue007",
    "\\|": "\ue008",
}
_UNMASK = {v: k[1:] for k, v in _MASK.items()}

_INLINE = re.compile(
    r"(?P<code>`[^`\n]+`)"
    r"|(?P<link>\[(?P<label>[^\]\n]*)\]\((?P<href>[^)\s]+)\))"
    r"|(?P<auto><(?:https?://|mailto:)[^>\s]+>)"
    r"|(?P<bi>\*\*\*(?=\S).+?(?<=\S)\*\*\*)"
    r"|(?P<bold>\*\*(?=\S).+?(?<=\S)\*\*|__(?=\S).+?(?<=\S)__)"
    r"|(?P<ital>\*(?=[^\s*])[^*\n]+?(?<=[^\s*])\*|_(?=[^\s_])[^_\n]+?(?<=[^\s_])_)"
)


def parse_inline(text: str) -> list[Span]:
    """Parse emphasis, code spans and links in one line of text."""
    if not text:
        return []
    masked = text
    for raw, token in _MASK.items():
        masked = masked.replace(raw, token)

    spans: list[Span] = []
    pos = 0
    for match in _INLINE.finditer(masked):
        if match.start() > pos:
            spans.append(Span(_restore(masked[pos : match.start()])))
        token = match.group(0)
        if match.group("code") is not None:
            spans.append(Span(_restore(token[1:-1]), code=True))
        elif match.group("link") is not None:
            label = _restore(match.group("label")) or match.group("href")
            spans.append(Span(label, link=match.group("href")))
        elif match.group("auto") is not None:
            target = token[1:-1]
            if target.startswith("mailto:"):
                spans.append(Span(target[7:], link=target))
            else:
                spans.append(Span(target, link=target))
        elif match.group("bi") is not None:
            spans.append(Span(_restore(token[3:-3]), bold=True, italic=True))
        elif match.group("bold") is not None:
            inner = token[2:-2]
            spans.append(Span(_restore(inner), bold=True))
        else:
            inner = token[1:-1]
            spans.append(Span(_restore(inner), italic=True))
        pos = match.end()
    if pos < len(masked):
        spans.append(Span(_restore(masked[pos:])))
    return [span for span in spans if span.text != ""]


def _restore(text: str) -> str:
    for token, raw in _UNMASK.items():
        text = text.replace(token, raw)
    return text


# -- block parsing ---------------------------------------------------------
def parse_markdown(text: str) -> list[Block]:
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return _parse(lines)


def _parse(lines: list[str]) -> list[Block]:
    blocks: list[Block] = []
    stack: list[dict] = []
    i, n = 0, len(lines)

    def close_to(indent: int) -> None:
        while stack and stack[-1]["indent"] > indent:
            stack.pop()

    def place(block: Block, indent: int) -> None:
        if stack and indent > stack[-1]["indent"] and stack[-1]["item"] is not None:
            stack[-1]["item"].children.append(block)
        else:
            stack.clear()
            blocks.append(block)

    while i < n:
        raw = lines[i].rstrip()
        if not raw.strip():
            i += 1
            continue

        fm = _FENCE.match(raw)
        if fm:
            indent = _indent(fm.group(1))
            fence_char = fm.group(2)[0]
            i += 1
            body: list[str] = []
            while i < n:
                closing = _FENCE.match(lines[i].rstrip())
                if (
                    closing
                    and closing.group(2)[0] == fence_char
                    and not closing.group(3).strip()
                ):
                    i += 1
                    break
                body.append(_dedent(lines[i], indent))
                i += 1
            place(CodeBlock(text="\n".join(body), language=fm.group(3).strip()), indent)
            continue

        hm = _HEADING.match(raw)
        if hm:
            place(Heading(len(hm.group(1)), parse_inline(hm.group(2))), _line_indent(raw))
            i += 1
            continue

        if raw.strip() and i + 1 < n and _SETEXT.match(lines[i + 1]) and not _is_marker(raw):
            level = 1 if "=" in lines[i + 1] else 2
            place(Heading(level, parse_inline(raw.strip())), _line_indent(raw))
            i += 2
            continue

        if _HR.match(raw):
            place(Rule(), _line_indent(raw))
            i += 1
            continue

        if _QUOTE.match(raw):
            indent = _line_indent(raw)
            buf: list[str] = []
            while i < n:
                qm = _QUOTE.match(lines[i])
                if qm:
                    buf.append(qm.group(1))
                    i += 1
                elif not lines[i].strip():
                    buf.append("")
                    i += 1
                else:
                    break
            while buf and not buf[-1].strip():
                buf.pop()
            place(Quote(_parse(buf)), indent)
            continue

        if "|" in raw and i + 1 < n and _is_table_separator(lines[i + 1]):
            indent = _line_indent(raw)
            header = [parse_inline(cell) for cell in _cells(raw)]
            align = [_alignment(cell) for cell in _cells(lines[i + 1])]
            rows: list[list[list[Span]]] = []
            i += 2
            while i < n and lines[i].strip() and "|" in lines[i]:
                rows.append([parse_inline(cell) for cell in _cells(lines[i])])
                i += 1
            width = max([len(header)] + [len(row) for row in rows])
            header += [[] for _ in range(width - len(header))]
            for row in rows:
                row += [[] for _ in range(width - len(row))]
            place(Table(header=header, rows=rows, align=align), indent)
            continue

        bm = _BULLET.match(raw)
        om = _ORDERED.match(raw)
        if bm or om:
            match = bm or om
            assert match is not None
            indent = _indent(match.group(1))
            ordered = om is not None
            body = match.group(3)
            checked: bool | None = None
            check = _CHECK.match(body)
            if check and not ordered:
                checked = check.group(1).lower() == "x"
                body = check.group(2)
            close_to(indent)
            target = None
            if stack and stack[-1]["indent"] == indent:
                if stack[-1]["ordered"] == ordered:
                    target = stack[-1]
                else:
                    stack.pop()
            if target is None:
                lst: Block
                if ordered:
                    lst = OrderedList(items=[], start=int(om.group(2)) if om else 1)
                else:
                    lst = BulletList(items=[])
                node = {"indent": indent, "block": lst, "item": None, "ordered": ordered}
                parent = stack[-1]["item"] if stack else None
                stack.append(node)
                if parent is not None:
                    parent.children.append(lst)
                else:
                    blocks.append(lst)
                target = node
            item = ListItem(content=parse_inline(body), checked=checked)
            target["block"].items.append(item)
            target["item"] = item
            i += 1
            continue

        # paragraph (or an indented paragraph that belongs to the last item)
        indent = _line_indent(raw)
        buf = [raw.strip()]
        i += 1
        while i < n:
            nxt = lines[i]
            if not nxt.strip():
                break
            if _starts_block(nxt):
                break
            buf.append(nxt.strip())
            i += 1
        place(Paragraph(parse_inline(" ".join(buf))), indent)

    return blocks


def _starts_block(line: str) -> bool:
    if _HEADING.match(line) or _FENCE.match(line) or _HR.match(line) or _QUOTE.match(line):
        return True
    if _BULLET.match(line) or _ORDERED.match(line):
        return True
    if "|" in line and _is_table_separator(line):
        return True
    return False


def _is_marker(line: str) -> bool:
    return bool(_BULLET.match(line) or _ORDERED.match(line) or _HR.match(line))


def _indent(prefix: str) -> int:
    return len(prefix.expandtabs(4))


def _line_indent(line: str) -> int:
    stripped = line.lstrip(" \t")
    return _indent(line[: len(line) - len(stripped)])


def _dedent(line: str, count: int) -> str:
    removed = 0
    index = 0
    while index < len(line) and removed < count and line[index] in " \t":
        removed += 1 if line[index] == " " else 4
        index += 1
    return line[index:]


def _cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _is_table_separator(line: str) -> bool:
    if "-" not in line:
        return False
    cells = _cells(line)
    return len(cells) >= 2 and all(_SEP_CELL.match(cell) for cell in cells)


def _alignment(cell: str) -> str:
    cell = cell.strip()
    if cell.startswith(":") and cell.endswith(":"):
        return "center"
    if cell.endswith(":"):
        return "right"
    return "left"
