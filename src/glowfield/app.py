"""FastAPI server for Glowfield.

The server is stateless: it only generates puzzles and hints. Anything about
the player (like having solved today's daily) lives in a cookie in their
browser.
"""

from __future__ import annotations

import secrets
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .puzzle import DIFFICULTIES, generate, hint

STATIC = Path(__file__).parent / "static"
DAILY_DIFFICULTY = "medium"
# Daily seeds live above the range of random seeds so a daily board can't be
# loaded (and solved again) as an ordinary puzzle.
DAILY_SEED_BASE = 100_000_000

app = FastAPI(title="Glowfield")


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


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")
