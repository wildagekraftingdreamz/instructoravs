"""Formatting preferences and the prose transforms they drive.

Preferences are intentionally a small, validated set: they are stored in every
version's metadata, echoed by the API, and accepted as ``key=value`` pairs on
the CLI, so a typo must fail loudly rather than silently produce a document in
the wrong voice.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

TONES = ("professional", "friendly", "concise", "formal")
AUDIENCES = ("general", "beginner", "expert")
DETAILS = ("brief", "standard", "detailed")
EMPHASIS = ("none", "stars", "caps")
PAGE_SIZES = ("a4", "letter")

_ACCENT_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class PrefError(ValueError):
    """Raised for an unknown key or an invalid value."""


@dataclass
class Prefs:
    tone: str = "professional"
    audience: str = "general"
    detail: str = "standard"
    number_headings: bool = False
    caps_headings: bool = False
    checklist_steps: bool = False
    include_troubleshooting: bool = True
    include_meta: bool = True
    include_document_control: bool = True
    text_width: int = 88
    text_emphasis: str = "none"
    page_size: str = "a4"
    accent: str = "#1f4e79"
    font_scale: float = 1.0
    author: str = "Instructoravs"
    template: str = ""

    # -- validation ---------------------------------------------------------
    def __post_init__(self) -> None:
        self.tone = _choice("tone", self.tone, TONES, "professional")
        self.audience = _choice("audience", self.audience, AUDIENCES, "general")
        self.detail = _choice("detail", self.detail, DETAILS, "standard")
        self.text_emphasis = _choice("text_emphasis", self.text_emphasis, EMPHASIS, "none")
        self.page_size = _choice("page_size", self.page_size, PAGE_SIZES, "a4")
        self.text_width = max(48, min(160, int(self.text_width)))
        self.font_scale = max(0.75, min(1.5, float(self.font_scale)))
        if not _ACCENT_RE.match(self.accent):
            raise PrefError(f"accent must be a #rrggbb colour, got {self.accent!r}")

    # -- serialisation ------------------------------------------------------
    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Prefs":
        return cls(**{k: v for k, v in (data or {}).items() if k in cls.__annotations__})

    @classmethod
    def parse_pairs(cls, pairs: Iterable[str], base: "Prefs | None" = None) -> "Prefs":
        """Build from ``key=value`` strings (CLI/API friendly)."""
        data = (base or cls()).as_dict()
        for pair in pairs:
            if not pair.strip():
                continue
            if "=" not in pair:
                raise PrefError(f"preference {pair!r} must be key=value")
            key, _, raw = pair.partition("=")
            key = key.strip().replace("-", "_")
            if key not in cls.__annotations__:
                raise PrefError(
                    f"unknown preference {key!r}; known: {', '.join(sorted(cls.__annotations__))}"
                )
            current = data[key]
            if isinstance(current, bool):
                data[key] = _bool(key, raw)
            elif isinstance(current, int):
                data[key] = int(raw)
            elif isinstance(current, float):
                data[key] = float(raw)
            else:
                data[key] = raw.strip()
        return cls.from_dict(data)

    # -- presentation helpers ----------------------------------------------
    @property
    def keyword_set(self) -> set[str]:
        return {
            "tone",
            "audience",
            "detail",
            "number_headings",
            "caps_headings",
            "checklist_steps",
            "include_troubleshooting",
            "text_width",
            "text_emphasis",
            "page_size",
            "accent",
            "font_scale",
            "author",
        }

    def expanded(self) -> dict[str, str]:
        return {
            "text_width": str(self.text_width),
            "font_scale": f"{self.font_scale:.2f}",
        }


def _choice(name: str, value: str, allowed: tuple[str, ...], default: str) -> str:
    value = (value or default).strip().lower()
    if value not in allowed:
        raise PrefError(f"{name} must be one of {', '.join(allowed)}; got {value!r}")
    return value


def _bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on", "y"}:
        return True
    if value in {"0", "false", "no", "off", "n"}:
        return False
    raise PrefError(f"{name} must be a boolean (true/false), got {raw!r}")


# -- prose transforms ------------------------------------------------------
_CONTRACTIONS = {
    "don't": "do not",
    "won't": "will not",
    "can't": "cannot",
    "isn't": "is not",
    "aren't": "are not",
    "doesn't": "does not",
    "didn't": "did not",
    "hasn't": "has not",
    "haven't": "have not",
    "it's": "it is",
    "that's": "that is",
    "there's": "there is",
    "you'll": "you will",
    "you're": "you are",
    "you've": "you have",
    "we'll": "we will",
    "we're": "we are",
    "let's": "let us",
    "I'm": "I am",
    "they're": "they are",
}

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def formalise(text: str) -> str:
    """Expand contractions; used for the formal tone."""
    out = text
    for short, long in _CONTRACTIONS.items():
        out = re.sub(rf"\b{re.escape(short)}\b", long, out, flags=re.IGNORECASE)
    return out


def first_sentence(text: str) -> str:
    parts = _SENTENCE_END.split(text.strip(), maxsplit=1)
    return parts[0].strip()


def shape(text: str, prefs: Prefs) -> str:
    """Apply the tone preference to one sentence of generated prose."""
    if not text:
        return text
    if prefs.tone == "concise":
        text = first_sentence(text)
    if prefs.tone == "formal":
        text = formalise(text)
    return text


def shape_all(items: Iterable[str], prefs: Prefs) -> list[str]:
    return [shape(item, prefs) for item in items]


def hint(text: str, prefs: Prefs) -> str:
    """Extra guidance lines: beginners get them, experts do not."""
    return "" if prefs.audience == "expert" else text


def tone_label(prefs: Prefs) -> str:
    return f"{prefs.tone} · {prefs.audience} · {prefs.detail}"


def accent_rgb(hex_colour: str) -> tuple[float, float, float]:
    value = hex_colour.lstrip("#")
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
