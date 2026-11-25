"""Démo du lot 2 : lance l'AG sur une instance, compare aux méthodes de référence,
trace la courbe de convergence et exporte le planning obtenu.

Usage : python run_ga.py [small|medium|large|xlarge] [--seed N]
Sorties : results/convergence_<taille>.png, results/planning_ag_<taille>.csv
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.baseline import greedy_solution, random_solution  # noqa: E402
from src.fitness import evaluate  # noqa: E402
from src.ga import GAConfig, run_ga  # noqa: E402
from src.generator import SIZES, generate  # noqa: E402
from src.report import constraints_table, grid_table, planning_table  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"


def plot_convergence(history: list[dict], greedy_cost: float, title: str, path: Path) -> None:
    gens = [h["generation"] for h in history]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(gens, [h["best_cost"] for h in history], label="meilleur individu", lw=2)
    ax.plot(gens, [h["mean_cost"] for h in history], label="moyenne de la population", lw=1, alpha=0.7)
    ax.axhline(greedy_cost, color="grey", ls="--", label="heuristique gloutonne")
    ax.set_yscale("log")
    ax.set_xlabel("génération")
    ax.set_ylabel("coût (échelle log)")
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("size", nargs="?", default="medium", choices=list(SIZES))
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    RESULTS.mkdir(exist_ok=True)

    inst = generate(args.size)
    print(inst.summary())
    rand = evaluate(inst, random_solution(inst, random.Random(args.seed)))
    greedy = evaluate(inst, greedy_solution(inst))

    def progress(row: dict) -> None:
        if row["generation"] % 25 == 0:
            print(f"  gén. {row['generation']:3d}  meilleur = {row['best_cost']:9.1f}  "
                  f"moyenne = {row['mean_cost']:10.1f}  faisables = {row['feasible_ratio']:.0%}")

    res = run_ga(inst, GAConfig(seed=args.seed), on_generation=progress)
    print(f"\nAG : {res.generations_run} générations, {res.evaluations} évaluations, {res.seconds:.1f} s")
    print(f"{'Méthode':12s} {'Coût':>9s} {'Dures':>6s} {'Souple':>8s}")
    for name, ev in (("aléatoire", rand), ("gloutonne", greedy), ("AG", res.best)):
        print(f"{name:12s} {ev.cost:9.1f} {ev.hard_total:6.0f} {ev.soft_cost:8.1f}")

    print("\nAG — contraintes :\n" + constraints_table(res.best).to_string(index=False))
    print("\nAG — calendrier :\n" + grid_table(inst, res.best).to_string())
    planning_table(inst, res.best).to_csv(RESULTS / f"planning_ag_{args.size}.csv",
                                          index=False, encoding="utf-8-sig")
    plot_convergence(res.history, greedy.cost, f"Convergence de l'AG — instance {args.size}",
                     RESULTS / f"convergence_{args.size}.png")
    print(f"\n→ results/convergence_{args.size}.png, results/planning_ag_{args.size}.csv")


if __name__ == "__main__":
    main()
