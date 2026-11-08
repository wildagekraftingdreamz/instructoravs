"""Engine tests: parsing, rendering, storage, merge and the CLI."""

from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import unittest
import zlib
from pathlib import Path

from instructoravs import builder, cli, guides
from instructoravs.blocks import BulletList, Heading, OrderedList, Table
from instructoravs.exporters import to_csv, to_json, to_slides
from instructoravs.markdown import parse_inline, parse_markdown
from instructoravs.merge import merge3
from instructoravs.prefs import Prefs
from instructoravs.render_html import render_html, render_html_fragment
from instructoravs.render_md import render_markdown
from instructoravs.render_pdf import render_pdf
from instructoravs.render_text import render_text
from instructoravs.store import DocumentStore


class InlineTests(unittest.TestCase):
    def test_emphasis_code_and_links(self) -> None:
        spans = parse_inline("Use **Win+R**, then `cmd`, *carefully*, see [portal](https://p.example).")
        texts = [span.text for span in spans]
        self.assertIn("Win+R", texts)
        self.assertTrue(any(span.bold for span in spans if span.text == "Win+R"))
        self.assertTrue(any(span.code for span in spans if span.text == "cmd"))
        self.assertTrue(any(span.italic for span in spans if span.text == "carefully"))
        link = next(span for span in spans if span.link)
        self.assertEqual(link.link, "https://p.example")

    def test_escaped_asterisk_is_literal(self) -> None:
        spans = parse_inline(r"2 \* 3")
        self.assertEqual("".join(span.text for span in spans), "2 * 3")
        self.assertFalse(any(span.italic for span in spans))


class MarkdownTests(unittest.TestCase):
    def test_roundtrip_is_stable(self) -> None:
        prefs = Prefs(number_headings=True)
        blocks = guides.build_guide(guides.get("login"), prefs)  # type: ignore[arg-type]
        markdown = render_markdown(blocks, prefs)
        again = render_markdown(parse_markdown(markdown), prefs)
        self.assertEqual(markdown, again)

    def test_nested_lists_checklist_and_table(self) -> None:
        markdown = (
            "1. **Open.** Click it.\n"
            "   A detail paragraph.\n"
            "2. Next step\n\n"
            "- [ ] verify one\n- [x] verify two\n\n"
            "| Symptom | Fix |\n| --- | --- |\n| A | B |\n"
        )
        blocks = parse_markdown(markdown)
        ordered = next(block for block in blocks if isinstance(block, OrderedList))
        self.assertEqual(len(ordered.items), 2)
        self.assertTrue(ordered.items[0].children)
        checklist = next(block for block in blocks if isinstance(block, BulletList))
        self.assertEqual([item.checked for item in checklist.items], [False, True])
        table = next(block for block in blocks if isinstance(block, Table))
        self.assertEqual(table.rows[0][0][0].text, "A")

    def test_code_fence_in_list_item(self) -> None:
        blocks = parse_markdown("1. Run it\n\n   ```powershell\n   Get-Date\n   ```\n")
        ordered = next(block for block in blocks if isinstance(block, OrderedList))
        self.assertTrue(any(type(child).__name__ == "CodeBlock" for child in ordered.items[0].children))


class RenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prefs = Prefs()
        self.blocks = guides.build_guide(guides.get("login"), self.prefs)  # type: ignore[arg-type]

    def test_text_has_structure_and_no_markup(self) -> None:
        text = render_text(self.blocks, self.prefs)
        self.assertIn("SIGNING IN WITH YOUR WORK ACCOUNT", text)
        self.assertIn("Before you begin", text)
        self.assertIn("| Symptom", text)
        self.assertNotIn("**", text)
        self.assertNotIn("##", text)

    def test_html_escapes_and_fragments(self) -> None:
        html = render_html(parse_markdown("Use <script>alert(1)</script> now"), "x", self.prefs)
        self.assertIn("&lt;script&gt;", html)
        fragment = render_html_fragment(self.blocks, self.prefs)
        self.assertTrue(fragment.startswith('<article class="doc">'))
        self.assertIn("<table>", fragment)
        self.assertIn("<ol", fragment)

    def test_pdf_is_structurally_valid(self) -> None:
        data = render_pdf(self.blocks, "Signing in with your work account", self.prefs)
        self.assert_pdf(data)
        streams = b"".join(
            zlib.decompress(match.group(1))
            for match in re.finditer(rb"stream\n(.*?)\nendstream", data, re.S)
        )
        self.assertIn(b"BT", streams)
        self.assertIn(b"Signing in with your work account", streams)
        self.assertIn(b"Troubleshooting", streams)

    def test_pdf_breaks_pages_on_long_documents(self) -> None:
        prefs = Prefs(detail="detailed")
        blocks = guides.build_guide(guides.get("onboarding"), prefs)  # type: ignore[arg-type]
        data = render_pdf(blocks, "New starter IT setup", prefs)
        self.assert_pdf(data)
        count = int(re.search(rb"/Count (\d+)", data).group(1))
        self.assertGreaterEqual(count, 2)

    def assert_pdf(self, data: bytes) -> None:
        self.assertTrue(data.startswith(b"%PDF-1.7"))
        self.assertTrue(data.rstrip().endswith(b"%%EOF"))
        marker = data.rfind(b"startxref")
        offset = int(data[marker + len(b"startxref") :].split()[0])
        self.assertEqual(data[offset : offset + 4], b"xref")
        header = data[offset:].split(b"\n")[1].split()
        size = int(header[1])
        entries = re.findall(rb"(\d{10}) 00000 n \n", data[offset:])
        self.assertEqual(len(entries), size - 1)
        for raw in entries:
            position = int(raw)
            self.assertRegex(data[position : position + 24], rb"^\d+ 0 obj")
        pages = len(re.findall(rb"/Type /Page\b", data))
        count = int(re.search(rb"/Count (\d+)", data).group(1))
        self.assertEqual(pages, count)


class BuilderTests(unittest.TestCase):
    def test_login_brief_picks_the_playbook(self) -> None:
        kind, title, blocks, prefs = builder.build(
            "Create a step-by-step guide for user login", prefs=Prefs()
        )
        self.assertEqual(kind, "guide")
        self.assertIn("sign", title.lower())
        markdown = render_markdown(blocks, prefs)
        self.assertIn("## Before you begin", markdown)
        self.assertIn("## Troubleshooting", markdown)
        self.assertIn("Approve the multi-factor prompt", markdown)

    def test_new_playbooks_are_complete(self) -> None:
        for key in ("shared-mailbox", "mobile-enrolment", "asset-handover", "teams-meeting", "file-access"):
            with self.subTest(key=key):
                playbook = guides.get(key)
                self.assertIsNotNone(playbook)
                self.assertGreaterEqual(len(playbook.steps), 5)
                self.assertEqual(len(playbook.verify), 3)
                self.assertEqual(len(playbook.troubleshooting), 4)
                self.assertTrue(playbook.related)

    def test_shared_mailbox_brief_beats_generic_email(self) -> None:
        _, title, blocks, prefs = builder.build(
            "Create a guide for opening a shared mailbox in Outlook", prefs=Prefs()
        )
        self.assertEqual(title, "Opening and using a shared mailbox")
        self.assertIn("send on behalf", render_markdown(blocks, prefs).lower())

    def test_every_playbook_brief_routes_back_to_itself(self) -> None:
        for entry in guides.summary():
            with self.subTest(key=entry["key"]):
                self.assertTrue(entry["brief"], entry["key"])
                matched = guides.match(entry["brief"])
                self.assertIsNotNone(matched, entry["brief"])
                self.assertEqual(matched.key, entry["key"], entry["brief"])

    def test_every_playbook_has_a_known_category(self) -> None:
        entries = guides.summary()
        self.assertEqual({entry["category"] for entry in entries}, set(guides.CATEGORIES))
        for entry in entries:
            with self.subTest(key=entry["key"]):
                self.assertIn(entry["category"], guides.CATEGORIES)

    def test_playbook_summary_carries_picker_details(self) -> None:
        for entry in guides.summary():
            with self.subTest(key=entry["key"]):
                self.assertGreaterEqual(entry["steps"], 5)
                self.assertTrue(str(entry["first_prerequisite"]).strip())
                self.assertTrue(entry["brief"])

    def test_enrolment_and_handover_briefs_pick_their_playbooks(self) -> None:
        _, enrol_title, _, _ = builder.build("Enrol my work phone for email", prefs=Prefs())
        self.assertIn("phone", enrol_title.lower())
        _, handover_title, handover_blocks, handover_prefs = builder.build(
            "Hand over a loan laptop to a new starter", prefs=Prefs()
        )
        self.assertEqual(handover_title, "Handing over and returning loan equipment")
        self.assertIn("asset tag", render_markdown(handover_blocks, handover_prefs).lower())

    def test_cv_spec_builds_sections(self) -> None:
        spec = {
            "kind": "cv",
            "name": "Alex Morgan",
            "headline": "Senior IT Support Engineer",
            "contact": {"email": "a@example.com", "phone": "123"},
            "summary": "Eight years in support.",
            "skills": {"Platforms": ["Windows 11", "macOS"]},
            "experience": [
                {
                    "role": "Senior Engineer",
                    "company": "Northwind",
                    "dates": "2021 – Present",
                    "bullets": ["Cut onboarding from 90 to 35 minutes."],
                }
            ],
            "education": [{"qualification": "BSc Computing", "institution": "Leeds", "dates": "2016"}],
        }
        kind, title, blocks, prefs = builder.build("", spec=spec, prefs=Prefs())
        self.assertEqual(kind, "cv")
        self.assertEqual(title, "Alex Morgan")
        markdown = render_markdown(blocks, prefs)
        self.assertIn("ALEX MORGAN", markdown)
        self.assertIn("Core skills", markdown)
        self.assertIn("Cut onboarding", markdown)
        self.assertIn("Education", markdown)

    def test_detailed_adds_document_control(self) -> None:
        _, _, blocks, prefs = builder.build(
            "guide for resetting a password", prefs=Prefs(detail="detailed")
        )
        self.assertIn("Document control", render_markdown(blocks, prefs))

    def test_explicit_steps_are_kept(self) -> None:
        brief = (
            "Create a guide for swapping a toner cartridge\n"
            "1. Open the front cover\n"
            "2. Pull the empty cartridge out\n"
            "3. Fit the new cartridge and close\n"
        )
        _, _, blocks, prefs = builder.build(brief, prefs=Prefs())
        markdown = render_markdown(blocks, prefs)
        self.assertIn("Open the front cover", markdown)
        self.assertIn("Fit the new cartridge", markdown)

    def test_cv_without_spec_is_a_scaffold(self) -> None:
        _, title, blocks, prefs = builder.build("Create a CV for a helpdesk analyst", prefs=Prefs())
        self.assertIn("CV", title)
        markdown = render_markdown(blocks, prefs)
        self.assertIn("[YOUR NAME]", markdown)
        self.assertIn("Scaffold generated", markdown)


class StoreTests(unittest.TestCase):
    def test_versions_annotations_restore_and_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DocumentStore(tmp)
            prefs = Prefs()
            blocks = guides.build_guide(guides.get("vpn"), prefs)  # type: ignore[arg-type]
            document = store.create("VPN from home", "guide", blocks, prefs)
            self.assertEqual(document.latest.number, 1)
            folder = document.path / "versions" / "v0001"
            for name in ("content.md", "content.txt", "content.pdf"):
                self.assertTrue((folder / name).exists(), name)

            store.annotate(document.id, "Step 3 needs the new profile name", number=1)
            document = store.load(document.id)
            self.assertEqual(len(document.latest.annotations), 1)

            document = store.add_markdown(
                document.id, "# VPN\n\nShort version.\n", prefs, message="Shortened"
            )
            self.assertEqual(document.latest.number, 2)
            self.assertEqual(document.latest.parent, 1)

            document = store.restore(document.id, 1)
            self.assertEqual(document.latest.number, 3)
            self.assertEqual(
                store.read_markdown(document.id, 3), store.read_markdown(document.id, 1)
            )
            pdf = store.render_version(document.id, 3, "pdf")
            self.assertTrue(pdf.startswith(b"%PDF"))

            listing = store.all()
            self.assertEqual(len(listing), 1)
            self.assertEqual(listing[0].id, document.id)

    def test_prefix_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DocumentStore(tmp)
            blocks = guides.build_guide(guides.get("printer"), Prefs())  # type: ignore[arg-type]
            document = store.create("Printer guide", "guide", blocks, Prefs())
            self.assertEqual(store.resolve(document.id[:6]), document.id)


class MergeTests(unittest.TestCase):
    def test_clean_three_way_merge(self) -> None:
        base = "one\ntwo\nthree\n"
        ours = "ONE\ntwo\nthree\n"
        theirs = "one\ntwo\nTHREE\n"
        merged, conflicts = merge3(base, ours, theirs)
        self.assertEqual(conflicts, 0)
        self.assertEqual(merged, "ONE\ntwo\nTHREE\n")

    def test_overlapping_edits_conflict(self) -> None:
        base = "one\ntwo\n"
        ours = "ours\ntwo\n"
        theirs = "theirs\ntwo\n"
        merged, conflicts = merge3(base, ours, theirs)
        self.assertEqual(conflicts, 1)
        self.assertIn("<<<<<<< ours", merged)
        self.assertIn(">>>>>>> theirs", merged)


class ExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.blocks = guides.build_guide(guides.get("login"), Prefs())  # type: ignore[arg-type]

    def test_csv_rows_and_json(self) -> None:
        csv_text = to_csv(self.blocks)
        self.assertTrue(csv_text.startswith("section,order,step,detail,status"))
        self.assertIn("Approve the multi-factor prompt", csv_text)
        payload = json.loads(to_json(self.blocks, {"title": "Login"}))
        self.assertEqual(payload["meta"]["title"], "Login")
        self.assertTrue(any(block["type"] == "heading" for block in payload["blocks"]))
        self.assertIn("steps", payload)

    def test_slides_outline(self) -> None:
        slides = to_slides(self.blocks, "Login")
        self.assertTrue(slides.startswith("---\nmarp: true"))
        self.assertIn("## Troubleshooting", slides)


class CliTests(unittest.TestCase):
    def test_generate_list_show_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = cli.main(
                    [
                        "generate",
                        "Create a step-by-step guide for user login",
                        "--store",
                        tmp,
                        "--format",
                        "md,txt,pdf",
                        "--pref",
                        "audience=beginner",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertIn("Created", buffer.getvalue())

            store = DocumentStore(tmp)
            documents = store.all()
            self.assertEqual(len(documents), 1)
            doc_id = documents[0].id

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                cli.main(["list", "--store", tmp])
            self.assertIn(doc_id, out.getvalue())

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                cli.main(["show", doc_id, "--store", tmp, "--format", "txt"])
            self.assertIn("SIGNING IN", out.getvalue())

            export_path = Path(tmp) / "steps.csv"
            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(
                    ["export", doc_id, "--store", tmp, "--format", "csv", "--out", str(export_path)]
                )
            self.assertTrue(export_path.exists())


if __name__ == "__main__":
    unittest.main()
