import pytest

from glowfield.puzzle import DIFFICULTIES, generate, hint, neighbors, solve


@pytest.mark.parametrize("difficulty", list(DIFFICULTIES))
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_generated_puzzle_is_solvable_without_guessing(difficulty, seed):
    p = generate(difficulty, seed)
    d = DIFFICULTIES[difficulty]
    solution = solve(p.rows, p.cols, p.clues, d.max_rule)
    assert solution is not None
    assert {cell for cell, f in solution.items() if f} == p.fireflies


@pytest.mark.parametrize("difficulty", list(DIFFICULTIES))
def test_clues_are_correct_and_never_on_fireflies(difficulty):
    p = generate(difficulty, 7)
    assert not (set(p.clues) & p.fireflies)
    for cell, value in p.clues.items():
        assert value == sum(nb in p.fireflies for nb in neighbors(cell, p.rows, p.cols))


def test_generation_is_deterministic():
    generate.cache_clear()
    a = generate("medium", 42)
    generate.cache_clear()
    b = generate("medium", 42)
    assert a == b


def test_hint_is_consistent_with_solution():
    p = generate("hard", 5)
    known = {}
    # Follow hints all the way through: every hint must be true and progress.
    while len(known) < p.rows * p.cols - len(p.clues):
        h = hint(p, known)
        assert h is not None and h.reason
        for cell in h.cells:
            assert (cell in p.fireflies) == h.firefly
            assert cell not in known
            known[cell] = h.firefly
    assert hint(p, known) is None


def test_hint_ignores_wrong_player_marks():
    p = generate("easy", 3)
    wrong_cell = next(iter(p.fireflies))
    h = hint(p, {wrong_cell: False})
    assert h is not None
    for cell in h.cells:
        assert (cell in p.fireflies) == h.firefly


@pytest.mark.parametrize("difficulty", list(DIFFICULTIES))
@pytest.mark.parametrize("seed", range(8))
def test_difficulty_targets_hold(difficulty, seed):
    from glowfield.puzzle import grade

    d = DIFFICULTIES[difficulty]
    p = generate(difficulty, seed)
    g = grade(p.rows, p.cols, p.clues, d.max_rule)
    assert g is not None
    assert g.has_choices(d.min_choices)
    if d.max_rule > 1:
        assert g.rule_steps[d.max_rule] >= 1


def test_easy_levels_never_narrow_to_a_single_move():
    from glowfield.puzzle import grade

    for difficulty in ("beginner", "easy"):
        for seed in range(20):
            p = generate(difficulty, seed)
            g = grade(p.rows, p.cols, p.clues, 1)
            assert g.min_choices() >= DIFFICULTIES[difficulty].min_choices
