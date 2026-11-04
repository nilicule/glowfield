"""FastAPI server for Glowfield.

The server is stateless: it only generates puzzles and hints. Anything about
the player (like having solved today's daily) lives in a cookie in their
browser.
"""

from __future__ import annotations

import secrets
from datetime import date
from functools import lru_cache
from html import escape
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .puzzle import DIFFICULTIES, generate, hint

STATIC = Path(__file__).parent / "static"
DAILY_DIFFICULTY = "medium"
# Daily seeds live above the range of random seeds so a daily board can't be
# loaded (and solved again) as an ordinary puzzle.
DAILY_SEED_BASE = 100_000_000

app = FastAPI(title="Glowfield")


class SubpathMiddleware:
    """Make the app work under a URL prefix however the proxy forwards it.

    With ``--root-path /glowfield`` uvicorn prepends the prefix to every
    request path, which is right when the proxy strips it (proxy_pass with
    a trailing slash). If the proxy passes the prefix through instead, the
    path arrives doubled (/glowfield/glowfield/...), so drop one copy. A bare
    /glowfield redirects to /glowfield/ so relative URLs resolve.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        root = scope.get("root_path", "")
        if root and scope["type"] == "http":
            path = scope["path"]
            doubled = root + root
            if path == doubled or path.startswith(doubled + "/"):
                path = path[len(root):]
                scope = dict(scope, path=path, raw_path=path.encode())
            if path == root:
                query = scope.get("query_string", b"").decode()
                location = root + "/" + (f"?{query}" if query else "")
                await send({"type": "http.response.start", "status": 308,
                            "headers": [(b"location", location.encode())]})
                await send({"type": "http.response.body", "body": b""})
                return
        await self.app(scope, receive, send)


app.add_middleware(SubpathMiddleware)


def daily_seed(day: date) -> int:
    return DAILY_SEED_BASE + day.toordinal()


def _check(difficulty: str) -> None:
    if difficulty not in DIFFICULTIES:
        raise HTTPException(404, f"unknown difficulty {difficulty!r}")


@app.get("/api/difficulties")
def difficulties() -> list[dict]:
    return [
        {"key": d.key, "label": d.label, "rows": d.rows, "cols": d.cols}
        for d in DIFFICULTIES.values()
    ]


@app.get("/api/puzzle")
def puzzle(difficulty: str = "beginner", seed: int | None = None) -> dict:
    _check(difficulty)
    if seed is None:
        seed = secrets.randbelow(1_000_000)
    if not 0 <= seed < DAILY_SEED_BASE:
        raise HTTPException(400, "seed out of range")
    return generate(difficulty, seed).to_dict()


@app.get("/api/daily")
def daily() -> dict:
    today = date.today()
    data = generate(DAILY_DIFFICULTY, daily_seed(today)).to_dict()
    data["daily"] = today.isoformat()
    return data


class HintRequest(BaseModel):
    difficulty: str
    seed: int = Field(ge=0, lt=10**9)
    fireflies: list[tuple[int, int]] = []
    empty: list[tuple[int, int]] = []


@app.post("/api/hint")
def get_hint(req: HintRequest) -> dict | None:
    _check(req.difficulty)
    p = generate(req.difficulty, req.seed)
    known = {tuple(c): True for c in req.fireflies} | {tuple(c): False for c in req.empty}
    ded = hint(p, known)
    if ded is None:
        return None
    return {
        "cells": ded.cells,
        "firefly": ded.firefly,
        "clues": ded.clues,
        "reason": ded.reason,
    }


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {"ok": True}


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@lru_cache
def _read(name: str) -> str:
    return (STATIC / name).read_text()


def _page(name: str, request: Request) -> HTMLResponse:
    """Serve a page with a <base> pointing at wherever the app is mounted.

    All URLs in the pages are relative, so behind a proxy at e.g.
    /glowfield/ (uvicorn --root-path /glowfield) everything resolves there.
    """
    base = request.scope.get("root_path", "").rstrip("/") + "/"
    html = _read(name).replace("<head>", f'<head>\n  <base href="{escape(base)}">', 1)
    return HTMLResponse(html)


@app.get("/", include_in_schema=False)
def index(request: Request) -> HTMLResponse:
    return _page("index.html", request)


@app.get("/about", include_in_schema=False)
def about(request: Request) -> HTMLResponse:
    return _page("about.html", request)
