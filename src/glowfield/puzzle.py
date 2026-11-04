"""Puzzle generation and logical solving for Glowfield (reverse minesweeper).

A board is a grid of cells. Some cells are *clues*: they show how many of their
eight neighbours hold a firefly, and never hold one themselves. Every other
cell is *open*: it either holds a firefly or is empty. The player has to work
out which is which.

Puzzles are generated so they can always be solved by pure deduction: we start
with every non-firefly cell as a clue, then remove clues one at a time as long
as the logical solver below can still solve the board without guessing.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache

Cell = tuple[int, int]


@dataclass(frozen=True)
class Difficulty:
    key: str
    label: str
    rows: int
    cols: int
    density: float  # fraction of cells holding a firefly
    max_rule: int  # strongest deduction rule the player needs (see iter_deductions)
    removal: float  # chance of trying to remove each clue (1.0 = as sparse as possible)
    # Easy levels: at every point there are at least this many cells the
    # simplest rule settles, so you're never hunting for the one move left.
    min_choices: int = 0
    # Hard levels: the strongest rule must be needed at least this often,
    # not just once somewhere on the board.
    min_hard_steps: int = 0


# Difficulty comes from the logic, not the board size. Beginner and Easy only
# ever need single-clue reasoning and always offer several moves at once;
# Medium adds comparing two clues, Hard and Expert need overlap reasoning
# repeatedly.
DIFFICULTIES: dict[str, Difficulty] = {
    d.key: d
    for d in [
        Difficulty("beginner", "Beginner", 6, 6, 0.30, 1, 0.6, min_choices=4),
        Difficulty("easy", "Easy", 7, 7, 0.32, 1, 1.0, min_choices=3),
        Difficulty("medium", "Medium", 8, 8, 0.34, 2, 1.0, min_hard_steps=2),
        Difficulty("hard", "Hard", 9, 9, 0.36, 3, 1.0, min_hard_steps=2),
        Difficulty("expert", "Expert", 10, 10, 0.38, 3, 1.0, min_hard_steps=4),
    ]
}


def neighbors(cell: Cell, rows: int, cols: int) -> list[Cell]:
    r, c = cell
    return [
        (r + dr, c + dc)
        for dr in (-1, 0, 1)
        for dc in (-1, 0, 1)
        if (dr or dc) and 0 <= r + dr < rows and 0 <= c + dc < cols
    ]


def _fireflies(n: int) -> str:
    return f"{n} {'firefly' if n == 1 else 'fireflies'}"


@dataclass(frozen=True)
class Deduction:
    """A fact that follows logically from the clues and the known cells."""

    cells: tuple[Cell, ...]
    firefly: bool
    clues: tuple[Cell, ...]
    rule: int
    reason: str


# A constraint is (clue cell, its unknown open neighbours, fireflies still needed).
Constraint = tuple[Cell, frozenset[Cell], int]


def _constraints(
    rows: int, cols: int, clues: dict[Cell, int], known: dict[Cell, bool]
) -> list[Constraint]:
    out: list[Constraint] = []
    for clue, value in clues.items():
        unknown: list[Cell] = []
        placed = 0
        for nb in neighbors(clue, rows, cols):
            if nb in clues:
                continue
            state = known.get(nb)
            if state is None:
                unknown.append(nb)
            elif state:
                placed += 1
        if unknown:
            out.append((clue, frozenset(unknown), value - placed))
    return out


def iter_deductions(
    rows: int,
    cols: int,
    clues: dict[Cell, int],
    known: dict[Cell, bool],
    max_rule: int = 3,
) -> Iterator[Deduction]:
    """Yield deductions, simplest rules first.

    Rule 1: a single clue is already satisfied, or needs all of its open cells.
    Rule 2: one clue's open cells are a subset of another's.
    Rule 3: two overlapping clues, where one needs so many more fireflies than
            the other that its private cells must all hold one.
    """
    cons = _constraints(rows, cols, clues, known)

    for clue, unknown, need in cons:
        cells = tuple(sorted(unknown))
        if need == 0:
            reason = (
                "A 0 means there are no fireflies around it."
                if clues[clue] == 0
                else f"This {clues[clue]} already has all its fireflies, "
                "so every other cell around it is empty."
            )
            yield Deduction(cells, False, (clue,), 1, reason)
        elif need == len(unknown):
            yield Deduction(
                cells,
                True,
                (clue,),
                1,
                f"This {clues[clue]} still needs {_fireflies(need)} and has exactly "
                f"{len(unknown)} open {'cell' if len(unknown) == 1 else 'cells'} left.",
            )

    if max_rule < 2:
        return

    by_cell: dict[Cell, list[int]] = defaultdict(list)
    for i, (_, unknown, _) in enumerate(cons):
        for cell in unknown:
            by_cell[cell].append(i)

    for i, (a, ua, na) in enumerate(cons):
        partners = {j for cell in ua for j in by_cell[cell] if j != i}
        for j in sorted(partners):
            b, ub, nb = cons[j]
            diff = nb - na
            if ua < ub:
                rest = tuple(sorted(ub - ua))
                prefix = (
                    f"Every open cell around the {clues[a]} also touches the "
                    f"{clues[b]}. The {clues[a]} needs {_fireflies(na)} there and the "
                    f"{clues[b]} needs {_fireflies(nb)}, "
                )
                if diff == 0:
                    yield Deduction(
                        rest, False, (a, b), 2,
                        prefix + f"so the {clues[b]}'s other cells are empty.",
                    )
                elif diff == len(rest):
                    yield Deduction(
                        rest, True, (a, b), 2,
                        prefix + f"so the {clues[b]}'s other cells all hold fireflies.",
                    )
            elif max_rule >= 3:
                only_b = ub - ua
                only_a = ua - ub
                if only_b and diff == len(only_b):
                    reason = (
                        f"The {clues[b]} needs {_fireflies(diff)} more than the "
                        f"{clues[a]}, and has exactly {len(only_b)} "
                        f"{'cell' if len(only_b) == 1 else 'cells'} the {clues[a]} "
                        "can't see."
                    )
                    yield Deduction(
                        tuple(sorted(only_b)), True, (a, b), 3,
                        reason + " Those must all hold fireflies.",
                    )
                    if only_a:
                        yield Deduction(
                            tuple(sorted(only_a)), False, (a, b), 3,
                            reason + f" So the {clues[a]}'s own cells are empty.",
                        )


def solve(
    rows: int,
    cols: int,
    clues: dict[Cell, int],
    max_rule: int = 3,
    known: dict[Cell, bool] | None = None,
) -> dict[Cell, bool] | None:
    """Solve by deduction only. Returns the full solution, or None if stuck."""
    known = dict(known or {})
    open_count = rows * cols - len(clues)
    while len(known) < open_count:
        progress = False
        for ded in iter_deductions(rows, cols, clues, known, max_rule):
            if ded.rule > 1 and progress:
                break  # recompute with the cheap rule first
            for cell in ded.cells:
                known[cell] = ded.firefly
            progress = True
        if not progress:
            return None
    return known


@dataclass(frozen=True)
class Grade:
    """How a puzzle feels to solve, measured by replaying the solver.

    waves: for each round of the solve, (cells the simplest rule can settle
        right now, cells still unknown). A wide wave means many easy moves
        to choose from; a wave of 1 means you're on a narrow chain.
    rule_steps: how many rounds needed each rule (rule 1 = single clue).
    """

    waves: tuple[tuple[int, int], ...]
    rule_steps: dict[int, int]

    def min_choices(self) -> int:
        """Fewest easy moves on offer at any point (ignoring the endgame)."""
        return min(
            (avail for avail, remaining in self.waves if avail < remaining),
            default=10**9,
        )

    def has_choices(self, target: int) -> bool:
        return all(avail >= min(target, remaining) for avail, remaining in self.waves)


def grade(
    rows: int, cols: int, clues: dict[Cell, int], max_rule: int = 3
) -> Grade | None:
    """Replay a simplest-first solve; None if it needs guessing (or a stronger rule)."""
    known: dict[Cell, bool] = {}
    open_count = rows * cols - len(clues)
    waves: list[tuple[int, int]] = []
    steps = {1: 0, 2: 0, 3: 0}
    while len(known) < open_count:
        remaining = open_count - len(known)
        easy: dict[Cell, bool] = {}
        advanced: Deduction | None = None
        for ded in iter_deductions(rows, cols, clues, known, max_rule):
            if ded.rule == 1:
                easy.update((cell, ded.firefly) for cell in ded.cells)
            elif easy:
                break  # rule 1 always runs first, so we're done collecting
            elif advanced is None or ded.rule < advanced.rule:
                advanced = ded  # a player would spot the simpler rule first
                if ded.rule == 2:
                    break
        waves.append((len(easy), remaining))
        if easy:
            known.update(easy)
            steps[1] += 1
        elif advanced:
            known.update((cell, advanced.firefly) for cell in advanced.cells)
            steps[advanced.rule] += 1
        else:
            return None
    return Grade(tuple(waves), steps)


@dataclass(frozen=True)
class Puzzle:
    difficulty: str
    seed: int
    rows: int
    cols: int
    clues: dict[Cell, int]
    fireflies: frozenset[Cell]

    @property
    def id(self) -> str:
        return f"{self.difficulty}-{self.seed}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "difficulty": self.difficulty,
            "label": DIFFICULTIES[self.difficulty].label,
            "seed": self.seed,
            "rows": self.rows,
            "cols": self.cols,
            "clues": [[r, c, n] for (r, c), n in sorted(self.clues.items())],
            "fireflies": [[r, c] for r, c in sorted(self.fireflies)],
        }


@lru_cache(maxsize=512)
def generate(difficulty: str, seed: int) -> Puzzle:
    """Deterministically build a no-guess puzzle for (difficulty, seed)."""
    d = DIFFICULTIES[difficulty]
    rng = random.Random(f"{difficulty}:{seed}")
    cells = [(r, c) for r in range(d.rows) for c in range(d.cols)]
    count = round(d.density * len(cells))
    best: tuple[int, Puzzle] | None = None

    def playable(clues: dict[Cell, int]) -> Grade | None:
        g = grade(d.rows, d.cols, clues, d.max_rule)
        if g is None or not g.has_choices(d.min_choices):
            return None
        return g

    for _ in range(100):
        fireflies = frozenset(rng.sample(cells, count))
        clues = {
            cell: sum(nb in fireflies for nb in neighbors(cell, d.rows, d.cols))
            for cell in cells
            if cell not in fireflies
        }
        if playable(clues) is None:
            continue  # e.g. a firefly fully boxed in by other fireflies

        order = list(clues)
        rng.shuffle(order)
        for cell in order:
            if rng.random() > d.removal:
                continue
            value = clues.pop(cell)
            if playable(clues) is None:
                clues[cell] = value

        puzzle = Puzzle(difficulty, seed, d.rows, d.cols, clues, fireflies)
        if d.max_rule == 1:
            return puzzle
        hard_steps = grade(d.rows, d.cols, clues, d.max_rule).rule_steps[d.max_rule]
        if hard_steps >= d.min_hard_steps:
            return puzzle
        if best is None or hard_steps > best[0]:
            best = (hard_steps, puzzle)

    if best is None:
        raise RuntimeError(f"could not generate {difficulty} puzzle for seed {seed}")
    return best[1]


def hint(puzzle: Puzzle, known: dict[Cell, bool]) -> Deduction | None:
    """The simplest next deduction given what the player has already found."""
    # Ignore anything that contradicts the solution so hints stay truthful.
    known = {
        cell: state
        for cell, state in known.items()
        if cell not in puzzle.clues and (cell in puzzle.fireflies) == state
    }
    return next(
        iter_deductions(puzzle.rows, puzzle.cols, puzzle.clues, known, 3), None
    )
