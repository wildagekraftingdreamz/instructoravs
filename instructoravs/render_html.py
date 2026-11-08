"""HTML renderer: a fragment for the app preview, a print-ready page for export."""

from __future__ import annotations

import html

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
from .prefs import Prefs

_STANDALONE_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; background: #f4f6fb; color: #17202f;
  font: 15px/1.65 "Segoe UI", system-ui, -apple-system, sans-serif; }
main { max-width: 820px; margin: 0 auto; padding: 48px 32px 64px;
  background: #fff; box-shadow: 0 12px 40px rgba(15, 23, 42, .08); }
h1, h2, h3, h4 { line-height: 1.25; color: #12203a; }
h1 { font-size: 30px; margin: 0 0 18px; letter-spacing: -.01em; }
h2 { font-size: 20px; margin: 34px 0 10px; padding-bottom: 6px;
  border-bottom: 1px solid #e3e8f1; }
h3 { font-size: 16px; margin: 24px 0 8px; }
p { margin: 0 0 12px; }
a { color: #0f6f83; }
ul, ol { padding-left: 22px; margin: 0 0 14px; }
li { margin: 4px 0; }
li.task { list-style: none; margin-left: -18px; }
li.task .box { display: inline-block; width: 15px; color: #0f6f83; }
table { border-collapse: collapse; width: 100%; margin: 14px 0 18px; font-size: 14px; }
th, td { border: 1px solid #dfe5f0; padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: #eef3f9; font-size: 12.5px; text-transform: uppercase;
  letter-spacing: .06em; color: #4a5772; }
code { background: #eef3f9; padding: 1px 5px; border-radius: 4px;
  font: 13px/1.4 "Cascadia Code", ui-monospace, monospace; }
pre { background: #0f1622; color: #dbe4f0; padding: 16px; border-radius: 10px;
  overflow-x: auto; font: 13px/1.5 "Cascadia Code", ui-monospace, monospace; }
pre code { background: none; padding: 0; color: inherit; }
blockquote { margin: 16px 0; padding: 10px 16px; border-left: 3px solid #2aa7bd;
  background: #eef8fa; color: #33415c; border-radius: 0 8px 8px 0; }
hr { border: 0; border-top: 1px solid #e3e8f1; margin: 26px 0; }
@page { margin: 18mm 16mm; }
@media print {
  body { background: #fff; }
  main { box-shadow: none; padding: 0; max-width: none; }
  h2, h3 { break-after: avoid; }
  tr, pre, blockquote { break-inside: avoid; }
}
"""


def render_html_fragment(blocks: list[Block], prefs: Prefs | None = None) -> str:
    """Just the article body: the web app supplies the (dark) styling."""
    prefs = prefs or Prefs()
    body = _render_blocks(blocks, prefs)
    return f'<article class="doc">\n{body}\n</article>'


def render_html(blocks: list[Block], title: str = "", prefs: Prefs | None = None) -> str:
    """A complete HTML file that prints well and reads well in a browser."""
    prefs = prefs or Prefs()
    body = _render_blocks(blocks, prefs)
    safe_title = html.escape(title or "Document")
    accent = html.escape(prefs.accent)
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{safe_title}</title>\n<style>{_STANDALONE_CSS}"
        f"h2 {{ border-bottom-color: {accent}33; }}"
        f"blockquote {{ border-left-color: {accent}; }}"
        "</style>\n</head>\n<body>\n<main>\n"
        f"{body}\n</main>\n</body>\n</html>\n"
    )


def _render_blocks(blocks: list[Block], prefs: Prefs) -> str:
    out: list[str] = []
    for block in blocks:
        if isinstance(block, Heading):
            level = max(1, min(6, block.level))
            out.append(f"<h{level}>{_inline(block.content)}</h{level}>")
        elif isinstance(block, Paragraph):
            out.append(f"<p>{_inline(block.content)}</p>")
        elif isinstance(block, (BulletList, OrderedList)):
            ordered = isinstance(block, OrderedList)
            tag = "ol" if ordered else "ul"
            attr = f' start="{block.start}"' if ordered and block.start != 1 else ""
            items = []
            for item in block.items:
                if item.checked is not None:
                    glyph = "&#9745;" if item.checked else "&#9744;"
                    body = (
                        f'<li class="task"><span class="box">{glyph}</span>'
                        f"{_inline(item.content)}"
                    )
                    inner = _render_blocks(item.children, prefs)
                    items.append(body + (f"\n{inner}" if inner else "") + "</li>")
                else:
                    inner = _render_blocks(item.children, prefs)
                    items.append(
                        f"<li>{_inline(item.content)}"
                        + (f"\n{inner}" if inner else "")
                        + "</li>"
                    )
            out.append(f"<{tag}{attr}>\n" + "\n".join(items) + f"\n</{tag}>")
        elif isinstance(block, CodeBlock):
            language = f' class="language-{html.escape(block.language)}"' if block.language else ""
            out.append(f"<pre><code{language}>{html.escape(block.text)}</code></pre>")
        elif isinstance(block, Quote):
            out.append(f"<blockquote>\n{_render_blocks(block.blocks, prefs)}\n</blockquote>")
        elif isinstance(block, Table):
            columns = block.columns
            head = "".join(f"<th>{_inline(cell)}</th>" for cell in block.header)
            rows = []
            for row in block.rows:
                cells = []
                for index in range(columns):
                    cell = row[index] if index < len(row) else []
                    cells.append(f"<td>{_inline(cell)}</td>")
                rows.append("<tr>" + "".join(cells) + "</tr>")
            out.append(
                "<table>\n<thead><tr>"
                + head
                + "</tr></thead>\n<tbody>\n"
                + "\n".join(rows)
                + "\n</tbody>\n</table>"
            )
        elif isinstance(block, Rule):
            out.append("<hr>")
    return "\n".join(out)


def _inline(spans: list[Span]) -> str:
    out: list[str] = []
    for span in spans:
        text = html.escape(span.text)
        if span.code:
            text = f"<code>{text}</code>"
        if span.bold:
            text = f"<strong>{text}</strong>"
        if span.italic:
            text = f"<em>{text}</em>"
        if span.link:
            href = html.escape(span.link, quote=True)
            text = f'<a href="{href}" rel="noreferrer">{text}</a>'
        out.append(text)
    return "".join(out)
