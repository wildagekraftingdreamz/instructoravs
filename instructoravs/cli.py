"""Command line interface.

The same engine the web app uses. Every command takes ``--store`` so a script
can keep documents next to the project instead of in the default folder.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
from pathlib import Path

from . import __version__, builder, guides
from .blocks import inline_text
from .exporters import to_csv, to_json, to_slides
from .markdown import parse_markdown
from .merge import merge3
from .prefs import AUDIENCES, DETAILS, EMPHASIS, PAGE_SIZES, TONES, PrefError, Prefs
from .render_docx import render_docx
from .render_html import render_html
from .render_pdf import render_pdf
from .render_text import render_text
from .store import DEFAULT_FORMATS, DocumentStore, copy_files, slugify

DEFAULT_STORE = os.environ.get("INSTRUCTORAVS_HOME", "")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="instructoravs",
        description="Generate and version IT help guides, CVs and PDFs.",
    )
    parser.add_argument("--version", action="version", version=f"Instructoravs {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--store", default=None, help="document store folder (default ./.instructoravs)")

    generate = sub.add_parser("generate", aliases=["new"], help="write a new document from a brief")
    generate.add_argument("instruction", help="the brief, for example 'Create a step-by-step guide for user login'")
    generate.add_argument("--kind", choices=builder.KINDS, default="auto")
    generate.add_argument("--title", default=None)
    generate.add_argument("--detail", choices=DETAILS, default=None)
    generate.add_argument("--tone", choices=TONES, default=None)
    generate.add_argument("--audience", choices=AUDIENCES, default=None)
    generate.add_argument("--pref", action="append", default=[], metavar="KEY=VALUE")
    generate.add_argument("--spec", default=None, help="JSON spec file (or - for stdin)")
    generate.add_argument("--format", action="append", default=None, help="md,txt,pdf,docx,html")
    generate.add_argument("--message", default="Initial version")
    generate.add_argument("--out", default=None, help="copy the rendered files to this folder")
    generate.add_argument("--json", action="store_true")
    common(generate)
    generate.set_defaults(func=cmd_generate)

    listing = sub.add_parser("list", help="list stored documents")
    listing.add_argument("--json", action="store_true")
    common(listing)
    listing.set_defaults(func=cmd_list)

    show = sub.add_parser("show", help="print one version")
    show.add_argument("document")
    show.add_argument("-v", "--version", type=int, default=None)
    show.add_argument("--format", choices=("md", "txt"), default="md")
    show.add_argument("--out", default=None)
    common(show)
    show.set_defaults(func=cmd_show)

    history = sub.add_parser("history", help="versions and annotations")
    history.add_argument("document")
    history.add_argument("--json", action="store_true")
    common(history)
    history.set_defaults(func=cmd_history)

    diff = sub.add_parser("diff", help="compare two versions")
    diff.add_argument("document")
    diff.add_argument("a", nargs="?", type=int)
    diff.add_argument("b", nargs="?", type=int)
    common(diff)
    diff.set_defaults(func=cmd_diff)

    annotate = sub.add_parser("annotate", help="attach a note to a version")
    annotate.add_argument("document")
    annotate.add_argument("text")
    annotate.add_argument("-v", "--version", type=int, default=None)
    common(annotate)
    annotate.set_defaults(func=cmd_annotate)

    restore = sub.add_parser("restore", help="make an old version current again")
    restore.add_argument("document")
    restore.add_argument("-v", "--version", type=int, required=True)
    restore.add_argument("--message", default=None)
    common(restore)
    restore.set_defaults(func=cmd_restore)

    merge = sub.add_parser("merge", help="three-way merge of two edited versions")
    merge.add_argument("document")
    merge.add_argument("base", type=int)
    merge.add_argument("ours", type=int)
    merge.add_argument("theirs", type=int)
    merge.add_argument("--message", default=None)
    common(merge)
    merge.set_defaults(func=cmd_merge)

    render = sub.add_parser("render", help="re-render stored versions")
    render.add_argument("document")
    render.add_argument("-v", "--version", type=int, default=None)
    render.add_argument("--format", action="append", default=None)
    render.add_argument("--out", default=None)
    common(render)
    render.set_defaults(func=cmd_render)

    export = sub.add_parser("export", help="export for other tools (csv, json, slides)")
    export.add_argument("document")
    export.add_argument("-v", "--version", type=int, default=None)
    export.add_argument("--format", choices=("md", "txt", "pdf", "docx", "html", "csv", "json", "slides"), required=True)
    export.add_argument("--out", default=None)
    common(export)
    export.set_defaults(func=cmd_export)

    convert = sub.add_parser("convert", help="convert an existing Markdown/text file")
    convert.add_argument("input")
    convert.add_argument("--to", default="md,txt,pdf,docx,html")
    convert.add_argument("--out", default=".")
    convert.add_argument("--title", default=None)
    common(convert)
    convert.set_defaults(func=cmd_convert)

    imp = sub.add_parser("import", help="store an existing Markdown file as version 1")
    imp.add_argument("input")
    imp.add_argument("--title", default=None)
    imp.add_argument("--format", action="append", default=None)
    common(imp)
    imp.set_defaults(func=cmd_import)

    playbooks = sub.add_parser("playbooks", help="built-in IT guide topics")
    playbooks.add_argument("--json", action="store_true")
    common(playbooks)
    playbooks.set_defaults(func=cmd_playbooks)

    prefs = sub.add_parser("prefs", help="preference keys and accepted values")
    prefs.add_argument("--json", action="store_true")
    common(prefs)
    prefs.set_defaults(func=cmd_prefs)

    return parser


# -- helpers ---------------------------------------------------------------
def store_for(args: argparse.Namespace) -> DocumentStore:
    root = args.store or DEFAULT_STORE or str(Path.cwd() / ".instructoravs")
    return DocumentStore(root)


def parse_formats(values: list[str] | None) -> list[str]:
    if not values:
        return list(DEFAULT_FORMATS)
    formats: list[str] = []
    for value in values:
        for part in str(value).split(","):
            part = part.strip().lower().lstrip(".")
            if part:
                formats.append(part)
    return formats or list(DEFAULT_FORMATS)


def prefs_for(args: argparse.Namespace) -> Prefs:
    pairs = list(getattr(args, "pref", []) or [])
    if getattr(args, "detail", None):
        pairs.append(f"detail={args.detail}")
    if getattr(args, "tone", None):
        pairs.append(f"tone={args.tone}")
    if getattr(args, "audience", None):
        pairs.append(f"audience={args.audience}")
    return Prefs.parse_pairs(pairs)


def _version(args: argparse.Namespace, document) -> int:
    return args.version if getattr(args, "version", None) else document.latest.number


# -- commands --------------------------------------------------------------
def cmd_generate(args: argparse.Namespace) -> int:
    spec = builder.load_spec(args.spec)
    prefs = prefs_for(args)
    kind, title, blocks, prefs = builder.build(
        args.instruction,
        spec=spec,
        kind=args.kind,
        title=args.title,
        prefs=prefs,
        detail=args.detail,
    )
    store = store_for(args)
    document = store.create(
        title, kind, blocks, prefs, message=args.message, formats=parse_formats(args.format)
    )
    if spec:
        store.save_spec(document.id, spec)
    version = document.latest
    written = []
    if args.out:
        written = copy_files(document, version, args.out)

    if args.json:
        print(json.dumps({"document": document.as_dict(), "written": [str(p) for p in written]}, indent=2))
        return 0

    print(f"Created {title!r}  [{document.id}]  v{version.number}")
    print(f"  kind      {document.kind} · {prefs.detail} · {prefs.tone} · {prefs.audience}")
    print(f"  words     {version.words}")
    print(f"  store     {store.root}")
    for fmt in version.formats:
        path = store.version_dir(document.id, version.number) / f"content.{fmt}"
        print(f"  {fmt:<8}  {path}")
    for path in written:
        print(f"  copied    {path}")
    print()
    print(f"Preview:  instructoravs show {document.id}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    store = store_for(args)
    documents = store.all()
    if args.json:
        print(json.dumps([document.as_dict() for document in documents], indent=2))
        return 0
    if not documents:
        print(f"No documents in {store.root}")
        return 0
    print(f"{'document':<28} {'kind':<7} {'ver':>4} {'words':>6}  updated")
    for document in documents:
        latest = document.latest
        print(
            f"{document.id:<28} {document.kind:<7} {latest.number:>4} {latest.words:>6}  "
            f"{document.updated[:16].replace('T', ' ')}"
        )
        print(f"  {document.title}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    store = store_for(args)
    document = store.load(args.document)
    number = _version(args, document)
    markdown = store.read_markdown(document.id, number)
    if args.format == "md":
        text = markdown
    else:
        prefs = Prefs.from_dict(document.version(number).prefs)  # type: ignore[union-attr]
        text = render_text(parse_markdown(markdown), prefs)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
        return 0
    sys.stdout.write(text)
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    store = store_for(args)
    document = store.load(args.document)
    if args.json:
        print(json.dumps(document.as_dict(), indent=2))
        return 0
    print(f"{document.title}  [{document.id}]  {document.kind}")
    for version in sorted(document.versions, key=lambda item: item.number, reverse=True):
        parent = f" <- v{version.parent}" if version.parent else ""
        print(
            f"  v{version.number:<3} {version.created[:16].replace('T', ' ')}  "
            f"{version.words:>5} words  {', '.join(version.formats)}{parent}"
        )
        print(f"       {version.message}")
        for note in version.annotations:
            print(f"       note ({note.get('author')}): {note.get('text')}")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    store = store_for(args)
    document = store.load(args.document)
    numbers = sorted(version.number for version in document.versions)
    b = args.b or (numbers[-1] if numbers else 0)
    a = args.a or (numbers[-2] if len(numbers) > 1 else b)
    left = store.read_markdown(document.id, a).splitlines(keepends=True)
    right = store.read_markdown(document.id, b).splitlines(keepends=True)
    diff = difflib.unified_diff(left, right, fromfile=f"v{a}", tofile=f"v{b}")
    sys.stdout.writelines(diff)
    return 0


def cmd_annotate(args: argparse.Namespace) -> int:
    store = store_for(args)
    document = store.load(args.document)
    number = _version(args, document)
    version = store.annotate(document.id, args.text, number=number)
    print(f"Annotated v{version.number} of {document.id} ({len(version.annotations)} notes)")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    store = store_for(args)
    document = store.restore(args.document, args.version, message=args.message)
    print(f"Restored v{args.version} as v{document.latest.number} of {document.id}")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    store = store_for(args)
    document = store.load(args.document)
    base = store.read_markdown(document.id, args.base)
    ours = store.read_markdown(document.id, args.ours)
    theirs = store.read_markdown(document.id, args.theirs)
    merged, conflicts = merge3(base, ours, theirs)
    prefs = Prefs.from_dict(document.version(args.ours).prefs)  # type: ignore[union-attr]
    message = args.message or f"Merge of v{args.ours} and v{args.theirs} (base v{args.base})"
    document = store.add_markdown(document.id, merged, prefs, message=message, parent=args.ours)
    print(f"Merged into v{document.latest.number} with {conflicts} conflict(s)")
    if conflicts:
        print("Resolve the markers in the stored Markdown, then add another version.")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    store = store_for(args)
    document = store.load(args.document)
    number = _version(args, document)
    formats = parse_formats(args.format)
    for fmt in formats:
        data = store.render_version(document.id, number, fmt, write=True)
        print(f"  {fmt:<5} {len(data):>8} bytes")
    if args.out:
        for path in copy_files(document, document.version(number), args.out):  # type: ignore[arg-type]
            print(f"  copied {path}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    store = store_for(args)
    document = store.load(args.document)
    number = _version(args, document)
    markdown = store.read_markdown(document.id, number)
    prefs = Prefs.from_dict(document.version(number).prefs)  # type: ignore[union-attr]
    blocks = parse_markdown(markdown)
    fmt = args.format
    if fmt == "md":
        payload: bytes = markdown.encode("utf-8")
    elif fmt == "txt":
        payload = render_text(blocks, prefs).encode("utf-8")
    elif fmt == "pdf":
        payload = store.render_version(document.id, number, "pdf")
    elif fmt == "docx":
        payload = store.render_version(document.id, number, "docx")
    elif fmt == "html":
        payload = render_html(blocks, document.title, prefs).encode("utf-8")
    elif fmt == "csv":
        payload = to_csv(blocks).encode("utf-8")
    elif fmt == "json":
        payload = to_json(blocks, {"document": document.as_dict(), "version": number}).encode("utf-8")
    else:
        payload = to_slides(blocks, document.title).encode("utf-8")

    if args.out:
        target = Path(args.out)
        if target.is_dir():
            target = target / f"{slugify(document.title)}-v{number:04d}.{fmt}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        print(f"Wrote {target}")
    else:
        sys.stdout.write(payload.decode("utf-8"))
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    source = Path(args.input)
    text = source.read_text(encoding="utf-8")
    blocks = parse_markdown(text)
    title = args.title or next(
        (inline_text(block.content) for block in blocks if hasattr(block, "level")), source.stem
    )
    prefs = Prefs()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.title and slugify(args.title) or source.stem
    written = []
    for fmt in [part.strip().lower() for part in args.to.split(",") if part.strip()]:
        if fmt == "md":
            data = text.encode("utf-8")
        elif fmt == "txt":
            data = render_text(blocks, prefs).encode("utf-8")
        elif fmt == "html":
            data = render_html(blocks, title, prefs).encode("utf-8")
        elif fmt == "pdf":
            data = render_pdf(blocks, title, prefs)
        elif fmt == "docx":
            data = render_docx(blocks, title, prefs)
        else:
            print(f"  skipped unknown format {fmt!r}", file=sys.stderr)
            continue
        target = out_dir / f"{stem}.{fmt}"
        target.write_bytes(data)
        written.append(target)
    for path in written:
        print(f"Wrote {path}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    source = Path(args.input)
    text = source.read_text(encoding="utf-8")
    blocks = parse_markdown(text)
    title = args.title or next(
        (inline_text(block.content) for block in blocks if hasattr(block, "level")), source.stem
    )
    store = store_for(args)
    document = store.create(
        title,
        "guide",
        blocks,
        Prefs(),
        message=f"Imported from {source.name}",
        formats=parse_formats(args.format),
    )
    print(f"Imported {title!r} as {document.id} v{document.latest.number}")
    return 0


def cmd_playbooks(args: argparse.Namespace) -> int:
    items = guides.summary()
    if args.json:
        print(json.dumps(items, indent=2))
        return 0
    for item in items:
        print(f"{item['key']:<18} {item['title']}")
        print(f"{'':<18} {item['applies_to']} · {item['time']}")
    return 0


def cmd_prefs(args: argparse.Namespace) -> int:
    data = {
        "tone": list(TONES),
        "audience": list(AUDIENCES),
        "detail": list(DETAILS),
        "text_emphasis": list(EMPHASIS),
        "page_size": list(PAGE_SIZES),
        "booleans": [
            "number_headings",
            "caps_headings",
            "checklist_steps",
            "include_troubleshooting",
            "include_meta",
            "include_document_control",
        ],
        "numbers": ["text_width", "font_scale"],
        "text": ["accent", "author", "template"],
    }
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    for key, values in data.items():
        print(f"{key}: {', '.join(str(value) for value in values)}")
    print("\nPass with --pref key=value (repeatable).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (PrefError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"error: file not found: {exc.filename or exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
