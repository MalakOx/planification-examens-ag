"""Évaluation d'un planning : contraintes dures, contraintes souples, coût.

coût = W_HARD × (violations dures) + Σ poids_i × pénalité_souple_i   (à minimiser)
fitness = 1 / (1 + coût)                                              (à maximiser)

Contraintes dures
  H1  un groupe a deux examens au même créneau (compté par paire d'examens)
  H2  un examen n'a pas assez de places (compté par examen)
  H3  une salle a deux examens au même créneau     -> garanti à 0 par le décodeur
  H4  un surveillant à deux endroits / indisponible -> garanti à 0 par le décodeur
  H5  surveillant manquant dans une salle (compté par surveillant manquant)

Contraintes souples
  S1  deux examens le même jour pour un groupe (par paire)
  S2  deux examens sur deux jours consécutifs pour un groupe (par paire)
  S3  examen à gros effectif placé tard (somme des indices de jour)
  S4  déséquilibre des surveillances (écart-type du nombre de surveillances)
  S5  places gaspillées (total des places vides dans les salles affectées)
"""
from __future__ import annotations

from dataclasses import dataclass

from .decoder import Schedule, decode
from .models import Instance

W_HARD = 1000.0
SOFT_WEIGHTS = {"S1": 10.0, "S2": 3.0, "S3": 2.0, "S4": 10.0, "S5": 0.1}

HARD_LABELS = {
    "H1": "Groupe avec deux examens au même créneau",
    "H2": "Examen sans assez de places",
    "H3": "Salle utilisée deux fois au même créneau",
    "H4": "Surveillant à deux endroits ou indisponible",
    "H5": "Surveillant manquant",
}
SOFT_LABELS = {
    "S1": "Deux examens le même jour (groupe)",
    "S2": "Examens sur deux jours consécutifs (groupe)",
    "S3": "Gros examens placés tard",
    "S4": "Déséquilibre des surveillances (écart-type)",
    "S5": "Places gaspillées",
}


def _pstdev(values: list[int]) -> float:
    """Écart-type de population (statistics.pstdev est exact mais lent sur des entiers)."""
    if not values:
        return 0.0
    m = sum(values) / len(values)
    return (sum((v - m) ** 2 for v in values) / len(values)) ** 0.5


@dataclass
class Evaluation:
    hard: dict[str, float]
    soft: dict[str, float]
    cost: float
    schedule: Schedule

    @property
    def hard_total(self) -> float:
        return sum(self.hard.values())

    @property
    def soft_cost(self) -> float:
        return sum(SOFT_WEIGHTS[k] * v for k, v in self.soft.items())

    @property
    def fitness(self) -> float:
        return 1.0 / (1.0 + self.cost)

    @property
    def feasible(self) -> bool:
        return self.hard_total == 0


def evaluate(inst: Instance, slots: list[int], exams_of_group: dict[int, list[int]] | None = None) -> Evaluation:
    sched = decode(inst, slots)
    if exams_of_group is None:
        exams_of_group = inst.exams_of_group()
    n_days = len(inst.days)
    n_periods = len(inst.periods)
    day = [s // n_periods for s in slots]  # jour de chaque examen

    h1 = s1 = s2 = 0
    for exams in exams_of_group.values():
        per_slot: dict[int, int] = {}
        per_day = [0] * n_days
        for e in exams:
            s = slots[e]
            per_slot[s] = per_slot.get(s, 0) + 1
            per_day[day[e]] += 1
        same_slot = sum(c * (c - 1) // 2 for c in per_slot.values())
        same_day = sum(c * (c - 1) // 2 for c in per_day)
        h1 += same_slot
        s1 += same_day - same_slot
        s2 += sum(per_day[d] * per_day[d + 1] for d in range(n_days - 1))

    hard = {
        "H1": float(h1),
        "H2": float(sum(1 for u in sched.unseated if u > 0)),
        "H3": 0.0,
        "H4": 0.0,
        "H5": float(sum(sched.missing_invigilators)),
    }
    soft = {
        "S1": float(s1),
        "S2": float(s2),
        "S3": float(sum(day[e.id] for e in inst.exams
                        if e.enrolled >= inst.large_exam_threshold)),
        "S4": round(_pstdev(sched.duties), 4),
        "S5": float(sum(sched.wasted_seats)),
    }
    cost = W_HARD * sum(hard.values()) + sum(SOFT_WEIGHTS[k] * v for k, v in soft.items())
    return Evaluation(hard=hard, soft=soft, cost=round(cost, 4), schedule=sched)
