"""Three-way line merge for combining two edits of one version.

Diff three versions, apply the non-overlapping edits from both sides, and mark
real conflicts with git-style markers so nothing is lost silently.
"""

from __future__ import annotations

import difflib

MARKER_OURS = "<<<<<<< ours"
MARKER_BASE = "||||||| base"
MARKER_SEP = "======="
MARKER_THEIRS = ">>>>>>> theirs"


def _changes(base: list[str], other: list[str]) -> list[tuple[int, int, list[str]]]:
    matcher = difflib.SequenceMatcher(a=base, b=other, autojunk=False)
    changes = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            changes.append((i1, i2, other[j1:j2]))
    return changes


def _apply(
    changes: list[tuple[int, int, list[str]]],
    start: int,
    end: int,
    base: list[str],
) -> list[str]:
    out: list[str] = []
    cursor = start
    for change_start, change_end, replacement in changes:
        if change_end <= start or change_start >= end:
            continue
        if change_start > cursor:
            out.extend(base[cursor:change_start])
        out.extend(replacement)
        cursor = max(cursor, change_end)
    if cursor < end:
        out.extend(base[cursor:end])
    return out


def merge3(base_text: str, ours_text: str, theirs_text: str) -> tuple[str, int]:
    """Return the merged text and the number of conflicts."""
    base = base_text.split("\n")
    ours = ours_text.split("\n")
    theirs = theirs_text.split("\n")
    ours_changes = _changes(base, ours)
    theirs_changes = _changes(base, theirs)

    out: list[str] = []
    conflicts = 0
    index = 0
    ours_at = 0
    theirs_at = 0

    while index < len(base):
        next_starts = []
        if ours_at < len(ours_changes):
            next_starts.append(ours_changes[ours_at][0])
        if theirs_at < len(theirs_changes):
            next_starts.append(theirs_changes[theirs_at][0])
        if not next_starts:
            out.extend(base[index:])
            break

        start = min(next_starts)
        if start > index:
            out.extend(base[index:start])
        end = start
        ours_region: list[tuple[int, int, list[str]]] = []
        theirs_region: list[tuple[int, int, list[str]]] = []

        while True:
            advanced = False
            if ours_at < len(ours_changes) and ours_changes[ours_at][0] <= end:
                change = ours_changes[ours_at]
                end = max(end, change[1])
                ours_region.append(change)
                ours_at += 1
                advanced = True
            if theirs_at < len(theirs_changes) and theirs_changes[theirs_at][0] <= end:
                change = theirs_changes[theirs_at]
                end = max(end, change[1])
                theirs_region.append(change)
                theirs_at += 1
                advanced = True
            if not advanced:
                break

        ours_result = _apply(ours_region, start, end, base)
        theirs_result = _apply(theirs_region, start, end, base)
        if ours_result == theirs_result:
            out.extend(ours_result)
        elif not theirs_region:
            out.extend(ours_result)
        elif not ours_region:
            out.extend(theirs_result)
        else:
            conflicts += 1
            out.append(MARKER_OURS)
            out.extend(ours_result)
            out.append(MARKER_BASE)
            out.extend(base[start:end])
            out.append(MARKER_SEP)
            out.extend(theirs_result)
            out.append(MARKER_THEIRS)
        index = end

    return "\n".join(out), conflicts


def has_conflicts(text: str) -> bool:
    return any(line.startswith(MARKER_OURS) for line in text.split("\n"))
