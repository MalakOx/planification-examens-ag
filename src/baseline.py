"""Méthodes de référence auxquelles l'AG sera comparé.

* ``random_solution`` : chaque examen reçoit un créneau tiré au hasard.
* ``greedy_solution`` : heuristique classique de coloration de graphe —
  les examens les plus contraints (plus grand degré de conflit, puis plus gros
  effectif) sont placés en premier, chacun dans le créneau qui augmente le
  moins un coût local (conflits, places, surveillants, confort).
"""
from __future__ import annotations

import math
import random

from .fitness import SOFT_WEIGHTS, W_HARD
from .models import Instance


def random_solution(inst: Instance, rng: random.Random) -> list[int]:
    return [rng.randrange(inst.n_slots) for _ in inst.exams]


def random_search(inst: Instance, n_evals: int, rng: random.Random) -> list[int]:
    """Recherche aléatoire : tire ``n_evals`` solutions au hasard et garde la meilleure.
    Sert de référence « à budget égal » face à l'AG (même nombre d'évaluations)."""
    from .fitness import evaluate  # import local : fitness importe déjà ce module indirectement

    groups = inst.exams_of_group()
    best, best_cost = None, math.inf
    for _ in range(n_evals):
        s = random_solution(inst, rng)
        c = evaluate(inst, s, groups).cost
        if c < best_cost:
            best, best_cost = s, c
    return best


def _estimated_invigilators(enrolled: int) -> int:
    return 2 * math.ceil(enrolled / 36)


def greedy_solution(inst: Instance, rng: random.Random | None = None, noise: float = 0.0) -> list[int]:
    """Construit une solution gloutonne.

    ``noise`` > 0 perturbe légèrement l'ordre des examens et les égalités :
    utile pour produire des individus initiaux variés pour l'AG.
    """
    rng = rng or random.Random(0)
    n_slots, n_days = inst.n_slots, len(inst.days)
    degree = inst.conflict_degree()
    order = sorted(
        range(len(inst.exams)),
        key=lambda e: (-(degree[e] + rng.uniform(0, noise * 10)), -inst.exams[e].enrolled),
    )
    total_seats = sum(r.capacity for r in inst.rooms)
    n_rooms = len(inst.rooms)
    available_inv = [sum(1 for i in inst.invigilators if s not in i.unavailable) for s in range(n_slots)]

    slots = [-1] * len(inst.exams)
    group_slot: dict[tuple[int, int], int] = {}  # (groupe, créneau) -> nb d'examens
    group_day: dict[tuple[int, int], int] = {}  # (groupe, jour) -> nb d'examens
    seats_used = [0] * n_slots
    rooms_used = [0] * n_slots
    inv_used = [0] * n_slots

    for e in order:
        exam = inst.exams[e]
        est_rooms = math.ceil(exam.enrolled / 36)
        est_inv = _estimated_invigilators(exam.enrolled)
        best, best_cost = 0, math.inf
        for s in range(n_slots):
            d = inst.day_of(s)
            hard = sum(group_slot.get((g, s), 0) for g in exam.groups)
            hard += seats_used[s] + exam.enrolled > total_seats
            hard += rooms_used[s] + est_rooms > n_rooms
            hard += inv_used[s] + est_inv > available_inv[s]
            same_day = sum(group_day.get((g, d), 0) for g in exam.groups)
            adjacent = sum(group_day.get((g, d + k), 0) for g in exam.groups for k in (-1, 1)
                           if 0 <= d + k < n_days)
            late = d if exam.enrolled >= inst.large_exam_threshold else 0
            cost = (W_HARD * hard + SOFT_WEIGHTS["S1"] * same_day + SOFT_WEIGHTS["S2"] * adjacent
                    + SOFT_WEIGHTS["S3"] * late + 0.01 * s + rng.uniform(0, noise))
            if cost < best_cost:
                best, best_cost = s, cost
        slots[e] = best
        d = inst.day_of(best)
        for g in exam.groups:
            group_slot[(g, best)] = group_slot.get((g, best), 0) + 1
            group_day[(g, d)] = group_day.get((g, d), 0) + 1
        seats_used[best] += exam.enrolled
        rooms_used[best] += est_rooms
        inv_used[best] += est_inv
    return slots
