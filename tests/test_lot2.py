"""Tests du lot 2 : opérateurs génétiques, réparation, boucle AG."""
import random
from collections import Counter

from src.baseline import greedy_solution, random_solution
from src.fitness import evaluate
from src.ga import GAConfig, run_ga
from src.generator import generate
from src.operators import (CROSSOVERS, Repairer, mutate, roulette, tournament)
from tests.test_lot1 import tiny


def test_tournament_with_full_size_returns_best():
    costs = [5.0, 1.0, 3.0]
    assert tournament(costs, random.Random(0), k=3) == 1


def test_roulette_prefers_low_cost():
    rng = random.Random(0)
    picks = Counter(roulette([0.0, 1000.0], rng) for _ in range(2000))
    assert picks[0] > 0.9 * 2000


def test_crossovers_keep_genes_position_wise():
    rng = random.Random(0)
    a, b = list(range(10)), list(range(100, 110))
    for name, cross in CROSSOVERS.items():
        c1, c2 = cross(a, b, rng)
        assert len(c1) == len(c2) == 10, name
        for i in range(10):
            assert {c1[i], c2[i]} == {a[i], b[i]}, name


def test_mutation_rates():
    rng = random.Random(0)
    s = [0, 1, 2, 3, 4]
    assert mutate(s, 10, rng, gene_rate=0.0, swap_rate=0.0) == s
    swapped = mutate(s, 10, rng, gene_rate=0.0, swap_rate=1.0)
    assert sorted(swapped) == s and swapped != s
    assert all(0 <= x < 10 for x in mutate(s, 10, rng, gene_rate=1.0, swap_rate=0.0))


def test_repair_removes_group_conflicts():
    inst = tiny()
    bad = [0, 0, 0]
    ev = evaluate(inst, bad)
    fixed = Repairer(inst).repair(bad, ev, random.Random(0))
    assert evaluate(inst, fixed).hard["H1"] == 0


def test_ga_small_feasible_and_not_worse_than_greedy():
    inst = generate("small")
    greedy = evaluate(inst, greedy_solution(inst))
    res = run_ga(inst, GAConfig(pop_size=30, generations=40, seed=3))
    assert res.best.feasible
    assert res.best.cost <= greedy.cost
    assert res.history[0]["generation"] == 0 and len(res.history) == res.generations_run + 1
    costs = [h["best_cost"] for h in res.history]
    assert costs == sorted(costs, reverse=True)  # élitisme : le meilleur ne se dégrade jamais


def test_ga_fixes_greedy_shortage_on_medium():
    inst = generate("medium")
    assert not evaluate(inst, greedy_solution(inst)).feasible
    res = run_ga(inst, GAConfig(pop_size=40, generations=30, seed=1))
    assert res.best.feasible


def test_pure_ga_improves_random_population():
    inst = generate("small")
    rand = evaluate(inst, random_solution(inst, random.Random(0)))
    res = run_ga(inst, GAConfig(pop_size=30, generations=40, seed=0, repair=False, greedy_init_ratio=0))
    assert res.best.cost < rand.cost / 5


def test_ga_reproducible_with_seed():
    inst = generate("small")
    cfg = GAConfig(pop_size=20, generations=10, seed=5)
    assert run_ga(inst, cfg).best_slots == run_ga(inst, cfg).best_slots
