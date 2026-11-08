"""DOCX renderer: the same block model as the preview, in Word form.

The project deliberately has no runtime dependencies, so this writes Office
Open XML directly instead of importing python-docx.  The result uses Word
heading styles, real tables, list indents, a shaded code treatment and a page
footer, which keeps a downloaded guide or CV visually close to the studio
preview while remaining editable in Word.
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape

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
from .prefs import Prefs

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_CORE_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_DC_NS = "http://purl.org/dc/elements/1.1/"
_DCTERMS_NS = "http://purl.org/dc/terms/"
_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
_EP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
_VT_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"

_CONTENT_WIDTH = 9026  # A4 with 1.1 in side margins, in twips.
_DARK = "12203A"
_BODY = "17202F"
_MUTED = "5A6477"
_HAIRLINE = "DFE5F0"
_WASH = "EEF3F9"
_CODE_BG = "0F1622"
_CODE_INK = "DBE4F0"


def render_docx(
    blocks: list[Block],
    title: str,
    prefs: Prefs | None = None,
    *,
    subject: str = "",
) -> bytes:
    """Render a guide or CV as a Word document."""
    return _DocxRenderer(blocks, title, prefs or Prefs(), subject).build()


def _xml(value: object) -> str:
    text = str(value or "")
    # XML 1.0 cannot represent most C0 control characters.
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return escape(text, {'"': "&quot;"})


def _twips(points: float) -> int:
    return max(1, int(round(points * 20)))


def _half_points(points: float) -> int:
    return max(1, int(round(points * 2)))


class _DocxRenderer:
    def __init__(self, blocks: list[Block], title: str, prefs: Prefs, subject: str) -> None:
        self.blocks = blocks
        self.title = title or "Document"
        self.prefs = prefs
        self.subject = subject
        self.scale = prefs.font_scale
        self.accent = prefs.accent.lstrip("#").upper()
        self.numbering = SectionNumbers()
        self._link_ids: dict[str, int] = {}
        self._links: list[str] = []

    # -- XML primitives -----------------------------------------------------
    def _run(
        self,
        text: str,
        *,
        bold: bool = False,
        italic: bool = False,
        code: bool = False,
        link: str | None = None,
        color: str | None = None,
        size: float | None = None,
        underline: bool = False,
        shading: str | None = None,
        symbol: bool = False,
    ) -> str:
        props: list[str] = []
        if link:
            props.append('<w:rStyle w:val="Hyperlink"/>')
        if code:
            props.append(
                '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" '
                'w:eastAsia="Consolas" w:cs="Consolas"/>'
            )
        elif symbol:
            props.append(
                '<w:rFonts w:ascii="Segoe UI Symbol" w:hAnsi="Segoe UI Symbol" '
                'w:eastAsia="Segoe UI Symbol" w:cs="Segoe UI Symbol"/>'
            )
        else:
            props.append(
                '<w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI" '
                'w:eastAsia="Segoe UI" w:cs="Segoe UI"/>'
            )
        if bold:
            props.append("<w:b/><w:bCs/>")
        if italic:
            props.append("<w:i/><w:iCs/>")
        if color:
            props.append(f'<w:color w:val="{color}"/>')
        if size:
            props.append(f'<w:sz w:val="{_half_points(size)}"/><w:szCs w:val="{_half_points(size)}"/>')
        if underline or link:
            props.append('<w:u w:val="single"/>')
        if shading:
            props.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{shading}"/>')
        run = (
            "<w:r><w:rPr>"
            + "".join(props)
            + "</w:rPr><w:t xml:space=\"preserve\">"
            + _xml(text)
            + "</w:t></w:r>"
        )
        if link:
            rid = self._relationship_for(link)
            return f'<w:hyperlink r:id="rId{rid}" w:history="1">{run}</w:hyperlink>'
        return run

    def _inline(
        self,
        spans: list[Span],
        *,
        bold: bool = False,
        italic: bool = False,
        color: str | None = None,
        size: float | None = None,
    ) -> str:
        if not spans:
            return ""
        return "".join(
            self._run(
                span.text,
                bold=bold or span.bold,
                italic=italic or span.italic,
                code=span.code,
                link=span.link,
                color=color,
                size=size,
            )
            for span in spans
        )

    def _p(self, inner: str, *, style: str = "Normal", extra: str = "") -> str:
        return (
            "<w:p><w:pPr>"
            + f'<w:pStyle w:val="{style}"/>'
            + extra
            + "</w:pPr>"
            + inner
            + "</w:p>"
        )

    def _relationship_for(self, target: str) -> int:
        if target not in self._link_ids:
            self._link_ids[target] = 10 + len(self._link_ids)
            self._links.append(target)
        return self._link_ids[target]

    # -- block renderers ----------------------------------------------------
    def build(self) -> bytes:
        body: list[str] = []
        for block in self.blocks:
            body.append(self._block(block))
        document = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:document xmlns:w="{_W_NS}" xmlns:r="{_R_NS}">'
            "<w:body>"
            + "".join(body)
            + self._sect_pr()
            + "</w:body></w:document>"
        )
        return self._zip(
            {
                "[Content_Types].xml": self._content_types(),
                "_rels/.rels": self._package_rels(),
                "docProps/core.xml": self._core_props(),
                "docProps/app.xml": self._app_props(),
                "word/document.xml": document,
                "word/styles.xml": self._styles(),
                "word/numbering.xml": self._numbering(),
                "word/settings.xml": self._settings(),
                "word/footer1.xml": self._footer(),
                "word/_rels/document.xml.rels": self._document_rels(),
            }
        )

    def _block(self, block: Block, *, level: int = 0, quote: bool = False) -> str:
        if isinstance(block, Heading):
            return self._heading(block)
        if isinstance(block, Paragraph):
            return self._paragraph(block, quote=quote)
        if isinstance(block, (BulletList, OrderedList)):
            return self._list(block, level=level)
        if isinstance(block, CodeBlock):
            return self._code(block)
        if isinstance(block, Quote):
            return "".join(self._block(child, level=level, quote=True) for child in block.blocks)
        if isinstance(block, Table):
            return self._table(block)
        if isinstance(block, Rule):
            return self._rule()
        return ""

    def _heading(self, block: Heading) -> str:
        text = inline_text(block.content)
        if self.prefs.number_headings:
            text = f"{self.numbering.label(block.level)}  {text}"
        if self.prefs.caps_headings and block.level <= 3:
            text = text.upper()
        sizes = {1: 21.0, 2: 14.0, 3: 11.5}
        size = sizes.get(block.level, 10.8) * self.scale
        before = {1: 0.0, 2: 14.0, 3: 10.0}.get(block.level, 8.0) * self.scale
        after = {1: 8.0, 2: 5.0, 3: 3.0}.get(block.level, 2.0) * self.scale
        color = _DARK if block.level >= 2 else _DARK
        border = ""
        if block.level == 1:
            border = (
                '<w:pBdr><w:bottom w:val="single" w:sz="12" w:space="5" '
                f'w:color="{self.accent}"/></w:pBdr>'
            )
        elif block.level == 2:
            border = (
                '<w:pBdr><w:bottom w:val="single" w:sz="4" w:space="4" '
                f'w:color="{_HAIRLINE}"/></w:pBdr>'
            )
        extra = (
            "<w:keepNext/><w:keepLines/>"
            + border
            + f'<w:spacing w:before="{_twips(before)}" w:after="{_twips(after)}" '
            'w:line="240" w:lineRule="auto"/>'
            + f'<w:outlineLvl w:val="{max(0, block.level - 1)}"/>'
        )
        inner = self._run(text, bold=True, color=color, size=size)
        return self._p(inner, style=f"Heading{min(block.level, 3)}", extra=extra)

    def _paragraph(self, block: Paragraph, *, quote: bool = False) -> str:
        extra = '<w:spacing w:after="120" w:line="276" w:lineRule="auto"/>'
        if quote:
            extra = (
                '<w:pBdr><w:left w:val="single" w:sz="18" w:space="8" '
                f'w:color="{self.accent}"/></w:pBdr>'
                '<w:shd w:val="clear" w:color="auto" w:fill="EEF8FA"/>'
                '<w:spacing w:after="120" w:line="276" w:lineRule="auto"/>'
                '<w:ind w:left="360" w:right="120"/>'
            )
        inner = self._inline(block.content, italic=quote, color=_MUTED if quote else None)
        return self._p(inner, extra=extra)

    def _list(self, block: BulletList | OrderedList, *, level: int = 0) -> str:
        ordered = isinstance(block, OrderedList)
        out: list[str] = []
        for index, item in enumerate(block.items):
            left = 720 + level * 360
            if item.checked is not None:
                marker = "☒" if item.checked else "☐"
                extra = (
                    '<w:spacing w:after="60" w:line="264" w:lineRule="auto"/>'
                    f'<w:ind w:left="{left}" w:hanging="360"/>'
                )
                inner = self._run(
                    marker + " ",
                    symbol=True,
                    color=self.accent if item.checked else _MUTED,
                    size=10.5,
                ) + self._inline(item.content)
            elif ordered:
                marker = f"{block.start + index}."
                extra = (
                    '<w:spacing w:after="60" w:line="264" w:lineRule="auto"/>'
                    f'<w:ind w:left="{left}" w:hanging="360"/>'
                )
                inner = self._run(marker + " ", bold=True, color=self.accent) + self._inline(
                    item.content
                )
            else:
                extra = (
                    '<w:pStyle w:val="ListParagraph"/>'
                    '<w:numPr>'
                    f'<w:ilvl w:val="{min(level, 2)}"/>'
                    '<w:numId w:val="1"/>'
                    "</w:numPr>"
                    '<w:spacing w:after="60" w:line="264" w:lineRule="auto"/>'
                )
                inner = self._inline(item.content)
            out.append(self._p(inner, extra=extra))

            for child in item.children:
                if isinstance(child, Paragraph):
                    child_extra = (
                        f'<w:ind w:left="{left + 360}"/>'
                        '<w:spacing w:after="60" w:line="264" w:lineRule="auto"/>'
                    )
                    out.append(
                        self._p(
                            self._inline(child.content, color=_MUTED, size=10.0),
                            style="ListParagraph",
                            extra=child_extra,
                        )
                    )
                elif isinstance(child, (BulletList, OrderedList)):
                    out.append(self._list(child, level=level + 1))
                elif isinstance(child, CodeBlock):
                    out.append(self._code(child))
                elif isinstance(child, Table):
                    out.append(self._table(child))
                elif isinstance(child, Quote):
                    out.append(self._block(child, level=level + 1, quote=True))
        return "".join(out)

    def _code(self, block: CodeBlock) -> str:
        out: list[str] = []
        lines = block.text.split("\n") or [""]
        for index, line in enumerate(lines):
            before = "80" if index == 0 else "0"
            after = "80" if index == len(lines) - 1 else "0"
            extra = (
                '<w:pStyle w:val="CodeBlock"/>'
                f'<w:shd w:val="clear" w:color="auto" w:fill="{_CODE_BG}"/>'
                f'<w:spacing w:before="{before}" w:after="{after}" w:line="240" w:lineRule="auto"/>'
                '<w:ind w:left="120" w:right="120"/>'
            )
            out.append(
                self._p(
                    self._run(line or " ", code=True, color=_CODE_INK, size=8.4),
                    style="CodeBlock",
                    extra=extra,
                )
            )
        return "".join(out)

    def _table(self, block: Table) -> str:
        columns = block.columns
        if not columns:
            return ""
        header = block.header
        rows = block.rows
        show_header = bool(header and any(inline_text(cell).strip() for cell in header))
        all_rows = ([header] if show_header else []) + rows
        if not all_rows:
            return ""

        natural = []
        for index in range(columns):
            values = [inline_text(row[index]) if index < len(row) else "" for row in all_rows]
            natural.append(max(6, min(48, max((len(value) for value in values), default=6))))
        total = sum(natural)
        widths = [max(900, int(_CONTENT_WIDTH * value / total)) for value in natural]
        widths[-1] += _CONTENT_WIDTH - sum(widths)

        grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in widths)
        out = [
            "<w:tbl><w:tblPr>"
            '<w:tblW w:w="5000" w:type="pct"/>'
            '<w:tblBorders>'
            f'<w:top w:val="single" w:sz="4" w:space="0" w:color="{_HAIRLINE}"/>'
            f'<w:left w:val="single" w:sz="4" w:space="0" w:color="{_HAIRLINE}"/>'
            f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="{_HAIRLINE}"/>'
            f'<w:right w:val="single" w:sz="4" w:space="0" w:color="{_HAIRLINE}"/>'
            f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="{_HAIRLINE}"/>'
            f'<w:insideV w:val="single" w:sz="4" w:space="0" w:color="{_HAIRLINE}"/>'
            "</w:tblBorders>"
            '<w:tblLayout w:type="autofit"/>'
            '<w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
            '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar>'
            "</w:tblPr>"
            f"<w:tblGrid>{grid}</w:tblGrid>"
        ]
        for row_index, row in enumerate(all_rows):
            is_header = show_header and row_index == 0
            tr_pr = "<w:trPr><w:cantSplit/>"
            if is_header:
                tr_pr += "<w:tblHeader/>"
            tr_pr += "</w:trPr>"
            out.append(f"<w:tr>{tr_pr}")
            for index, width in enumerate(widths):
                cell = row[index] if index < len(row) else []
                shade = f'<w:shd w:val="clear" w:color="auto" w:fill="{_WASH}"/>' if is_header else ""
                out.append(
                    "<w:tc><w:tcPr>"
                    f'<w:tcW w:w="{width}" w:type="dxa"/>'
                    + shade
                    + "</w:tcPr>"
                )
                inner = self._inline(
                    cell,
                    bold=is_header,
                    color="4A5772" if is_header else None,
                    size=9.0 if is_header else 9.5,
                )
                out.append(
                    self._p(
                        inner,
                        extra='<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>',
                    )
                )
                out.append("</w:tc>")
            out.append("</w:tr>")
        out.append("</w:tbl>")
        # A tiny spacer keeps following text from touching the last rule.
        out.append(self._p("", extra='<w:spacing w:after="0" w:line="120" w:lineRule="auto"/>'))
        return "".join(out)

    def _rule(self) -> str:
        extra = (
            '<w:pBdr><w:bottom w:val="single" w:sz="4" w:space="1" '
            f'w:color="{_HAIRLINE}"/></w:pBdr>'
            '<w:spacing w:before="160" w:after="160" w:line="120" w:lineRule="auto"/>'
        )
        return self._p("", extra=extra)

    # -- package parts ------------------------------------------------------
    def _sect_pr(self) -> str:
        return (
            "<w:sectPr>"
            '<w:footerReference w:type="default" r:id="rId4"/>'
            '<w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
            'w:header="720" w:footer="720" w:gutter="0"/>'
            '<w:cols w:space="720"/>'
            '<w:docGrid w:linePitch="360"/>'
            "</w:sectPr>"
        )

    def _content_types(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Types xmlns="{_CT_NS}">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
            '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
            '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            "</Types>"
        )

    def _package_rels(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{_PKG_NS}">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            "</Relationships>"
        )

    def _core_props(self) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<cp:coreProperties xmlns:cp="{_CORE_NS}" xmlns:dc="{_DC_NS}" '
            f'xmlns:dcterms="{_DCTERMS_NS}" xmlns:xsi="{_XSI_NS}">'
            f"<dc:title>{_xml(self.title)}</dc:title>"
            f"<dc:subject>{_xml(self.subject or 'Instructoravs document')}</dc:subject>"
            f"<dc:creator>{_xml(self.prefs.author)}</dc:creator>"
            f"<cp:lastModifiedBy>{_xml(self.prefs.author)}</cp:lastModifiedBy>"
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{stamp}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{stamp}</dcterms:modified>'
            "<cp:revision>1</cp:revision>"
            "</cp:coreProperties>"
        )

    def _app_props(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Properties xmlns="{_EP_NS}" xmlns:vt="{_VT_NS}">'
            "<Application>Instructoravs</Application>"
            "<DocSecurity>0</DocSecurity><ScaleCrop>false</ScaleCrop>"
            "<LinksUpToDate>false</LinksUpToDate><SharedDoc>false</SharedDoc>"
            "<HyperlinksChanged>false</HyperlinksChanged><AppVersion>1.0</AppVersion>"
            "</Properties>"
        )

    def _document_rels(self) -> str:
        rels = [
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>',
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>',
            '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>',
        ]
        for target, rid in self._link_ids.items():
            rels.append(
                f'<Relationship Id="rId{rid}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                f'Target="{_xml(target)}" TargetMode="External"/>'
            )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{_PKG_NS}">' + "".join(rels) + "</Relationships>"
        )

    def _styles(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:styles xmlns:w="{_W_NS}">'
            "<w:docDefaults><w:rPrDefault><w:rPr>"
            '<w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI" w:eastAsia="Segoe UI" w:cs="Segoe UI"/>'
            f'<w:color w:val="{_BODY}"/><w:sz w:val="21"/><w:szCs w:val="21"/>'
            '<w:lang w:val="en-GB" w:eastAsia="en-GB" w:bidi="ar-SA"/>'
            "</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>"
            '<w:spacing w:after="120" w:line="276" w:lineRule="auto"/>'
            "</w:pPr></w:pPrDefault></w:docDefaults>"
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
            '<w:name w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr>'
            f'<w:rPr><w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI"/><w:color w:val="{_BODY}"/>'
            '<w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading1">'
            '<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
            '<w:uiPriority w:val="9"/><w:qFormat/>'
            '<w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="0" w:after="160" w:line="240" w:lineRule="auto"/>'
            '<w:outlineLvl w:val="0"/></w:pPr>'
            f'<w:rPr><w:b/><w:bCs/><w:color w:val="{_DARK}"/><w:sz w:val="42"/><w:szCs w:val="42"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading2">'
            '<w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
            '<w:uiPriority w:val="9"/><w:qFormat/>'
            '<w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="280" w:after="100" w:line="240" w:lineRule="auto"/>'
            '<w:outlineLvl w:val="1"/></w:pPr>'
            f'<w:rPr><w:b/><w:bCs/><w:color w:val="{_DARK}"/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading3">'
            '<w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
            '<w:uiPriority w:val="9"/><w:qFormat/>'
            '<w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="200" w:after="60" w:line="240" w:lineRule="auto"/>'
            '<w:outlineLvl w:val="2"/></w:pPr>'
            f'<w:rPr><w:b/><w:bCs/><w:color w:val="{_DARK}"/><w:sz w:val="23"/><w:szCs w:val="23"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="ListParagraph">'
            '<w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:spacing w:after="60" w:line="264" w:lineRule="auto"/></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="CodeBlock">'
            '<w:name w:val="Code Block"/><w:basedOn w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
            '<w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:color w:val="DBE4F0"/>'
            '<w:sz w:val="17"/><w:szCs w:val="17"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Footer">'
            '<w:name w:val="footer"/><w:basedOn w:val="Normal"/>'
            '<w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="right"/></w:pPr>'
            '<w:rPr><w:color w:val="6B7280"/><w:sz w:val="16"/><w:szCs w:val="16"/></w:rPr></w:style>'
            '<w:style w:type="character" w:styleId="Hyperlink">'
            '<w:name w:val="Hyperlink"/>'
            f'<w:rPr><w:color w:val="{self.accent}"/><w:u w:val="single"/></w:rPr></w:style>'
            "</w:styles>"
        )

    def _numbering(self) -> str:
        levels = []
        for level in range(3):
            levels.append(
                f'<w:lvl w:ilvl="{level}"><w:start w:val="1"/><w:numFmt w:val="bullet"/>'
                '<w:lvlText w:val="•"/><w:lvlJc w:val="left"/>'
                f'<w:pPr><w:ind w:left="{720 + level * 360}" w:hanging="360"/></w:pPr>'
                '<w:rPr><w:rFonts w:ascii="Segoe UI Symbol" w:hAnsi="Segoe UI Symbol"/>'
                f'<w:color w:val="{_MUTED}"/></w:rPr></w:lvl>'
            )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:numbering xmlns:w="{_W_NS}">'
            '<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="hybridMultilevel"/>'
            + "".join(levels)
            + '</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
            "</w:numbering>"
        )

    def _settings(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:settings xmlns:w="{_W_NS}">'
            '<w:zoom w:percent="100"/><w:defaultTabStop w:val="720"/>'
            '<w:characterSpacingControl w:val="doNotCompress"/>'
            "</w:settings>"
        )

    def _footer(self) -> str:
        accent = self.accent
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:ftr xmlns:w="{_W_NS}" xmlns:r="{_R_NS}">'
            '<w:p><w:pPr><w:pStyle w:val="Footer"/><w:jc w:val="right"/></w:pPr>'
            '<w:r><w:rPr><w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI"/>'
            f'<w:color w:val="{_MUTED}"/><w:sz w:val="16"/></w:rPr>'
            f'<w:t xml:space="preserve">{_xml(self.title)}  ·  Page </w:t></w:r>'
            '<w:fldSimple w:instr=" PAGE "><w:r><w:rPr><w:color w:val="6B7280"/>'
            '<w:sz w:val="16"/></w:rPr><w:t>1</w:t></w:r></w:fldSimple>'
            '<w:r><w:rPr><w:color w:val="6B7280"/><w:sz w:val="16"/></w:rPr>'
            '<w:t xml:space="preserve"> of </w:t></w:r>'
            '<w:fldSimple w:instr=" NUMPAGES "><w:r><w:rPr><w:color w:val="6B7280"/>'
            '<w:sz w:val="16"/></w:rPr><w:t>1</w:t></w:r></w:fldSimple>'
            "</w:p></w:ftr>"
        )

    def _zip(self, files: dict[str, str]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content.encode("utf-8"))
        return buffer.getvalue()
