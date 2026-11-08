"""Versioned document storage on disk.

One folder per document, one folder per version, Markdown as the source of
truth.  Every version keeps the preferences it was produced with, so an old
version can be re-rendered to PDF exactly as it was, and annotations live with
the text they comment on rather than in a separate log.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .blocks import Block, word_count
from .markdown import parse_markdown
from .prefs import Prefs
from .render_html import render_html
from .render_md import render_markdown
from .render_pdf import render_pdf
from .render_text import render_text

DEFAULT_FORMATS = ("md", "txt", "pdf")
VALID_FORMATS = ("md", "txt", "pdf", "html")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (slug[:52] or "document").strip("-")


@dataclass
class VersionInfo:
    number: int
    created: str
    message: str
    parent: int | None = None
    digest: str = ""
    formats: list[str] = field(default_factory=lambda: ["md"])
    annotations: list[dict[str, Any]] = field(default_factory=list)
    prefs: dict[str, Any] = field(default_factory=dict)
    detail: str = "standard"
    words: int = 0
    title: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "created": self.created,
            "message": self.message,
            "parent": self.parent,
            "digest": self.digest,
            "formats": list(self.formats),
            "annotations": list(self.annotations),
            "prefs": dict(self.prefs),
            "detail": self.detail,
            "words": self.words,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VersionInfo":
        return cls(
            number=int(data.get("number", 0)),
            created=str(data.get("created", "")),
            message=str(data.get("message", "")),
            parent=data.get("parent"),
            digest=str(data.get("digest", "")),
            formats=list(data.get("formats") or ["md"]),
            annotations=list(data.get("annotations") or []),
            prefs=dict(data.get("prefs") or {}),
            detail=str(data.get("detail") or "standard"),
            words=int(data.get("words") or 0),
            title=str(data.get("title") or ""),
        )


@dataclass
class Document:
    id: str
    title: str
    kind: str
    created: str
    updated: str
    versions: list[VersionInfo] = field(default_factory=list)
    path: Path = Path(".")

    @property
    def latest(self) -> VersionInfo:
        return max(self.versions, key=lambda version: version.number)

    def version(self, number: int | None = None) -> VersionInfo | None:
        if number is None:
            return self.latest if self.versions else None
        for item in self.versions:
            if item.number == number:
                return item
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "created": self.created,
            "updated": self.updated,
            "path": str(self.path),
            "versions": [version.as_dict() for version in self.versions],
            "latest": self.latest.as_dict() if self.versions else None,
        }


class DocumentStore:
    """Filesystem store: ``<root>/documents/<id>/versions/v0001/``."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.documents_dir = self.root / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    # -- locations ----------------------------------------------------------
    def path_for(self, doc_id: str) -> Path:
        return self.documents_dir / doc_id

    def version_dir(self, doc_id: str, number: int) -> Path:
        return self.path_for(doc_id) / "versions" / f"v{number:04d}"

    # -- reading ------------------------------------------------------------
    def all(self) -> list[Document]:
        documents = []
        for entry in sorted(self.documents_dir.iterdir()):
            if not entry.is_dir():
                continue
            meta = entry / "document.json"
            if not meta.exists():
                continue
            try:
                documents.append(self._load_path(entry))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        documents.sort(key=lambda document: document.updated, reverse=True)
        return documents

    def resolve(self, doc_id: str) -> str:
        """Accept a full id or an unambiguous prefix."""
        if not doc_id:
            raise KeyError("a document id is required")
        direct = self.path_for(doc_id)
        if (direct / "document.json").exists():
            return doc_id
        matches = [
            entry.name
            for entry in self.documents_dir.iterdir()
            if entry.is_dir() and entry.name.startswith(doc_id)
        ]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise KeyError(f"no document matches {doc_id!r}")
        raise KeyError(f"{doc_id!r} is ambiguous: {', '.join(sorted(matches)[:4])}")

    def load(self, doc_id: str) -> Document:
        return self._load_path(self.path_for(self.resolve(doc_id)))

    def _load_path(self, path: Path) -> Document:
        data = json.loads((path / "document.json").read_text(encoding="utf-8"))
        return Document(
            id=str(data["id"]),
            title=str(data["title"]),
            kind=str(data.get("kind") or "guide"),
            created=str(data.get("created") or ""),
            updated=str(data.get("updated") or ""),
            versions=[VersionInfo.from_dict(item) for item in data.get("versions") or []],
            path=path,
        )

    def read_markdown(self, doc_id: str, number: int | None = None) -> str:
        document = self.load(doc_id)
        version = document.version(number)
        if version is None:
            raise KeyError(f"version {number} of {doc_id!r} does not exist")
        path = self.version_dir(document.id, version.number) / "content.md"
        return path.read_text(encoding="utf-8")

    # -- writing ------------------------------------------------------------
    def create(
        self,
        title: str,
        kind: str,
        blocks: list[Block],
        prefs: Prefs,
        *,
        message: str = "Initial version",
        formats: Iterable[str] = DEFAULT_FORMATS,
    ) -> Document:
        doc_id = self._unique_id(title)
        path = self.path_for(doc_id)
        (path / "versions").mkdir(parents=True, exist_ok=False)
        stamp = _now()
        document = Document(
            id=doc_id,
            title=title,
            kind=kind,
            created=stamp,
            updated=stamp,
            versions=[],
            path=path,
        )
        self._add(document, blocks, prefs, message, parent=None, formats=formats)
        return document

    def add_version(
        self,
        doc_id: str,
        blocks: list[Block],
        prefs: Prefs,
        *,
        message: str = "Updated",
        parent: int | None = None,
        formats: Iterable[str] = DEFAULT_FORMATS,
    ) -> Document:
        document = self.load(doc_id)
        if parent is None and document.versions:
            parent = document.latest.number
        self._add(document, blocks, prefs, message, parent=parent, formats=formats)
        return document

    def add_markdown(
        self,
        doc_id: str,
        markdown: str,
        prefs: Prefs,
        *,
        message: str = "Edited",
        parent: int | None = None,
        formats: Iterable[str] = DEFAULT_FORMATS,
    ) -> Document:
        return self.add_version(
            doc_id,
            parse_markdown(markdown),
            prefs,
            message=message,
            parent=parent,
            formats=formats,
        )

    def _add(
        self,
        document: Document,
        blocks: list[Block],
        prefs: Prefs,
        message: str,
        *,
        parent: int | None,
        formats: Iterable[str],
    ) -> VersionInfo:
        number = max((version.number for version in document.versions), default=0) + 1
        chosen = _formats(formats)
        version = VersionInfo(
            number=number,
            created=_now(),
            message=message.strip() or f"Version {number}",
            parent=parent,
            prefs=prefs.as_dict(),
            detail=prefs.detail,
            formats=chosen,
            words=word_count(blocks),
            title=document.title,
        )
        markdown = render_markdown(blocks, prefs)
        version.digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()

        folder = self.version_dir(document.id, number)
        folder.mkdir(parents=True, exist_ok=True)
        _atomic_write(folder / "content.md", markdown.encode("utf-8"))
        self._write_formats(folder, markdown, blocks, document, prefs, chosen)

        document.versions.append(version)
        document.updated = version.created
        self._save(document)
        _atomic_write(
            folder / "version.json",
            json.dumps(version.as_dict(), indent=2).encode("utf-8"),
        )
        return version

    def _write_formats(
        self,
        folder: Path,
        markdown: str,
        blocks: list[Block],
        document: Document,
        prefs: Prefs,
        formats: Iterable[str],
    ) -> None:
        chosen = set(formats)
        if "txt" in chosen:
            _atomic_write(folder / "content.txt", render_text(blocks, prefs).encode("utf-8"))
        if "html" in chosen:
            _atomic_write(
                folder / "content.html",
                render_html(blocks, document.title, prefs).encode("utf-8"),
            )
        if "pdf" in chosen:
            data = render_pdf(blocks, document.title, prefs, subject=document.kind)
            _atomic_write(folder / "content.pdf", data)

    def render_version(
        self,
        doc_id: str,
        number: int | None,
        fmt: str,
        *,
        write: bool = False,
    ) -> bytes:
        """Render one format from the stored Markdown; write it if missing."""
        fmt = fmt.lower()
        if fmt not in VALID_FORMATS:
            raise ValueError(f"unsupported format {fmt!r}")
        document = self.load(doc_id)
        version = document.version(number)
        if version is None:
            raise KeyError(f"version {number} of {doc_id!r} does not exist")
        folder = self.version_dir(document.id, version.number)
        path = folder / f"content.{fmt}"
        markdown = (folder / "content.md").read_text(encoding="utf-8")
        if fmt == "md":
            return markdown.encode("utf-8")
        if path.exists() and not write:
            return path.read_bytes()
        prefs = Prefs.from_dict(version.prefs)
        blocks = parse_markdown(markdown)
        if fmt == "txt":
            data = render_text(blocks, prefs).encode("utf-8")
        elif fmt == "html":
            data = render_html(blocks, document.title, prefs).encode("utf-8")
        else:
            data = render_pdf(blocks, document.title, prefs, subject=document.kind)
        if write or not path.exists():
            _atomic_write(path, data)
            if fmt not in version.formats:
                version.formats.append(fmt)
                self._save(document)
        return data

    def annotate(
        self,
        doc_id: str,
        text: str,
        *,
        number: int | None = None,
        author: str = "you",
    ) -> VersionInfo:
        document = self.load(doc_id)
        version = document.version(number)
        if version is None:
            raise KeyError(f"version {number} of {doc_id!r} does not exist")
        version.annotations.append(
            {"created": _now(), "author": author, "text": text.strip()}
        )
        document.updated = _now()
        self._save(document)
        folder = self.version_dir(document.id, version.number)
        _atomic_write(
            folder / "version.json", json.dumps(version.as_dict(), indent=2).encode("utf-8")
        )
        return version

    def restore(self, doc_id: str, number: int, *, message: str | None = None) -> Document:
        markdown = self.read_markdown(doc_id, number)
        document = self.load(doc_id)
        prefs = Prefs.from_dict(document.version(number).prefs)  # type: ignore[union-attr]
        return self.add_markdown(
            doc_id,
            markdown,
            prefs,
            message=message or f"Restored from version {number}",
            parent=number,
            formats=document.version(number).formats,  # type: ignore[union-attr]
        )

    def save_spec(self, doc_id: str, spec: dict[str, Any]) -> None:
        document = self.load(doc_id)
        _atomic_write(
            document.path / "spec.json", json.dumps(spec, indent=2).encode("utf-8")
        )

    def spec(self, doc_id: str) -> dict[str, Any] | None:
        document = self.load(doc_id)
        path = document.path / "spec.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    # -- internals ----------------------------------------------------------
    def _save(self, document: Document) -> None:
        data = {
            "id": document.id,
            "title": document.title,
            "kind": document.kind,
            "created": document.created,
            "updated": document.updated,
            "versions": [version.as_dict() for version in document.versions],
        }
        _atomic_write(
            document.path / "document.json",
            json.dumps(data, indent=2).encode("utf-8"),
        )

    def _unique_id(self, title: str) -> str:
        base = slugify(title)
        candidate = base
        counter = 2
        while self.path_for(candidate).exists():
            candidate = f"{base}-{counter}"
            counter += 1
        return candidate

    def stats(self) -> dict[str, Any]:
        documents = self.all()
        return {
            "documents": len(documents),
            "versions": sum(len(document.versions) for document in documents),
            "root": str(self.root),
        }


def _formats(formats: Iterable[str]) -> list[str]:
    chosen: list[str] = []
    for fmt in formats:
        value = str(fmt).strip().lower().lstrip(".")
        if value in VALID_FORMATS and value not in chosen:
            chosen.append(value)
    if "md" not in chosen:
        chosen.insert(0, "md")
    return chosen or ["md"]


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def copy_files(document: Document, version: VersionInfo, out_dir: str | Path) -> list[Path]:
    """Copy one version's rendered files to a folder the user chose."""
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    source = document.path / "versions" / f"v{version.number:04d}"
    for fmt in version.formats:
        file = source / f"content.{fmt}"
        if not file.exists():
            continue
        stem = slugify(document.title)
        destination = target / f"{stem}-v{version.number:04d}.{fmt}"
        shutil.copyfile(file, destination)
        written.append(destination)
    return written
