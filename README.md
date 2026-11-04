# Glowfield

A reverse minesweeper with fireflies. Every number tells you how many fireflies
sit in the 8 cells around it. Find them all.

- **Double-click** an open cell to place a firefly.
- **Click once** to rule a cell out.
- Three mistakes and the fireflies scatter.
- Every puzzle can be solved by logic alone. The hint button shows the next
  deduction and explains it.

## Run

```sh
uv sync
uv run glowfield            # http://127.0.0.1:8000
uv run glowfield --reload   # auto-reload while developing
```

## Test

```sh
uv run pytest
```

## How it works

- `src/glowfield/puzzle.py`: puzzle generator and logic solver. A board starts
  with every non-firefly cell as a clue, and clues are removed while the
  solver can still finish without guessing. Harder difficulties require
  stronger deduction rules (subset and overlap reasoning between two clues).
- `src/glowfield/app.py`: FastAPI endpoints (`/api/puzzle`, `/api/daily`,
  `/api/hint`) plus the static frontend.
- `src/glowfield/static/`: the browser game (vanilla HTML/CSS/JS).

Puzzles are deterministic per `difficulty-seed`, e.g. `/#hard-1234`, so a
puzzle ID can be shared or replayed.

The server is stateless and stores nothing about players. The daily puzzle
can be solved once per day: a win is remembered in a `gf_daily` cookie in
the browser, which then shows the finished board instead of a new attempt.
Losing doesn't set it, so you can retry.

## License

[MIT](LICENSE) © 2026 Remco Brink. You're free to use, change and share
Glowfield, as long as you keep the copyright notice and give attribution.
