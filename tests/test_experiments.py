"""Tests du lot 4 : une tâche d'expérience produit un enregistrement complet."""
import random
from dataclasses import replace

from src.baseline import random_search
from src.experiments import ga_task, run_task, summarize
from src.fitness import evaluate
from src.ga import GAConfig
from src.generator import generate

import pandas as pd


def test_ga_task_record_with_history():
    task = ga_task("T", "small", "test", 0, replace(GAConfig(), pop_size=10, generations=5), history=True)
    rec = run_task(task)
    assert rec["instance"] == "small" and rec["generations"] == 5
    assert len(rec["history"]) == 6
    assert rec["evaluations"] > 0 and rec["cost"] > 0


def test_random_search_task_and_budget():
    inst = generate("small")
    best = random_search(inst, 30, random.Random(0))
    single = evaluate(inst, best).cost
    assert single <= evaluate(inst, random_search(inst, 1, random.Random(0))).cost
    rec = run_task({"exp": "T", "instance": "small", "variant": "rs", "seed": 0,
                    "kind": "random_search", "n_evals": 30})
    assert rec["evaluations"] == 30 and rec["first_feasible_gen"] is None


def test_summarize_columns():
    df = pd.DataFrame({"variant": ["a", "a", "b"], "cost": [1.0, 3.0, 2.0], "feasible": [True, False, True],
                       "seconds": [1, 1, 1], "evaluations": [10, 10, 10]})
    s = summarize(df, ["variant"])
    assert list(s["cout_moyen"]) == [2.0, 2.0]
    assert list(s["faisables"]) == ["50 %", "100 %"]
