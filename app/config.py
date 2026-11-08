"""Paths and defaults for the local web app."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
STORE_DIR = Path(
    os.environ.get("INSTRUCTORAVS_HOME", str(BASE_DIR / "data" / "documents"))
)
PORT = int(os.environ.get("INSTRUCTORAVS_PORT", "8770"))
HOST = os.environ.get("INSTRUCTORAVS_HOST", "127.0.0.1")

STORE_DIR.mkdir(parents=True, exist_ok=True)
