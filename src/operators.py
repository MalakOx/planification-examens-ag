"""Opérateurs génétiques : sélection, croisement, mutation, réparation.

Un individu est une liste d'entiers : ``slots[e]`` = créneau de l'examen e.
"""
from __future__ import annotations

import random

from .fitness import Evaluation
from .models import Instance

# ---------------------------------------------------------------- sélection


def tournament(costs: list[float], rng: random.Random, k: int = 3) -> int:
    """Renvoie l'indice du meilleur (coût minimal) parmi k individus tirés au hasard."""
    contenders = rng.sample(range(len(costs)), k)
    return min(contenders, key=lambda i: costs[i])


def roulette(costs: list[float], rng: random.Random) -> int:
    """Roulette biaisée : probabilité proportionnelle à fitness = 1 / (1 + coût)."""
    weights = [1.0 / (1.0 + c) for c in costs]
    return rng.choices(range(len(costs)), weights=weights, k=1)[0]


SELECTIONS = {"tournoi": tournament, "roulette": roulette}

# ---------------------------------------------------------------- croisement


def uniform_crossover(a: list[int], b: list[int], rng: random.Random) -> tuple[list[int], list[int]]:
    c1, c2 = [], []
    for x, y in zip(a, b):
        if rng.random() < 0.5:
            c1.append(x); c2.append(y)
        else:
            c1.append(y); c2.append(x)
    return c1, c2


def one_point_crossover(a: list[int], b: list[int], rng: random.Random) -> tuple[list[int], list[int]]:
    p = rng.randrange(1, len(a))
    return a[:p] + b[p:], b[:p] + a[p:]


def two_point_crossover(a: list[int], b: list[int], rng: random.Random) -> tuple[list[int], list[int]]:
    p, q = sorted(rng.sample(range(1, len(a)), 2))
    return a[:p] + b[p:q] + a[q:], b[:p] + a[p:q] + b[q:]


CROSSOVERS = {"uniforme": uniform_crossover, "1 point": one_point_crossover,
              "2 points": two_point_crossover}

# ---------------------------------------------------------------- mutation


def mutate(slots: list[int], n_slots: int, rng: random.Random, gene_rate: float, swap_rate: float) -> list[int]:
    """Deux mutations complémentaires :
    * déplacement : chaque examen change de créneau avec la probabilité ``gene_rate`` ;
    * échange : avec la probabilité ``swap_rate``, deux examens échangent leurs créneaux
      (conserve l'occupation des créneaux, utile quand les ressources sont serrées).
    """
    out = list(slots)
    for e in range(len(out)):
        if rng.random() < gene_rate:
            out[e] = rng.randrange(n_slots)
    if rng.random() < swap_rate:
        i, j = rng.sample(range(len(out)), 2)
        out[i], out[j] = out[j], out[i]
    return out

# ---------------------------------------------------------------- réparation


class Repairer:
    """Réparation heuristique d'un individu non faisable.

    1. **Conflits de groupe (H1)** : chaque examen en conflit est déplacé vers le
       créneau qui minimise un coût local (conflits, saturation des ressources,
       confort des groupes).
    2. **Ressources (H2/H5)** : sur un créneau où il manque des places ou des
       surveillants, un examen est déplacé vers un créneau moins chargé.

    Le coût local n'est qu'une estimation ; l'individu réparé est ensuite réévalué
    par la vraie fonction de fitness.
    """

    def __init__(self, inst: Instance):
        self.inst = inst
        self.n_slots = inst.n_slots
        self.n_days = len(inst.days)
        self.available = [sum(1 for i in inst.invigilators if s not in i.unavailable)
                          for s in range(self.n_slots)]
        self.total_seats = sum(r.capacity for r in inst.rooms)

    def _local_cost(self, e: int, s: int, group_slot, group_day, inv_load, seat_load) -> float:
        inst, exam = self.inst, self.inst.exams[e]
        d = s // len(inst.periods)
        clash = sum(group_slot.get((g, s), 0) for g in exam.groups)
        same_day = sum(group_day.get((g, d), 0) for g in exam.groups)
        adjacent = sum(group_day.get((g, d + k), 0) for g in exam.groups for k in (-1, 1)
                       if 0 <= d + k < self.n_days)
        need = self._need(e)
        over_inv = max(0, inv_load[s] + need - self.available[s])
        over_seat = max(0, seat_load[s] + exam.enrolled - self.total_seats)
        return 1000 * clash + 300 * over_inv + 300 * (over_seat > 0) + 10 * same_day + 3 * adjacent

    def _need(self, e: int) -> int:
        """Surveillants estimés : une salle (2) jusqu'à 40, un amphi (3) jusqu'à 150,
        puis 2 par salle supplémentaire de ~36 places."""
        enrolled = self.inst.exams[e].enrolled
        if enrolled <= 40:
            return 2
        if enrolled <= 150:
            return 3
        return 3 + 2 * -(-(enrolled - 150) // 36)

    def repair(self, slots: list[int], ev: Evaluation, rng: random.Random) -> list[int]:
        inst = self.inst
        out = list(slots)
        group_slot: dict[tuple[int, int], int] = {}
        group_day: dict[tuple[int, int], int] = {}
        inv_load = [0] * self.n_slots
        seat_load = [0] * self.n_slots

        def place(e: int, s: int, sign: int) -> None:
            d = s // len(inst.periods)
            for g in inst.exams[e].groups:
                group_slot[(g, s)] = group_slot.get((g, s), 0) + sign
                group_day[(g, d)] = group_day.get((g, d), 0) + sign
            inv_load[s] += sign * self._need(e)
            seat_load[s] += sign * inst.exams[e].enrolled

        for e, s in enumerate(out):
            place(e, s, +1)

        def relocate(e: int) -> None:
            place(e, out[e], -1)
            best = min(range(self.n_slots),
                       key=lambda s: (self._local_cost(e, s, group_slot, group_day, inv_load, seat_load),
                                      rng.random()))
            out[e] = best
            place(e, best, +1)

        # 1. conflits de groupe
        order = list(range(len(out)))
        rng.shuffle(order)
        for e in order:
            if any(group_slot[(g, out[e])] > 1 for g in inst.exams[e].groups):
                relocate(e)

        # 2. créneaux en manque de places / surveillants
        sch = ev.schedule
        short_slots = {sch.slots[e] for e in range(len(out))
                       if sch.unseated[e] > 0 or sch.missing_invigilators[e] > 0}
        for s in short_slots:
            in_slot = [e for e in range(len(out)) if out[e] == s]
            if in_slot:
                relocate(rng.choice(in_slot))
        return out
