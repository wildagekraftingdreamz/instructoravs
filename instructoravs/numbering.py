"""Heading counters shared by the text and PDF renderers."""

from __future__ import annotations


class SectionNumbers:
    """Turns heading levels into 1, 1.1, 1.1.2 labels."""

    def __init__(self) -> None:
        self._counters = [0] * 6

    def bump(self, level: int) -> str:
        level = max(1, min(6, level))
        self._counters[level - 1] += 1
        for index in range(level, 6):
            self._counters[index] = 0
        return ".".join(str(value) for value in self._counters[:level])

    def label(self, level: int) -> str:
        return self.bump(level)
