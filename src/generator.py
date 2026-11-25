"""Génération de jeux de données synthétiques inspirés de l'ISI.

Les cursus, matières et noms sont fictifs mais réalistes. Plusieurs sources
de difficulté reproduisent une vraie session d'examens :

* **groupes de TD** : chaque niveau (L1-LSI, 1ING, 2ING-GL…) compte plusieurs
  groupes qui passent les mêmes examens au même moment ;
* **tronc commun 2ING** : examens partagés par toutes les spécialités ;
* **examens mutualisés** : ex. « Anglais 1 » commun à L1-LSI et L1-LIG
  (≈ 180 étudiants, forcément réparti sur plusieurs salles) ;
* **étudiants en dette** : un petit groupe par niveau repasse 2–3 modules du
  niveau précédent → conflits *entre* niveaux ;
* **vacataires** : surveillants présents seulement 2–3 jours de la session ;
* ressources serrées : peu de salles et de surveillants par rapport aux besoins.

Usage : python -m src.generator   (écrit data/<taille>.json)
"""
from __future__ import annotations

import random
from pathlib import Path

from .models import Exam, Group, Instance, Invigilator, Room

DAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"]
PERIODS = ["08:30", "11:00", "14:00"]

# niveau -> (nb de groupes de TD, matières propres au niveau)
PROGRAMMES: dict[str, tuple[int, list[str]]] = {
    "L1-LSI": (4, ["Algorithmique 1", "Analyse 1", "Algèbre 1", "Architecture des ordinateurs",
                   "Logique formelle"]),
    "L2-LSI": (3, ["Structures de données", "Systèmes d'exploitation", "Bases de données",
                   "Probabilités", "Programmation orientée objet", "Réseaux 1"]),
    "L3-LSI": (3, ["Génie logiciel", "Compilation", "Développement web",
                   "Recherche opérationnelle", "Sécurité informatique"]),
    "L1-LIG": (2, ["Programmation C", "Mathématiques discrètes", "Électronique numérique",
                   "Introduction aux SI", "Techniques de communication"]),
    "L2-LIG": (2, ["Programmation Java", "Conception des SI", "Statistiques",
                   "Réseaux locaux", "Systèmes embarqués", "Droit informatique"]),
    "L3-LIG": (2, ["ERP", "Business Intelligence", "Développement mobile", "Gestion de projet SI",
                   "Audit des SI"]),
    "1ING": (3, ["Analyse numérique", "Théorie des graphes", "Bases de données avancées",
                 "Programmation système", "Réseaux avancés", "Techniques de calcul intelligent",
                 "Management de projet"]),
    "2ING-GL": (2, ["Architecture logicielle", "Tests et qualité", "DevOps"]),
    "2ING-SSI": (1, ["Cryptographie", "Sécurité des réseaux", "Audit de sécurité"]),
    "2ING-IA": (1, ["Apprentissage automatique", "Vision par ordinateur", "Traitement du langage"]),
    "M1-SSI": (1, ["Cryptanalyse", "Forensique", "Sécurité du cloud", "Gouvernance SSI",
                   "Anglais scientifique"]),
}
# examens communs à plusieurs niveaux (créés avec les niveaux présents)
COMMON_EXAMS: list[tuple[str, str, list[str]]] = [
    ("COM-ANG1", "Anglais 1", ["L1-LSI", "L1-LIG"]),
    ("COM-ANG2", "Anglais 2", ["L2-LSI", "L2-LIG"]),
    ("2ING-TC-01", "Big Data", ["2ING-GL", "2ING-SSI", "2ING-IA"]),
    ("2ING-TC-02", "Cloud computing", ["2ING-GL", "2ING-SSI", "2ING-IA"]),
    ("2ING-TC-03", "Entrepreneuriat", ["2ING-GL", "2ING-SSI", "2ING-IA"]),
]
# niveau -> niveau précédent (pour les étudiants en dette)
PREVIOUS = {"L2-LSI": "L1-LSI", "L3-LSI": "L2-LSI", "L2-LIG": "L1-LIG", "L3-LIG": "L2-LIG",
            "2ING-GL": "1ING", "2ING-SSI": "1ING", "2ING-IA": "1ING"}

PRENOMS = ["Amel", "Sami", "Leila", "Mehdi", "Ines", "Karim", "Sonia", "Walid", "Hela", "Nabil",
           "Rim", "Anis", "Nour", "Hichem", "Salma", "Fares", "Olfa", "Bilel", "Yosra", "Tarek",
           "Meriem", "Slim", "Asma", "Imed", "Rania", "Chokri", "Emna", "Lotfi", "Sarra", "Ridha"]
NOMS = ["Ben Salah", "Trabelsi", "Gharbi", "Jlassi", "Haddad", "Mansouri", "Ayari", "Bouazizi",
        "Chaabane", "Ferchichi", "Hammami", "Khelifi", "Mejri", "Sassi", "Zouari", "Belhaj",
        "Dridi", "Karoui", "Masmoudi", "Rekik", "Toumi", "Baccouche", "Guesmi", "Nasri"]

SIZES = {
    "small": dict(levels=["L1-LSI", "L2-LSI", "1ING"], n_days=5,
                  amphis=[120], salles=4, n_inv=15),
    "medium": dict(levels=["L1-LSI", "L2-LSI", "L3-LSI", "1ING", "2ING-GL", "2ING-SSI"], n_days=7,
                   amphis=[120], salles=7, n_inv=28),
    "large": dict(levels=["L1-LSI", "L2-LSI", "L3-LSI", "L1-LIG", "L2-LIG", "1ING",
                          "2ING-GL", "2ING-SSI", "2ING-IA"], n_days=8,
                  amphis=[150, 120], salles=9, n_inv=30),
    "xlarge": dict(levels=list(PROGRAMMES), n_days=8,
                   amphis=[150, 120], salles=10, n_inv=37),
}


def _day_names(n_days: int) -> list[str]:
    """Jours ouvrés (lundi→samedi) sur plusieurs semaines : 'S1-Lun', …"""
    return [f"S{d // len(DAYS) + 1}-{DAYS[d % len(DAYS)]}" for d in range(n_days)]


def generate(size: str = "medium", seed: int = 42) -> Instance:
    cfg = SIZES[size]
    levels: list[str] = cfg["levels"]
    rng = random.Random(seed)
    days = _day_names(cfg["n_days"])
    n_periods = len(PERIODS)
    n_slots = len(days) * n_periods

    # --- groupes de TD + groupes « en dette » -------------------------------
    groups: list[Group] = []
    groups_of_level: dict[str, list[int]] = {}
    debt_group_of: dict[str, int] = {}  # niveau -> groupe en dette (rattaché à ce niveau)
    for level in levels:
        n_groups, _ = PROGRAMMES[level]
        groups_of_level[level] = []
        for k in range(n_groups):
            groups.append(Group(id=len(groups), name=f"{level}-G{k + 1}", size=rng.randint(26, 34)))
            groups_of_level[level].append(groups[-1].id)
        if PREVIOUS.get(level) in levels:
            groups.append(Group(id=len(groups), name=f"{level}-Dette", size=rng.randint(4, 12)))
            groups_of_level[level].append(groups[-1].id)
            debt_group_of[level] = groups[-1].id

    # --- examens --------------------------------------------------------------
    exam_groups: list[tuple[str, str, list[int]]] = []
    for level in levels:
        for k, subject in enumerate(PROGRAMMES[level][1]):
            exam_groups.append((f"{level}-{k + 1:02d}", subject, list(groups_of_level[level])))
    for code, subject, lvls in COMMON_EXAMS:
        gids = [g for lvl in lvls if lvl in levels for g in groups_of_level[lvl]]
        if gids:
            exam_groups.append((code, subject, gids))
    # les étudiants en dette repassent 2–3 modules du niveau précédent
    for level, dg in debt_group_of.items():
        prev = PREVIOUS[level]
        prev_exams = [i for i, (code, _, gids) in enumerate(exam_groups)
                      if set(gids) & set(groups_of_level[prev])]
        for i in rng.sample(prev_exams, min(len(prev_exams), rng.randint(2, 3))):
            exam_groups[i][2].append(dg)

    exams = [Exam(id=i, code=code, name=name, groups=tuple(gids),
                  enrolled=sum(groups[g].size for g in gids))
             for i, (code, name, gids) in enumerate(exam_groups)]

    # --- salles ----------------------------------------------------------------
    rooms: list[Room] = []
    for k, cap in enumerate(cfg["amphis"]):
        rooms.append(Room(id=len(rooms), name=f"Amphi {chr(65 + k)}", capacity=cap, kind="amphi"))
    for k in range(cfg["salles"]):
        rooms.append(Room(id=len(rooms), name=f"Salle {101 + k}",
                          capacity=rng.choice([30, 32, 36, 40]), kind="salle"))

    # --- surveillants : permanents et vacataires --------------------------------
    names = rng.sample([f"{p} {n}" for p in PRENOMS for n in NOMS], cfg["n_inv"])
    invigilators: list[Invigilator] = []
    for k, name in enumerate(names):
        unavailable: set[int] = set()
        r = rng.random()
        if r < 0.30:  # vacataire : présent seulement 2–3 jours
            present = set(rng.sample(range(len(days)), rng.randint(2, 3)))
            unavailable.update(s for s in range(n_slots) if s // n_periods not in present)
            name, max_duties = f"{name} (vacataire)", rng.randint(3, 5)
        else:
            max_duties = rng.randint(5, 9)
            if r < 0.50:  # permanent absent une journée (conseil, soutenance…)
                d = rng.randrange(len(days))
                unavailable.update(range(d * n_periods, (d + 1) * n_periods))
            elif r < 0.80:  # quelques séances isolées (cours, réunion…)
                unavailable.update(rng.sample(range(n_slots), rng.randint(1, 3)))
        invigilators.append(Invigilator(id=k, name=name, max_duties=max_duties,
                                        unavailable=frozenset(unavailable)))

    return Instance(name=size, days=days, periods=list(PERIODS), rooms=rooms, groups=groups,
                    exams=exams, invigilators=invigilators, large_exam_threshold=100)


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "data"
    for size in SIZES:
        inst = generate(size)
        inst.save(out / f"{size}.json")
        print(inst.summary())


if __name__ == "__main__":
    main()
