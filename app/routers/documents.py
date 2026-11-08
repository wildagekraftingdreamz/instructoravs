"""Document API: generate, read, version, diff, annotate, export."""

from __future__ import annotations

import difflib
import io
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from instructoravs import builder
from instructoravs.blocks import word_count
from instructoravs.exporters import to_csv, to_json, to_slides
from instructoravs.markdown import parse_markdown
from instructoravs.merge import merge3
from instructoravs.prefs import Prefs
from instructoravs.render_html import render_html, render_html_fragment
from instructoravs.render_pdf import render_pdf
from instructoravs.render_text import render_text
from instructoravs.store import VALID_FORMATS, DocumentStore

from .. import __version__, config

router = APIRouter(prefix="/api", tags=["documents"])


def store() -> DocumentStore:
    return DocumentStore(config.STORE_DIR)


class GenerateRequest(BaseModel):
    instruction: str = ""
    kind: str = "auto"
    title: str | None = None
    detail: str | None = None
    prefs: dict[str, Any] = Field(default_factory=dict)
    spec: dict[str, Any] | None = None
    formats: list[str] = Field(default_factory=lambda: ["md", "txt", "pdf", "docx"])
    message: str = "Initial version"


class VersionRequest(BaseModel):
    instruction: str | None = None
    markdown: str | None = None
    message: str = "Updated"
    detail: str | None = None
    prefs: dict[str, Any] = Field(default_factory=dict)
    formats: list[str] = Field(default_factory=lambda: ["md", "txt", "pdf", "docx"])


class AnnotateRequest(BaseModel):
    text: str
    author: str = "you"


class MergeRequest(BaseModel):
    base: int
    ours: int
    theirs: int
    message: str | None = None


def _prefs(data: dict[str, Any] | None, detail: str | None = None) -> Prefs:
    merged = dict(data or {})
    if detail:
        merged["detail"] = detail
    try:
        return Prefs.from_dict({**Prefs().as_dict(), **merged})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _document_summary(document) -> dict[str, Any]:
    latest = document.latest if document.versions else None
    return {
        "id": document.id,
        "title": document.title,
        "kind": document.kind,
        "created": document.created,
        "updated": document.updated,
        "versions": len(document.versions),
        "version": latest.number if latest else 0,
        "words": latest.words if latest else 0,
        "detail": latest.detail if latest else "",
        "formats": latest.formats if latest else [],
        "annotations": len(latest.annotations) if latest else 0,
        "digest": (latest.digest[:12] if latest else ""),
    }


def _version_payload(store_: DocumentStore, document, number: int | None) -> dict[str, Any]:
    version = document.version(number)
    if version is None:
        raise HTTPException(status_code=404, detail=f"version {number} not found")
    prefs = Prefs.from_dict(version.prefs)
    markdown = store_.read_markdown(document.id, version.number)
    blocks = parse_markdown(markdown)
    return {
        "number": version.number,
        "created": version.created,
        "message": version.message,
        "parent": version.parent,
        "words": version.words,
        "formats": version.formats,
        "annotations": version.annotations,
        "digest": version.digest,
        "prefs": version.prefs,
        "title": document.title,
        "kind": document.kind,
        "markdown": markdown,
        "text": render_text(blocks, prefs),
        "html": render_html_fragment(blocks, prefs),
        "headings": [
            {"level": b.level, "text": b.content[0].text if b.content else ""}
            for b in blocks
            if hasattr(b, "level")
        ],
    }


@router.get("/health")
def health() -> dict[str, Any]:
    store_ = store()
    return {"ok": True, "version": __version__, **store_.stats()}


@router.get("/playbooks")
def playbooks() -> list[dict[str, str | int]]:
    from instructoravs import guides

    return guides.summary()


@router.get("/documents")
def list_documents() -> list[dict[str, Any]]:
    return [_document_summary(document) for document in store().all()]


@router.post("/documents")
def create_document(request: GenerateRequest) -> JSONResponse:
    store_ = store()
    if not request.instruction.strip() and not request.spec:
        raise HTTPException(status_code=422, detail="a brief or a spec is required")
    if request.spec is not None:
        try:
            prefs = _prefs({**request.spec.get("prefs", {}), **request.prefs}, request.detail)
        except TypeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        prefs = _prefs(request.prefs, request.detail)

    try:
        kind, title, blocks, prefs = builder.build(
            request.instruction,
            spec=request.spec,
            kind=request.kind,
            title=request.title,
            prefs=prefs,
            detail=request.detail,
        )
        document = store_.create(
            title,
            kind,
            blocks,
            prefs,
            message=request.message or "Initial version",
            formats=[fmt for fmt in request.formats if fmt in VALID_FORMATS],
        )
        if request.spec is not None:
            store_.save_spec(document.id, request.spec)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = _version_payload(store_, document, document.latest.number)
    payload["document"] = _document_summary(document)
    return JSONResponse(payload)


@router.get("/documents/{doc_id}")
def get_document(doc_id: str, version: int | None = None) -> dict[str, Any]:
    store_ = store()
    try:
        document = store_.load(doc_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    payload = _version_payload(store_, document, version)
    payload["document"] = _document_summary(document)
    payload["versions"] = [
        {
            "number": item.number,
            "created": item.created,
            "message": item.message,
            "words": item.words,
            "formats": item.formats,
            "annotations": item.annotations,
            "parent": item.parent,
        }
        for item in sorted(document.versions, key=lambda entry: entry.number, reverse=True)
    ]
    return payload


@router.get("/documents/{doc_id}/versions/{number}")
def get_version(doc_id: str, number: int) -> dict[str, Any]:
    store_ = store()
    try:
        document = store_.load(doc_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _version_payload(store_, document, number)


@router.post("/documents/{doc_id}/versions")
def add_version(doc_id: str, request: VersionRequest) -> dict[str, Any]:
    store_ = store()
    try:
        document = store_.load(doc_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    prefs = _prefs(request.prefs or document.latest.prefs, request.detail)
    formats = [fmt for fmt in request.formats if fmt in VALID_FORMATS] or document.latest.formats
    try:
        if request.markdown is not None:
            document = store_.add_markdown(
                doc_id,
                request.markdown,
                prefs,
                message=request.message or "Edited",
                parent=document.latest.number,
                formats=formats,
            )
        elif request.instruction:
            spec = store_.spec(doc_id)
            kind, title, blocks, prefs = builder.build(
                request.instruction,
                spec=spec,
                kind=document.kind,
                title=document.title,
                prefs=prefs,
                detail=request.detail,
            )
            document = store_.add_version(
                doc_id,
                blocks,
                prefs,
                message=request.message or "Regenerated",
                parent=document.latest.number,
                formats=formats,
            )
        else:
            raise HTTPException(status_code=422, detail="send markdown or an instruction")
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = _version_payload(store_, document, document.latest.number)
    payload["document"] = _document_summary(document)
    return payload


@router.post("/documents/{doc_id}/versions/{number}/annotate")
def annotate(doc_id: str, number: int, request: AnnotateRequest) -> dict[str, Any]:
    store_ = store()
    try:
        store_.annotate(doc_id, request.text, number=number, author=request.author or "you")
        document = store_.load(doc_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _version_payload(store_, document, number)


@router.post("/documents/{doc_id}/versions/{number}/restore")
def restore(doc_id: str, number: int) -> dict[str, Any]:
    store_ = store()
    try:
        document = store_.restore(doc_id, number)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    payload = _version_payload(store_, document, document.latest.number)
    payload["document"] = _document_summary(document)
    return payload


@router.get("/documents/{doc_id}/diff")
def diff(doc_id: str, a: int | None = None, b: int | None = None) -> dict[str, Any]:
    store_ = store()
    try:
        document = store_.load(doc_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    numbers = sorted(item.number for item in document.versions)
    right = b or (numbers[-1] if numbers else 0)
    left = a or (numbers[-2] if len(numbers) > 1 else right)
    try:
        old = store_.read_markdown(doc_id, left).splitlines(keepends=True)
        new = store_.read_markdown(doc_id, right).splitlines(keepends=True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    text = "".join(difflib.unified_diff(old, new, fromfile=f"v{left}", tofile=f"v{right}"))
    return {"a": left, "b": right, "diff": text, "changed": bool(text)}


@router.post("/documents/{doc_id}/merge")
def merge(doc_id: str, request: MergeRequest) -> dict[str, Any]:
    store_ = store()
    try:
        document = store_.load(doc_id)
        base = store_.read_markdown(doc_id, request.base)
        ours = store_.read_markdown(doc_id, request.ours)
        theirs = store_.read_markdown(doc_id, request.theirs)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    merged, conflicts = merge3(base, ours, theirs)
    prefs = Prefs.from_dict(document.version(request.ours).prefs)  # type: ignore[union-attr]
    document = store_.add_markdown(
        doc_id,
        merged,
        prefs,
        message=request.message or f"Merge of v{request.ours} and v{request.theirs}",
        parent=request.ours,
    )
    payload = _version_payload(store_, document, document.latest.number)
    payload["document"] = _document_summary(document)
    payload["conflicts"] = conflicts
    return payload


@router.get("/documents/{doc_id}/file")
def file(doc_id: str, format: str = "pdf", version: int | None = None, inline: bool = False) -> Response:
    fmt = format.lower()
    if fmt not in VALID_FORMATS:
        raise HTTPException(status_code=422, detail=f"unsupported format {fmt!r}")
    store_ = store()
    try:
        document = store_.load(doc_id)
        data = store_.render_version(doc_id, version, fmt)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    media = {
        "md": "text/markdown; charset=utf-8",
        "txt": "text/plain; charset=utf-8",
        "html": "text/html; charset=utf-8",
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }[fmt]
    disposition = "inline" if inline else "attachment"
    filename = f"{document.id}-v{(document.version(version).number if document.version(version) else 1):04d}.{fmt}"
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.get("/documents/{doc_id}/export")
def export(doc_id: str, format: str = "csv", version: int | None = None) -> Response:
    fmt = format.lower()
    store_ = store()
    try:
        document = store_.load(doc_id)
        number = version or document.latest.number
        markdown = store_.read_markdown(doc_id, number)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    prefs = Prefs.from_dict(document.version(number).prefs)  # type: ignore[union-attr]
    blocks = parse_markdown(markdown)
    if fmt == "csv":
        data = to_csv(blocks)
        media = "text/csv; charset=utf-8"
    elif fmt == "json":
        data = to_json(blocks, {"document": _document_summary(document), "version": number})
        media = "application/json"
    elif fmt == "slides":
        data = to_slides(blocks, document.title)
        media = "text/markdown; charset=utf-8"
    elif fmt in VALID_FORMATS:
        payload = store_.render_version(doc_id, number, fmt)
        return Response(
            content=payload,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{document.id}-v{number:04d}.{fmt}"'},
        )
    else:
        raise HTTPException(status_code=422, detail=f"unsupported export {fmt!r}")
    filename = f"{document.id}-v{number:04d}.{fmt}"
    return PlainTextResponse(
        data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
