"""FastAPI server for Glowfield."""

from __future__ import annotations

import secrets
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .puzzle import DIFFICULTIES, generate, hint

STATIC = Path(__file__).parent / "static"
DAILY_DIFFICULTY = "medium"

app = FastAPI(title="Glowfield")


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
    if not 0 <= seed < 10**9:
        raise HTTPException(400, "seed out of range")
    return generate(difficulty, seed).to_dict()


@app.get("/api/daily")
def daily() -> dict:
    today = date.today()
    data = generate(DAILY_DIFFICULTY, today.toordinal()).to_dict()
    data["daily"] = today.isoformat()
    return data


class HintRequest(BaseModel):
    difficulty: str
    seed: int
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
