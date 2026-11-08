"""The app shell: static UI, the document API, and one error shape."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from instructoravs import __version__

from . import config
from .routers.documents import router as documents_router

app = FastAPI(
    title="Instructoravs",
    version=__version__,
    description="Local generator for IT help guides, CVs and PDFs.",
    docs_url="/api/docs",
    redoc_url=None,
)

app.include_router(documents_router)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> RedirectResponse:
    return RedirectResponse("/static/logo.svg")
