"""Exports for other tools: spreadsheets, slides, JSON pipelines."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .blocks import (
    Block,
    BulletList,
    CodeBlock,
    Heading,
    OrderedList,
    Paragraph,
    Quote,
    Rule,
    Table,
    inline_text,
)

EXPORT_FORMATS = ("md", "txt", "pdf", "docx", "html", "csv", "json", "slides")


def step_rows(blocks: list[Block]) -> list[dict[str, str]]:
    """One row per step, with its section, title and detail, for a spreadsheet."""
    rows: list[dict[str, str]] = []
    section = ""

    def walk(nodes: list[Block]) -> None:
        nonlocal section
        for node in nodes:
            if isinstance(node, Heading):
                if node.level <= 2:
                    section = inline_text(node.content)
                else:
                    section = section or inline_text(node.content)
            elif isinstance(node, (OrderedList, BulletList)):
                for index, item in enumerate(node.items, start=1):
                    if isinstance(node, BulletList) and item.checked is None and len(node.items) > 6:
                        continue
                    detail = " ".join(
                        inline_text(child.content)
                        for child in item.children
                        if isinstance(child, Paragraph)
                    )
                    marker = "" if item.checked is None else ("done" if item.checked else "todo")
                    rows.append(
                        {
                            "section": section,
                            "order": str(index),
                            "step": inline_text(item.content),
                            "detail": detail,
                            "status": marker,
                        }
                    )
                    walk(
                        [child for child in item.children if not isinstance(child, Paragraph)]
                    )
            elif isinstance(node, Table):
                for row in node.rows:
                    cells = [inline_text(cell) for cell in row]
                    rows.append(
                        {
                            "section": section,
                            "order": "",
                            "step": cells[0] if cells else "",
                            "detail": " — ".join(cells[1:]),
                            "status": "",
                        }
                    )
            elif isinstance(node, Quote):
                walk(node.blocks)

    walk(blocks)
    return rows


def to_csv(blocks: list[Block]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=["section", "order", "step", "detail", "status"], lineterminator="\n"
    )
    writer.writeheader()
    for row in step_rows(blocks):
        writer.writerow(row)
    return buffer.getvalue()


def block_to_dict(block: Block) -> dict[str, Any]:
    if isinstance(block, Heading):
        return {"type": "heading", "level": block.level, "text": inline_text(block.content)}
    if isinstance(block, Paragraph):
        return {"type": "paragraph", "text": inline_text(block.content)}
    if isinstance(block, (BulletList, OrderedList)):
        return {
            "type": "ordered_list" if isinstance(block, OrderedList) else "bullet_list",
            "start": getattr(block, "start", None),
            "items": [
                {
                    "text": inline_text(item.content),
                    "checked": item.checked,
                    "children": [block_to_dict(child) for child in item.children],
                }
                for item in block.items
            ],
        }
    if isinstance(block, CodeBlock):
        return {"type": "code", "language": block.language, "text": block.text}
    if isinstance(block, Quote):
        return {"type": "quote", "blocks": [block_to_dict(child) for child in block.blocks]}
    if isinstance(block, Table):
        return {
            "type": "table",
            "header": [inline_text(cell) for cell in block.header],
            "rows": [[inline_text(cell) for cell in row] for row in block.rows],
        }
    if isinstance(block, Rule):
        return {"type": "rule"}
    return {"type": "unknown"}


def to_json(blocks: list[Block], meta: dict[str, Any] | None = None) -> str:
    payload = {
        "meta": meta or {},
        "steps": step_rows(blocks),
        "blocks": [block_to_dict(block) for block in blocks],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def to_slides(blocks: list[Block], title: str) -> str:
    """A Marp/Slidev-friendly outline: one slide per second-level heading."""
    lines: list[str] = ["---", "marp: true", "paginate: true", f"title: {title}", "---", ""]
    lines.append(f"# {title}")
    lines.append("")

    current: list[Block] | None = None
    groups: list[tuple[str, list[Block]]] = []
    for block in blocks:
        if isinstance(block, Heading) and block.level == 2:
            current = []
            groups.append((inline_text(block.content), current))
        elif isinstance(block, Heading) and block.level == 1:
            continue
        elif current is None:
            continue
        else:
            current.append(block)

    for heading, content in groups:
        lines.append("---")
        lines.append("")
        lines.append(f"## {heading}")
        lines.append("")
        bullets: list[str] = []
        for block in content:
            if isinstance(block, Paragraph):
                bullets.append(inline_text(block.content))
            elif isinstance(block, (BulletList, OrderedList)):
                for item in block.items:
                    text = inline_text(item.content)
                    if text:
                        bullets.append(text)
            elif isinstance(block, Table):
                for row in block.rows[:5]:
                    cells = [inline_text(cell) for cell in row]
                    bullets.append(" — ".join(cells))
        for bullet in bullets[:6]:
            if len(bullet) > 180:
                bullet = bullet[:177].rstrip() + "…"
            lines.append(f"- {bullet}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
