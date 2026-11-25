"""Décodage d'un chromosome en planning complet.

Le chromosome ne contient que le créneau de chaque examen. Le décodeur
affecte ensuite, créneau par créneau, de façon gloutonne et déterministe :

* les **salles** : examens traités du plus gros au plus petit ; on prend la
  plus petite salle libre qui suffit, sinon la plus grande salle libre et on
  continue avec le reste des étudiants (examen réparti sur plusieurs salles) ;
* les **surveillants** : pour chaque salle, les surveillants disponibles
  (pas indisponibles, pas déjà pris sur ce créneau, quota non atteint) les
  moins chargés jusque-là.

Par construction une salle ne reçoit qu'un examen par créneau (H3) et un
surveillant n'est jamais à deux endroits ni pendant une indisponibilité (H4).
Ce qui ne peut pas être satisfait est mesuré : étudiants sans place (H2) et
surveillants manquants (H5).
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import Instance


@dataclass
class Schedule:
    slots: list[int]  # créneau de chaque examen (le chromosome)
    rooms: list[list[int]]  # salles de chaque examen
    invigilators: list[list[int]]  # surveillants de chaque examen
    unseated: list[int]  # étudiants sans place, par examen
    missing_invigilators: list[int]  # surveillants manquants, par examen
    wasted_seats: list[int]  # places inoccupées dans les salles affectées, par examen
    duties: list[int]  # nombre de surveillances par surveillant


def decode(inst: Instance, slots: list[int]) -> Schedule:
    n = len(inst.exams)
    rooms_of = [[] for _ in range(n)]
    invs_of = [[] for _ in range(n)]
    unseated = [0] * n
    missing = [0] * n
    wasted = [0] * n
    duties = [0] * len(inst.invigilators)

    exams_in_slot: dict[int, list[int]] = {}
    for e, s in enumerate(slots):
        exams_in_slot.setdefault(s, []).append(e)

    enrolled = [e.enrolled for e in inst.exams]
    need_of_room = [r.invigilators_needed for r in inst.rooms]
    max_duties = [i.max_duties for i in inst.invigilators]
    rooms_by_cap = inst.rooms_by_capacity  # (capacité, id), croissant
    available = inst.available_by_slot

    for s in sorted(exams_in_slot):
        order = sorted(exams_in_slot[s], key=lambda e: -enrolled[e])  # du plus gros au plus petit
        # ---- salles -------------------------------------------------------
        free = list(rooms_by_cap)
        for e in order:
            remaining = enrolled[e]
            seats = 0
            while remaining > 0 and free:
                k = next((k for k, (cap, _) in enumerate(free) if cap >= remaining), len(free) - 1)
                cap, rid = free.pop(k)
                rooms_of[e].append(rid)
                seats += cap
                remaining -= cap
            unseated[e] = max(remaining, 0)
            wasted[e] = max(seats - enrolled[e], 0)

        # ---- surveillants -------------------------------------------------
        # File d'attente triée une seule fois par créneau : les surveillants pris sont
        # retirés de la file, la charge des autres ne change pas pendant le créneau.
        queue = sorted((i for i in available[s] if duties[i] < max_duties[i]),
                       key=lambda i: (duties[i], i))
        pos = 0
        for e in order:
            for rid in rooms_of[e]:
                need = need_of_room[rid]
                taken = queue[pos:pos + need]
                pos += len(taken)
                for i in taken:
                    duties[i] += 1
                    invs_of[e].append(i)
                missing[e] += need - len(taken)

    return Schedule(slots=list(slots), rooms=rooms_of, invigilators=invs_of, unseated=unseated,
                    missing_invigilators=missing, wasted_seats=wasted, duties=duties)
