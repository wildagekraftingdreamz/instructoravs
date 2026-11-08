# Instructoravs

Turn one sentence into a finished, versioned IT help guide or CV — then export it as
Markdown, plain text, HTML, PDF or Word (`.docx`). Everything runs on your machine: no
API keys, no uploads, no reportlab, no browser "print to PDF".

```text
brief ──► playbook / spec ──► blocks ──► content.md  (source of truth)
                                          ├── content.txt
                                          ├── content.html
                                          ├── content.pdf
                                          └── content.docx
```

## What it does

| Requested feature | Where it lives |
|---|---|
| "Create a step-by-step guide for user login" → structured text | `instructoravs/guides.py` (18 built-in playbooks) + `builder.py` |
| Markdown formatting handled and converted to plain text | `markdown.py` parser, `render_text.py` |
| Store documents as `.md`, `.txt`, `.pdf`, `.docx` (and `.html`) | `store.py` |
| Versions for different levels of detail | `--detail brief\|standard\|detailed` creates separate versions |
| Track changes, annotations, corrections | version history, `annotate`, `diff`, `restore`, three-way `merge` |
| Generate text to preferences | `prefs.py`: tone, audience, numbering, checklist steps, emphasis, page size, accent |
| Use the output in other tools | CSV steps for spreadsheets, JSON blocks for pipelines, Marp/Slidev slides |
| Cross-platform | Python 3.10+ standard library; no compiled dependencies, no OS-specific calls |

The web studio (FastAPI + static UI) is the face of the same engine: its card grid,
palette and typography follow the **Zana / Soul Apps** layout, with a document
workspace added.

## Quick start (Windows)

Double-click **`start.bat`**. On first run it creates `.venv`, installs
`requirements.txt`, starts the app on `http://127.0.0.1:8770` and opens the browser.
**`stop.bat`** stops the Python process listening on that port.

Any OS:

```bash
pip install -r requirements.txt
python -m app            # http://127.0.0.1:8770
```

The CLI needs nothing beyond the standard library:

```bash
python -m instructoravs generate "Create a step-by-step guide for user login"
```

## Studio layout

- **Toolbar** — detail level, tone, audience, output formats.
- **Brief** — one sentence, category shortcuts into the searchable **playbook browser**,
  a guided **Form** (guide and CV field sets with repeatable steps/roles and “View JSON”),
  or a JSON spec.
- **Document** — rendered preview, raw Markdown, plain text, and an inline PDF view;
  download buttons for `.md` / `.pdf` / `.docx`; hand-edit Markdown as a new version.
- **Versions** — history with notes, compare, annotate, restore, CSV export.
- **Library** — every document in the store, most recent first.

Keyboard: `Ctrl+K` (`⌘K` on macOS) opens the playbook browser with the filter focused.
The browser remembers the last topic area you selected; the category shortcuts override it.
Topic-area changes, arrow/Home/End movement between cards, and the number of matching
playbooks as the filter changes are announced through a polite live region for screen readers.
Toolbar choices (detail, tone, audience and formats) persist between sessions; the
**Reset defaults** button in the toolbar clears them and the picker's remembered topic;
a small “custom” badge marks when the toolbar differs from its defaults.

The design language is deliberately the Soul Apps one: `#0b0e14` page, `#121621` cards,
16 px radii, hairline `#232a3b` borders, teal `#5eead4` accent with violet `#8b8bff`
as the secondary, uppercase micro-labels, and a violet left edge on the document card
(the same treatment Zana gives its private room).

## CLI

```text
instructoravs generate "brief" [--kind auto|guide|cv] [--title T]
                   [--detail brief|standard|detailed] [--tone professional|friendly|concise|formal]
                   [--audience general|beginner|expert] [--pref key=value ...]
                   [--spec file.json] [--format md,txt,pdf,docx,html] [--out DIR] [--message M]

instructoravs list [--json]
instructoravs show DOC [-v N] [--format md|txt] [--out FILE]
instructoravs history DOC [--json]
instructoravs diff DOC [A] [B]
instructoravs annotate DOC "note" [-v N]
instructoravs restore DOC -v N [--message M]
instructoravs merge DOC BASE OURS THEIRS
instructoravs render DOC [-v N] [--format ...] [--out DIR]
instructoravs export DOC [-v N] --format csv|json|slides|md|txt|html|pdf|docx [--out PATH]
instructoravs convert FILE.md --to md,txt,pdf,docx,html --out DIR
instructoravs import FILE.md [--title T]
instructoravs playbooks
instructoravs prefs
```

`--store` selects the document folder (default `./.instructoravs`; the studio uses
`data/documents`). `INSTRUCTORAVS_HOME` overrides the CLI default.

Examples:

```bash
# IT guide, detailed, for beginners, as Markdown + PDF, copied to Desktop
python -m instructoravs generate "Create a guide for connecting to the VPN from home" \
  --detail detailed --audience beginner --out ~/Desktop

# CV from real data
python -m instructoravs generate "Create a CV for a senior IT support engineer" \
  --spec examples/cv.json

# Corrections and review
python -m instructoravs annotate login-guide "Step 3 changed after the MFA rollout" -v 1
python -m instructoravs restore login-guide -v 1
python -m instructoravs diff login-guide

# Spreadsheet / slide hand-off
python -m instructoravs export login-guide --format csv --out steps.csv
python -m instructoravs export login-guide --format slides --out login-slides.md
```

## Playbooks

`instructoravs playbooks` lists them. Keywords in the brief choose one:

`login` · `password-reset` · `mfa` · `vpn` · `wifi` · `printer` · `email` ·
`shared-mailbox` · `mobile-enrolment` · `asset-handover` · `software-install` ·
`backup` · `onboarding` · `remote-desktop` · `teams-meeting` · `file-access` ·
`phishing` · `updates`

Each supplies purpose, prerequisites, ordered steps with details and tips, a
verification checklist, four real troubleshooting rows, related guides and an
escalation line. Nothing is invented about a person; CVs built without a spec are
explicit scaffolds with bracketed placeholders.

## Specs

A spec gives complete control; `examples/guide.json` and `examples/cv.json` are working
starting points. Guide spec keys: `title`, `subtitle`, `purpose`, `meta`, `prerequisites`,
`sections[]` (`heading`, `level`, `paragraphs`, `bullets`, `checklist`, `steps`, `table`,
`code`, `language`, `note`), `footer`. CV spec keys: `name`, `headline`, `contact`,
`summary`, `skills` (list or category map), `experience[]`, `education[]`,
`certifications[]`, `projects[]`, `languages`, `availability`, `references`, `note`.

## Preferences

Set with `--pref key=value` or the toolbar:

```text
tone                     professional | friendly | concise | formal
audience                 general | beginner | expert
detail                   brief | standard | detailed
number_headings          true/false      caps_headings       true/false
checklist_steps          true/false      include_troubleshooting  true/false
include_document_control true/false      text_width          48-160
text_emphasis            none | stars | caps
page_size                a4 | letter      accent             #rrggbb
font_scale               0.75-1.50       author              text
```

Preferences are stored with every version, so re-rendering an old version reproduces
the document as it was.

## Storage layout

```text
data/documents/
  login-guide/
    document.json                 # id, title, kind, version list
    spec.json                     # optional, when generated from a spec
    versions/
      v0001/
        content.md                # source of truth
        content.txt
        content.pdf
        content.docx
        content.html              # only when requested
        version.json              # message, parent, digest, annotations, prefs
      v0002/ ...
```

Writes are atomic (temp file + replace), IDs are slugs with collision suffixes, and a
unique prefix is enough to address a document.

## API

`GET /api/health` · `GET /api/playbooks` · `GET /api/documents` ·
`POST /api/documents` · `GET /api/documents/{id}?version=N` ·
`POST /api/documents/{id}/versions` · `POST .../versions/{n}/annotate` ·
`POST .../versions/{n}/restore` · `GET /api/documents/{id}/diff?a=&b=` ·
`POST /api/documents/{id}/merge` · `GET /api/documents/{id}/file?format=pdf|docx&version=N` ·
`GET /api/documents/{id}/export?format=csv|json|slides`.

Interactive docs at `/api/docs`.

## The Word engine

`.docx` is written directly as Office Open XML, so Word support adds no runtime
dependency. Headings, lists, checkboxes, tables, code blocks, rules and hyperlinks use
the same block model as the preview; styles carry the accent colour, table header wash
and footer page numbers. The package is standard enough for Word, LibreOffice and
Google Docs to open and edit.

## The PDF engine

`instructoravs/pdf.py` writes PDF 1.7 directly: base-14 Helvetica/Courier fonts (no
font files), flate-compressed content streams, a real xref table, running headers,
page numbers and metadata. `render_pdf.py` lays out headings, paragraphs, hanging-indent
lists, checkboxes, code blocks, quotes and wrapped tables with page breaks that never
split a heading. `text_width()` uses the Helvetica AFM advance widths, so wraps are
measured rather than guessed.

## Tests

```bash
python -m unittest discover -s tests -v
```

The suite covers inline parsing, Markdown round-tripping, nested lists and tables,
text/HTML escaping, PDF structure (xref offsets, object headers, page count, stream
decompression), DOCX package structure and XML validity for guides and CVs, the builders,
storage/versioning, three-way merge, exporters and the CLI end to end.

## Notes and limits

- Generation is deterministic and rule-based by design — no model, key or network. The
  fallback for an unmatched brief is an honest scaffold, marked as such.
- The PDF uses the base-14 fonts, which cover WinAnsi (Western European). Characters
  outside that set render as `?`; the HTML export has no such limit.
- The studio binds to loopback only. It is a local tool, not a hosted service.
- Layout inspiration: `D:\SoulApps\zana-main` (Soul Apps card UI). Its palette is kept
  verbatim in `app/static/soul-tokens.css`.
