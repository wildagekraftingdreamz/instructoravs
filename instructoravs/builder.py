"""Brief or spec in, (kind, title, blocks) out."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import cv, guides
from .blocks import Block
from .build import bullets, checklist, code, h, kv_table, p, steps, table
from .prefs import Prefs, shape

KINDS = ("auto", "guide", "cv")

_CV_WORDS = ("cv", "curriculum vitae", "resume", "résumé")

_VERB = re.compile(
    r"^(?:please\s+)?(?:create|write|generate|make|build|draft|produce|prepare|give me)\s+",
    re.IGNORECASE,
)
_LEAD_NOUN = re.compile(
    r"^(?:(?:a|an|the)\s+)?(?:(?:step[- ]by[- ]step|quick|short|simple|detailed|technical|it|help|how-to)\s+)?"
    r"(?:(?:guide|article|instructions?|documentation|doc|walkthrough|runbook)\s+)?"
    r"(?:(?:for|to|on|about|covering|regarding)\s+)?",
    re.IGNORECASE,
)


def detect_kind(instruction: str, requested: str = "auto") -> str:
    if requested in ("guide", "cv"):
        return requested
    text = (instruction or "").lower()
    if any(re.search(rf"\b{re.escape(word)}\b", text) for word in _CV_WORDS):
        return "cv"
    return "guide"


def extract_topic(instruction: str) -> str:
    text = " ".join((instruction or "").split())
    text = _VERB.sub("", text)
    text = _LEAD_NOUN.sub("", text)
    match = re.search(r"\b(?:for|about|on|covering|regarding)\s+(.+)$", text, re.IGNORECASE)
    if match and len(match.group(1).strip()) > 2:
        text = match.group(1)
    text = text.strip(" .:!?\"'")
    text = re.sub(r"^(?:a|an|the)\s+", "", text, flags=re.IGNORECASE)
    return text


def sentence_title(topic: str) -> str:
    topic = topic.strip()
    if not topic:
        return "Untitled document"
    if topic.isupper() or topic.islower():
        topic = topic[:1].upper() + topic[1:]
    return topic[:120]


def explicit_steps(instruction: str) -> list[str]:
    """Steps the person already wrote in the brief: keep them verbatim."""
    lines = [line.strip() for line in (instruction or "").splitlines() if line.strip()]
    found: list[str] = []
    for line in lines[1:]:
        match = re.match(r"^(?:[-*\u2022]|\d{1,2}[.)])\s+(.*)$", line)
        if match and match.group(1).strip():
            found.append(match.group(1).strip())
    if len(found) >= 2:
        return found
    parts = [part.strip() for part in (instruction or "").split(";") if part.strip()]
    if len(parts) >= 3:
        return [re.sub(r"^(?:[-*\u2022]|\d{1,2}[.)])\s*", "", part) for part in parts]
    return []


def load_spec(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    text = Path(path).read_text(encoding="utf-8") if str(path) != "-" else None
    if text is None:
        import sys

        text = sys.stdin.read()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("a spec must be a JSON object")
    return data


def build(
    instruction: str = "",
    *,
    spec: dict[str, Any] | None = None,
    kind: str = "auto",
    title: str | None = None,
    prefs: Prefs | None = None,
    detail: str | None = None,
) -> tuple[str, str, list[Block], Prefs]:
    """Build a document, returning its kind, title, blocks and effective prefs."""
    prefs = prefs or Prefs()
    if detail:
        prefs = Prefs.from_dict({**prefs.as_dict(), "detail": detail})

    if spec:
        spec_kind = str(spec.get("kind") or kind)
        kind = detect_kind(instruction, spec_kind if spec_kind in ("guide", "cv") else kind)
        if spec.get("prefs"):
            merged = prefs.as_dict()
            merged.update({k: v for k, v in dict(spec["prefs"]).items() if k in Prefs.__annotations__})
            prefs = Prefs.from_dict(merged)
        if prefs.detail and spec.get("detail"):
            prefs = Prefs.from_dict({**prefs.as_dict(), "detail": str(spec["detail"])})
        if kind == "cv":
            spec_title = str(spec.get("name") or title or "Curriculum Vitae").strip()
            return kind, spec_title, cv.build_cv(spec, prefs, title=title), prefs
        document_title = sentence_title(str(title or spec.get("title") or extract_topic(instruction) or "Document"))
        return kind, document_title, build_from_spec(spec, prefs, document_title), prefs

    kind = detect_kind(instruction, kind)
    topic = extract_topic(instruction)

    if kind == "cv":
        document_title = title or (f"CV — {topic}" if topic and topic.lower() not in _CV_WORDS else "Curriculum Vitae")
        return kind, document_title, cv.build_cv({}, prefs, title=topic or title), prefs

    playbook = guides.match(instruction)
    if playbook is not None:
        document_title = title or playbook.title
        supplied = explicit_steps(instruction)
        blocks = guides.build_guide(
            playbook, prefs, title=title, custom_steps=supplied or None
        )
        return kind, document_title, blocks, prefs

    document_title = sentence_title(title or topic or "IT help guide")
    return kind, document_title, build_fallback(instruction, topic, prefs, document_title), prefs


def build_fallback(
    instruction: str, topic: str, prefs: Prefs, title: str
) -> list[Block]:
    """A structured scaffold for a brief no playbook covers."""
    subject = topic or title
    blocks: list[Block] = [h(1, title)]
    blocks.append(
        p(
            shape(
                f"This guide explains how to {subject} on company equipment. It is written for "
                f"{prefs.audience} staff and takes about 10 minutes.",
                prefs,
            )
        )
    )
    blocks.append(
        p(
            "_No built-in playbook matched this brief, so the sections below are a scaffold: "
            "replace the bracketed text and adjust the steps._"
        )
    )
    if prefs.include_meta:
        blocks.append(
            kv_table(
                [
                    ("Applies to", "[which systems, devices or accounts]"),
                    ("Audience", f"{prefs.audience} staff"),
                    ("Time needed", "About 10 minutes"),
                    ("Owner", "IT Service Desk"),
                ]
            )
        )

    blocks.append(h(2, "Before you begin"))
    blocks.append(
        bullets(
            [
                f"Confirm which system, account or device is involved in {subject}.",
                "Connect to the corporate network or the VPN.",
                "Save any open work; some steps require a restart or a sign-out.",
            ]
        )
    )

    blocks.append(h(2, "Step-by-step"))
    supplied = explicit_steps(instruction)
    if supplied:
        blocks.append(steps([(item, "") for item in supplied]))
    else:
        blocks.append(
            steps(
                [
                    (
                        "Confirm what you need",
                        f"Identify the system, account or device involved in {subject} and check "
                        "that you have access to it.",
                    ),
                    (
                        "Prepare the environment",
                        "Connect to the corporate network or VPN, close unsaved work and note the "
                        "device name or asset tag.",
                    ),
                    (
                        f"Carry out {subject}",
                        "Work one step at a time. Note the exact wording of any prompt or error "
                        "so support can reproduce it.",
                    ),
                    (
                        "Check the result",
                        "Confirm the intended outcome before closing the ticket or telling the "
                        "user the task is complete.",
                    ),
                    (
                        "Record the outcome",
                        "Add a short note to the ticket: what was done, the result and anything "
                        "left for the next person.",
                    ),
                ]
            )
        )

    blocks.append(h(2, "Verify it worked"))
    blocks.append(
        checklist(
            [
                f"The user can perform {subject} without help.",
                "No error message remains on screen.",
                "The change is visible to a second person or in the affected system.",
            ]
        )
    )

    if prefs.include_troubleshooting and prefs.detail != "brief":
        blocks.append(h(2, "Troubleshooting"))
        blocks.append(
            table(
                ["Symptom", "What to do"],
                [
                    ["The option described is missing", "Check the account's permissions first; then confirm the screen matches the version in this guide."],
                    ["An error appears mid-way", "Record the exact text, retry once, then escalate with the text and the device name."],
                    ["The change does not take effect", "Sign out and back in, or restart the application before trying again."],
                ],
            )
        )

    if prefs.detail == "detailed" and prefs.include_document_control:
        blocks.append(h(2, "Document control"))
        blocks.append(
            kv_table(
                [
                    ("Document", title),
                    ("Owner", "IT Service Desk"),
                    ("Review cycle", "Every 6 months"),
                    ("Source brief", instruction.strip()[:280] or "[none]"),
                ]
            )
        )

    blocks.append(h(2, "If you need more help"))
    blocks.append(
        p(
            "Contact the IT Service Desk on ext. 4357 or it-servicedesk@example.com, quoting "
            "this guide's title and the exact error text."
        )
    )
    return blocks


def build_from_spec(spec: dict[str, Any], prefs: Prefs, title: str) -> list[Block]:
    blocks: list[Block] = [h(1, title)]
    if spec.get("subtitle"):
        blocks.append(p(f"*{shape(str(spec['subtitle']), prefs)}*"))
    if spec.get("purpose"):
        blocks.append(p(shape(str(spec["purpose"]), prefs)))
    if spec.get("meta"):
        pairs = [(str(k), str(v)) for k, v in dict(spec["meta"]).items()]
        blocks.append(kv_table(pairs))
    if spec.get("prerequisites"):
        blocks.append(h(2, "Before you begin"))
        blocks.append(bullets([shape(str(item), prefs) for item in spec["prerequisites"]]))

    for section in spec.get("sections") or []:
        if not isinstance(section, dict):
            continue
        heading = str(section.get("heading") or "").strip()
        if heading:
            blocks.append(h(int(section.get("level") or 2), heading))
        for paragraph in section.get("paragraphs") or []:
            blocks.append(p(shape(str(paragraph), prefs)))
        if section.get("bullets"):
            blocks.append(bullets([shape(str(item), prefs) for item in section["bullets"]]))
        if section.get("checklist"):
            blocks.append(checklist([shape(str(item), prefs) for item in section["checklist"]]))
        if section.get("steps"):
            entries: list[tuple[str, str]] = []
            for item in section["steps"]:
                if isinstance(item, dict):
                    entries.append((str(item.get("title") or ""), shape(str(item.get("detail") or ""), prefs)))
                else:
                    entries.append((str(item), ""))
            blocks.append(steps(entries))
        if section.get("table"):
            spec_table = dict(section["table"])
            blocks.append(
                table(
                    [str(cell) for cell in spec_table.get("header") or []],
                    [[str(cell) for cell in row] for row in spec_table.get("rows") or []],
                )
            )
        if section.get("code"):
            blocks.append(code(str(section["code"]), str(section.get("language") or "")))
        if section.get("note"):
            blocks.append(p(f"_{shape(str(section['note']), prefs)}_"))

    if spec.get("footer"):
        blocks.append(p(f"_{spec['footer']}_"))
    return blocks
