"""Tests du lot 1 : modèle, générateur, décodeur, fitness, méthodes de référence."""
import random

import pytest

from src.baseline import greedy_solution, random_solution
from src.decoder import decode
from src.fitness import W_HARD, evaluate
from src.generator import SIZES, generate
from src.models import Exam, Group, Instance, Invigilator, Room


def tiny() -> Instance:
    """2 jours × 2 séances, 2 groupes, 3 examens, 2 salles, 4 surveillants."""
    groups = [Group(0, "A", 30), Group(1, "B", 30)]
    exams = [
        Exam(0, "E0", "Commun", (0, 1), 60),
        Exam(1, "E1", "Propre A", (0,), 30),
        Exam(2, "E2", "Propre B", (1,), 30),
    ]
    rooms = [Room(0, "Amphi", 60, "amphi"), Room(1, "S1", 30, "salle")]
    invs = [Invigilator(i, f"P{i}", max_duties=10) for i in range(4)]
    invs[3] = Invigilator(3, "P3", max_duties=10, unavailable=frozenset({0}))
    return Instance("tiny", ["J1", "J2"], ["08:30", "14:00"], rooms, groups, exams, invs,
                    large_exam_threshold=50)


def test_slot_helpers():
    inst = tiny()
    assert inst.n_slots == 4
    assert (inst.day_of(3), inst.period_of(3)) == (1, 1)
    assert inst.slot_label(2) == "J2 08:30"
    assert inst.conflict_degree() == [2, 1, 1]


def test_h1_conflict_counted_per_pair():
    inst = tiny()
    ev = evaluate(inst, [0, 0, 0])  # E0 + E1 pour A, E0 + E2 pour B au même créneau
    assert ev.hard["H1"] == 2
    assert ev.cost >= 2 * W_HARD


def test_feasible_spread_solution():
    inst = tiny()
    ev = evaluate(inst, [0, 2, 3])  # E0 J1 matin, E1 J2 matin, E2 J2 après-midi
    assert ev.feasible
    assert ev.soft["S1"] == 0  # A : J1, J2 ; B : J1, J2 -> jamais deux le même jour
    assert ev.soft["S2"] == 2  # A et B : examens sur J1 puis J2
    assert ev.soft["S3"] == 0  # le gros examen (60) est le 1er jour


def test_same_day_and_late_large_exam():
    inst = tiny()
    ev = evaluate(inst, [3, 2, 0])  # E0 (gros) J2 a-m ; E1 J2 matin -> A deux fois le même jour
    assert ev.soft["S1"] == 1
    assert ev.soft["S3"] == 1


def test_decoder_rooms_and_capacity():
    inst = tiny()
    sch = decode(inst, [0, 0, 1])  # E0 (60) et E1 (30) au créneau 0
    assert sch.rooms[0] == [0]  # le plus gros prend l'amphi (plus petite salle suffisante)
    assert sch.rooms[1] == [1]
    assert sch.unseated == [0, 0, 0]
    sch = decode(inst, [0, 0, 0])  # 120 étudiants pour 90 places
    assert sum(sch.unseated) == 30


def test_decoder_splits_exam_over_rooms():
    inst = tiny()
    inst.rooms[0] = Room(0, "Petite", 40, "salle")
    sch = decode(inst, [0, 1, 2])  # E0 (60) : 40 + 30
    assert sorted(sch.rooms[0]) == [0, 1] and sch.unseated[0] == 0
    assert sch.wasted_seats[0] == 10


def test_decoder_invigilators_respect_unavailability_and_shortage():
    inst = tiny()
    sch = decode(inst, [0, 0, 1])  # créneau 0 : amphi (3) + salle (2) = 5, mais P3 indisponible
    on_slot0 = sch.invigilators[0] + sch.invigilators[1]
    assert 3 not in on_slot0
    assert len(on_slot0) == len(set(on_slot0)) == 3
    assert sch.missing_invigilators[0] + sch.missing_invigilators[1] == 2
    assert evaluate(inst, [0, 0, 1]).hard["H5"] == 2


def test_decoder_respects_max_duties():
    inst = tiny()
    inst.invigilators[:] = [Invigilator(i, f"P{i}", max_duties=1) for i in range(4)]
    sch = decode(inst, [0, 1, 2])
    assert max(sch.duties) <= 1


def test_generator_deterministic_and_roundtrip(tmp_path):
    a, b = generate("small", seed=7), generate("small", seed=7)
    assert a.to_dict() == b.to_dict()
    a.save(tmp_path / "x.json")
    c = Instance.load(tmp_path / "x.json")
    assert c.to_dict() == a.to_dict()
    assert all(e.enrolled == sum(c.groups[g].size for g in e.groups) for e in c.exams)


def test_generator_realism_features():
    inst = generate("xlarge")
    names = {g.name for g in inst.groups}
    assert any(n.endswith("-Dette") for n in names)
    debt = [g.id for g in inst.groups if g.name.endswith("-Dette")]
    # un groupe en dette passe des examens de deux niveaux différents
    levels = {inst.exams[e].code.rsplit("-", 1)[0] for e in inst.exams_of_group()[debt[0]]}
    assert len(levels) >= 2
    assert any(e.code == "COM-ANG1" and e.enrolled > 150 for e in inst.exams)
    assert any("vacataire" in i.name for i in inst.invigilators)
    # instance faisable en capacité de surveillance globale
    assert sum(i.max_duties for i in inst.invigilators) > 2 * len(inst.exams)


@pytest.mark.parametrize("size", list(SIZES))
def test_greedy_beats_random_without_group_conflicts(size):
    """Les données sont volontairement serrées : la gloutonne évite les conflits de groupe
    mais peut manquer de surveillants (H5) — c'est l'AG qui doit atteindre la faisabilité."""
    inst = generate(size)
    greedy = evaluate(inst, greedy_solution(inst))
    rng = random.Random(0)
    rand = min(evaluate(inst, random_solution(inst, rng)).cost for _ in range(20))
    assert greedy.hard["H1"] == 0
    assert greedy.cost < rand
    assert all(0 <= s < inst.n_slots for s in greedy.schedule.slots)
