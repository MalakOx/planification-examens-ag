"""Algorithme génétique pour la planification des examens.

Boucle générationnelle avec élitisme :

    population initiale (aléatoire + gloutonne bruitée)
    répéter jusqu'au nombre max de générations ou à la stagnation :
        garder les `elitism` meilleurs
        tant que la nouvelle population n'est pas pleine :
            sélectionner deux parents (tournoi ou roulette)
            croiser (probabilité p_c) puis muter les deux enfants
            évaluer ; si non faisable et réparation active : réparer puis réévaluer
        population <- nouvelle population
"""
from __future__ import annotations

import random
import time
from dataclasses import asdict, dataclass, field
from typing import Callable

from .baseline import greedy_solution, random_solution
from .fitness import Evaluation, evaluate
from .models import Instance
from .operators import CROSSOVERS, SELECTIONS, Repairer, mutate


@dataclass
class GAConfig:
    pop_size: int = 80
    generations: int = 300
    crossover: str = "uniforme"  # "uniforme" | "1 point" | "2 points"
    crossover_rate: float = 0.8
    selection: str = "tournoi"  # "tournoi" | "roulette"
    tournament_k: int = 3
    gene_mutation_rate: float = 0.03  # probabilité de déplacer chaque examen
    swap_rate: float = 0.3  # probabilité d'un échange de deux examens par enfant
    elitism: int = 2
    repair: bool = True
    greedy_init_ratio: float = 0.2  # part de la population initiale construite par la gloutonne
    stagnation: int = 100  # arrêt si le meilleur ne s'améliore plus pendant N générations
    seed: int = 0


@dataclass
class GAResult:
    best_slots: list[int]
    best: Evaluation
    history: list[dict] = field(default_factory=list)  # une ligne par génération
    generations_run: int = 0
    evaluations: int = 0
    seconds: float = 0.0
    config: dict = field(default_factory=dict)


class GeneticAlgorithm:
    def __init__(self, inst: Instance, config: GAConfig | None = None):
        self.inst = inst
        self.cfg = config or GAConfig()
        self.rng = random.Random(self.cfg.seed)
        self.exams_of_group = inst.exams_of_group()
        self.repairer = Repairer(inst)
        self._cache: dict[tuple[int, ...], Evaluation] = {}
        self.evaluations = 0

    # ------------------------------------------------------------ évaluation
    def evaluate(self, slots: list[int]) -> Evaluation:
        key = tuple(slots)
        ev = self._cache.get(key)
        if ev is None:
            ev = evaluate(self.inst, slots, self.exams_of_group)
            self.evaluations += 1
            if len(self._cache) > 50_000:
                self._cache.clear()
            self._cache[key] = ev
        return ev

    def _finish(self, slots: list[int]) -> tuple[list[int], Evaluation]:
        """Évalue un enfant, le répare s'il n'est pas faisable (et si la réparation est active)."""
        ev = self.evaluate(slots)
        if self.cfg.repair and not ev.feasible:
            repaired = self.repairer.repair(slots, ev, self.rng)
            ev2 = self.evaluate(repaired)
            if ev2.cost <= ev.cost:
                return repaired, ev2
        return slots, ev

    # ------------------------------------------------------------ population
    def initial_population(self) -> list[list[int]]:
        n_greedy = round(self.cfg.pop_size * self.cfg.greedy_init_ratio)
        pop = [greedy_solution(self.inst)] if n_greedy else []
        while len(pop) < n_greedy:
            pop.append(greedy_solution(self.inst, random.Random(self.rng.random()), noise=1.0))
        while len(pop) < self.cfg.pop_size:
            pop.append(random_solution(self.inst, self.rng))
        return pop

    # ------------------------------------------------------------ boucle
    def run(self, on_generation: Callable[[dict], None] | None = None) -> GAResult:
        cfg, rng, n_slots = self.cfg, self.rng, self.inst.n_slots
        select = SELECTIONS[cfg.selection]
        cross = CROSSOVERS[cfg.crossover]
        t0 = time.perf_counter()

        pop, evs = [], []
        for ind in self.initial_population():
            ind, ev = self._finish(ind)
            pop.append(ind); evs.append(ev)

        best_i = min(range(len(pop)), key=lambda i: evs[i].cost)
        best_slots, best_ev = list(pop[best_i]), evs[best_i]
        history: list[dict] = []
        since_improve = 0
        gen = 0

        def record(g: int) -> None:
            costs = [ev.cost for ev in evs]
            row = {"generation": g, "best_cost": best_ev.cost, "mean_cost": sum(costs) / len(costs),
                   "best_hard": best_ev.hard_total, "best_soft": round(best_ev.soft_cost, 3),
                   "feasible_ratio": sum(ev.feasible for ev in evs) / len(evs),
                   "seconds": time.perf_counter() - t0}
            history.append(row)
            if on_generation:
                on_generation(row)

        record(0)
        for gen in range(1, cfg.generations + 1):
            costs = [ev.cost for ev in evs]
            pick = (lambda: select(costs, rng, cfg.tournament_k)) if cfg.selection == "tournoi" \
                else (lambda: select(costs, rng))
            order = sorted(range(len(pop)), key=lambda i: costs[i])
            new_pop = [pop[i] for i in order[:cfg.elitism]]
            new_evs = [evs[i] for i in order[:cfg.elitism]]
            while len(new_pop) < cfg.pop_size:
                a, b = pop[pick()], pop[pick()]
                c1, c2 = cross(a, b, rng) if rng.random() < cfg.crossover_rate else (list(a), list(b))
                for child in (c1, c2):
                    if len(new_pop) == cfg.pop_size:
                        break
                    child = mutate(child, n_slots, rng, cfg.gene_mutation_rate, cfg.swap_rate)
                    child, ev = self._finish(child)
                    new_pop.append(child); new_evs.append(ev)
            pop, evs = new_pop, new_evs

            gen_best = min(range(len(pop)), key=lambda i: evs[i].cost)
            if evs[gen_best].cost < best_ev.cost - 1e-9:
                best_slots, best_ev = list(pop[gen_best]), evs[gen_best]
                since_improve = 0
            else:
                since_improve += 1
            record(gen)
            if since_improve >= cfg.stagnation:
                break

        return GAResult(best_slots=best_slots, best=best_ev, history=history, generations_run=gen,
                        evaluations=self.evaluations, seconds=time.perf_counter() - t0,
                        config=asdict(cfg))


def run_ga(inst: Instance, config: GAConfig | None = None,
           on_generation: Callable[[dict], None] | None = None) -> GAResult:
    return GeneticAlgorithm(inst, config).run(on_generation)
