"""CV layout: a spec in, a clean single-column CV out.

Everything is optional except a name: a spec with only experience still makes a
usable document, and missing sections are skipped rather than left as empty
headings.  With no spec at all the generator returns a scaffold of placeholders
instead of inventing a career.
"""

from __future__ import annotations

from typing import Any

from .blocks import Block
from .build import bullets, h, p, rule, table
from .prefs import Prefs, shape


def build_cv(spec: dict[str, Any], prefs: Prefs, *, title: str | None = None) -> list[Block]:
    if not spec:
        return scaffold(title or "Curriculum Vitae", prefs)

    name = str(spec.get("name") or "").strip() or "Your Name"
    headline = str(spec.get("headline") or "").strip()
    contact = _contact_line(spec.get("contact"))
    blocks: list[Block] = [h(1, name.upper())]
    if headline:
        blocks.append(p(f"**{shape(headline, prefs)}**"))
    if contact:
        blocks.append(p(contact))
    blocks.append(rule())

    summary = str(spec.get("summary") or "").strip()
    if summary:
        blocks.append(h(2, "Professional summary"))
        blocks.append(p(shape(summary, prefs)))

    skills = spec.get("skills")
    if skills:
        blocks.append(h(2, "Core skills"))
        blocks.append(_skills(skills, prefs))

    experience = spec.get("experience") or []
    if experience:
        blocks.append(h(2, "Experience"))
        for role in experience:
            blocks.extend(_role(role, prefs))

    if prefs.detail != "brief":
        education = spec.get("education") or []
        if education:
            blocks.append(h(2, "Education"))
            for entry in education:
                blocks.extend(_education(entry, prefs))

        certifications = spec.get("certifications") or []
        if certifications:
            blocks.append(h(2, "Certifications"))
            blocks.append(bullets([shape(str(item), prefs) for item in certifications]))

    if prefs.detail == "detailed":
        projects = spec.get("projects") or []
        if projects:
            blocks.append(h(2, "Selected projects"))
            for project in projects:
                blocks.extend(_project(project, prefs))

        extras = []
        languages = spec.get("languages")
        if languages:
            extras.append(("Languages", ", ".join(str(item) for item in languages)))
        availability = spec.get("availability")
        if availability:
            extras.append(("Availability", str(availability)))
        if extras:
            blocks.append(h(2, "Additional information"))
            blocks.append(table(["", ""], [[key, value] for key, value in extras]))

        if spec.get("references"):
            blocks.append(h(2, "References"))
            blocks.append(p(str(spec["references"])))

    if spec.get("note"):
        blocks.append(rule())
        blocks.append(p(f"*{shape(str(spec['note']), prefs)}*"))
    return blocks


def scaffold(title: str, prefs: Prefs) -> list[Block]:
    """A CV outline with bracketed placeholders, not invented facts."""
    blocks: list[Block] = [h(1, "[YOUR NAME]".upper())]
    blocks.append(p("**[Target role, for example: Senior IT Support Engineer]**"))
    blocks.append(p("[email] · [phone] · [city] · [linkedin.com/in/you]"))
    blocks.append(rule())
    blocks.append(h(2, "Professional summary"))
    blocks.append(p("[Two or three sentences: what you do, your years of experience and the "
                    "result you are known for. Mirror the language of the job advert.]"))
    blocks.append(h(2, "Core skills"))
    blocks.append(
        bullets(
            [
                "**[Category]** — [skill, skill, skill]",
                "**[Category]** — [skill, skill, skill]",
            ]
        )
    )
    blocks.append(h(2, "Experience"))
    blocks.append(h(3, "[Job title] — [Company]"))
    blocks.append(p("*[Month Year] – [Month Year] · [Location]*"))
    blocks.append(
        bullets(
            [
                "[What you owned: the system, team or process.]",
                "[A result with a number: time saved, tickets closed, users supported.]",
                "[A second result, or a tool you introduced.]",
            ]
        )
    )
    blocks.append(h(3, "[Previous job title] — [Company]"))
    blocks.append(p("*[Month Year] – [Month Year] · [Location]*"))
    blocks.append(bullets(["[Responsibility.]", "[Result with a number.]"]))
    if prefs.detail != "brief":
        blocks.append(h(2, "Education"))
        blocks.append(p("**[Qualification]** — [Institution], [Year]"))
        blocks.append(h(2, "Certifications"))
        blocks.append(bullets(["[Certification, issuer, year]"]))
    if prefs.detail == "detailed":
        blocks.append(h(2, "Selected projects"))
        blocks.append(p("**[Project]** — [what it was, your role, the outcome.]"))
        blocks.append(h(2, "Additional information"))
        blocks.append(p("**Languages:** [language, level] · **Availability:** [notice period]"))
    blocks.append(rule())
    blocks.append(
        p(
            "_Scaffold generated by Instructoravs. Replace every bracketed field; nothing here "
            "is a fact about you._"
        )
    )
    return blocks


def _contact_line(contact: Any) -> str:
    if isinstance(contact, dict):
        parts = []
        for key in ("email", "phone", "location", "website", "linkedin"):
            value = contact.get(key)
            if value:
                parts.append(str(value))
        for link in contact.get("links") or []:
            parts.append(str(link))
        return " · ".join(parts)
    if isinstance(contact, list):
        return " · ".join(str(item) for item in contact)
    if contact:
        return str(contact)
    return ""


def _skills(skills: Any, prefs: Prefs) -> Block:
    if isinstance(skills, dict):
        return bullets(
            [
                f"**{shape(str(group), prefs)}** — " + " · ".join(str(item) for item in items)
                for group, items in skills.items()
            ]
        )
    if isinstance(skills, list):
        if all(isinstance(item, dict) for item in skills):
            return bullets(
                [
                    f"**{shape(str(item.get('group', 'Skills')), prefs)}** — "
                    + " · ".join(str(s) for s in item.get("items", []))
                    for item in skills
                ]
            )
        return bullets([" · ".join(str(item) for item in skills)])
    return p(str(skills))


def _role(role: Any, prefs: Prefs) -> list[Block]:
    if not isinstance(role, dict):
        return [p(str(role))]
    title = str(role.get("role") or role.get("title") or "Role")
    company = str(role.get("company") or "").strip()
    heading = f"{title} — {company}" if company else title
    blocks: list[Block] = [h(3, heading)]
    meta = " · ".join(
        str(part)
        for part in (role.get("dates"), role.get("location"), role.get("type"))
        if part
    )
    if meta:
        blocks.append(p(f"*{meta}*"))
    if role.get("summary"):
        blocks.append(p(shape(str(role["summary"]), prefs)))
    duties = role.get("bullets") or role.get("achievements") or []
    if duties:
        items = [shape(str(item), prefs) for item in duties]
        if prefs.detail == "brief":
            items = items[:3]
        blocks.append(bullets(items))
    return blocks


def _education(entry: Any, prefs: Prefs) -> list[Block]:
    if not isinstance(entry, dict):
        return [p(str(entry))]
    qualification = str(entry.get("qualification") or entry.get("degree") or "Qualification")
    institution = str(entry.get("institution") or "").strip()
    heading = f"{qualification} — {institution}" if institution else qualification
    blocks: list[Block] = [h(3, heading)]
    meta = " · ".join(str(part) for part in (entry.get("dates"), entry.get("grade")) if part)
    if meta:
        blocks.append(p(f"*{meta}*"))
    if entry.get("note"):
        blocks.append(p(shape(str(entry["note"]), prefs)))
    return blocks


def _project(project: Any, prefs: Prefs) -> list[Block]:
    if not isinstance(project, dict):
        return [p(str(project))]
    name = str(project.get("name") or "Project")
    blocks: list[Block] = [h(3, name)]
    if project.get("summary"):
        blocks.append(p(shape(str(project["summary"]), prefs)))
    if project.get("bullets"):
        blocks.append(bullets([shape(str(item), prefs) for item in project["bullets"]]))
    if project.get("link"):
        blocks.append(p(f"[{project['link']}]({project['link']})"))
    return blocks
