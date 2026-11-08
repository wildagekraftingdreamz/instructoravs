"""Instructoravs - document engine for IT help guides and CVs.

The engine is pure standard library: it parses Markdown into a small block
model, then renders that model to Markdown, plain text, HTML and PDF.  The
local web app in ``app/`` and the CLI in :mod:`instructoravs.cli` both use it.
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__ = ["__version__"]
