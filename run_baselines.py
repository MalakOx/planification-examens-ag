"""Démo du lot 1 : génère les jeux de données puis évalue les deux méthodes
de référence (aléatoire, gloutonne) sur chacun.

Usage : python run_baselines.py
Sorties : data/*.json, results/baselines.csv, results/planning_glouton_<taille>.csv
"""
from __future__ import annotations

import random
import statistics
import time
from pathlib import Path

import pandas as pd

from src.baseline import greedy_solution, random_solution
from src.fitness import evaluate
from src.generator import SIZES, generate
from src.report import constraints_table, grid_table, planning_table

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    pd.set_option("display.width", 200)
    rows = []
    for size in SIZES:
        inst = generate(size)
        inst.save(ROOT / "data" / f"{size}.json")
        print("\n" + "=" * 100 + "\n" + inst.summary())

        rng = random.Random(1)
        t0 = time.perf_counter()
        rand = [evaluate(inst, random_solution(inst, rng)) for _ in range(30)]
        t_eval = (time.perf_counter() - t0) / 30
        t0 = time.perf_counter()
        greedy = evaluate(inst, greedy_solution(inst))
        t_greedy = time.perf_counter() - t0

        for name, evs in (("aléatoire (moy. 30)", rand), ("gloutonne", [greedy])):
            rows.append({
                "Instance": size, "Méthode": name,
                "Coût": round(statistics.mean(ev.cost for ev in evs), 1),
                "Violations dures": round(statistics.mean(ev.hard_total for ev in evs), 1),
                **{k: round(statistics.mean(ev.hard[k] for ev in evs), 1) for k in ("H1", "H2", "H5")},
                **{k: round(statistics.mean(ev.soft[k] for ev in evs), 2) for k in greedy.soft},
            })
        print(f"évaluation d'une solution : {t_eval * 1000:.2f} ms — gloutonne : {t_greedy * 1000:.0f} ms")
        print("\nGloutonne — contraintes :\n" + constraints_table(greedy).to_string(index=False))
        print("\nGloutonne — calendrier :\n" + grid_table(inst, greedy).to_string())
        planning_table(inst, greedy).to_csv(RESULTS / f"planning_glouton_{size}.csv",
                                            index=False, encoding="utf-8-sig")

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "baselines.csv", index=False, encoding="utf-8-sig")
    print("\n" + "=" * 100 + "\nRécapitulatif des méthodes de référence :\n" + df.to_string(index=False))


if __name__ == "__main__":
    main()
