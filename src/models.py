"""Modèle de données du problème de planification des examens.

Une *instance* regroupe tout ce qui est fixé avant l'optimisation :
créneaux, salles, groupes d'étudiants, examens et surveillants.
Une *solution* (chromosome) associe à chaque examen l'indice d'un créneau.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from functools import cached_property
from pathlib import Path


@dataclass(frozen=True)
class Room:
    id: int
    name: str
    capacity: int
    kind: str  # "amphi" ou "salle"

    @property
    def invigilators_needed(self) -> int:
        """H5 : 3 surveillants dans un amphi, 2 dans une salle."""
        return 3 if self.kind == "amphi" else 2


@dataclass(frozen=True)
class Group:
    id: int
    name: str  # ex. "2ING-GL-G1"
    size: int


@dataclass(frozen=True)
class Exam:
    id: int
    code: str
    name: str
    groups: tuple[int, ...]  # groupes qui passent cet examen
    enrolled: int  # nombre d'inscrits (somme des tailles des groupes)


@dataclass(frozen=True)
class Invigilator:
    id: int
    name: str
    max_duties: int
    unavailable: frozenset[int] = field(default_factory=frozenset)  # indices de créneaux


@dataclass
class Instance:
    name: str
    days: list[str]
    periods: list[str]  # séances d'une journée, ex. ["08:30", "11:00", "14:00"]
    rooms: list[Room]
    groups: list[Group]
    exams: list[Exam]
    invigilators: list[Invigilator]
    large_exam_threshold: int = 100  # S3 : un examen « à gros effectif »

    # ---- créneaux ---------------------------------------------------------
    @property
    def n_slots(self) -> int:
        return len(self.days) * len(self.periods)

    def day_of(self, slot: int) -> int:
        return slot // len(self.periods)

    def period_of(self, slot: int) -> int:
        return slot % len(self.periods)

    def slot_label(self, slot: int) -> str:
        return f"{self.days[self.day_of(slot)]} {self.periods[self.period_of(slot)]}"

    # ---- index utiles -------------------------------------------------------
    @cached_property
    def rooms_by_capacity(self) -> list[tuple[int, int]]:
        """(capacité, id) des salles, par capacité croissante."""
        return sorted((r.capacity, r.id) for r in self.rooms)

    @cached_property
    def available_by_slot(self) -> list[list[int]]:
        """Pour chaque créneau, les ids des surveillants qui ne sont pas indisponibles."""
        return [[i.id for i in self.invigilators if s not in i.unavailable]
                for s in range(self.n_slots)]

    def exams_of_group(self) -> dict[int, list[int]]:
        """groupe -> liste des examens qu'il passe."""
        out: dict[int, list[int]] = {g.id: [] for g in self.groups}
        for e in self.exams:
            for g in e.groups:
                out[g].append(e.id)
        return out

    def conflict_degree(self) -> list[int]:
        """Pour chaque examen, nombre d'autres examens partageant au moins un groupe."""
        by_group = self.exams_of_group()
        neighbours: list[set[int]] = [set() for _ in self.exams]
        for exams in by_group.values():
            for a in exams:
                neighbours[a].update(exams)
        return [len(n) - 1 for n in neighbours]

    def summary(self) -> str:
        seats = sum(r.capacity for r in self.rooms)
        return (
            f"{self.name} : {len(self.exams)} examens, {len(self.groups)} groupes, "
            f"{self.n_slots} créneaux ({len(self.days)} j × {len(self.periods)} séances), "
            f"{len(self.rooms)} salles ({seats} places), {len(self.invigilators)} surveillants"
        )

    # ---- sérialisation ----------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        for inv in d["invigilators"]:
            inv["unavailable"] = sorted(inv["unavailable"])
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Instance":
        return cls(
            name=d["name"],
            days=list(d["days"]),
            periods=list(d["periods"]),
            rooms=[Room(**r) for r in d["rooms"]],
            groups=[Group(**g) for g in d["groups"]],
            exams=[Exam(**{**e, "groups": tuple(e["groups"])}) for e in d["exams"]],
            invigilators=[
                Invigilator(**{**i, "unavailable": frozenset(i["unavailable"])})
                for i in d["invigilators"]
            ],
            large_exam_threshold=d.get("large_exam_threshold", 100),
        )

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Instance":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
