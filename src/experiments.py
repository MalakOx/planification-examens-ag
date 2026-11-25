"""Campagne d'expériences du rapport (section « Résultats »).

E1  Convergence de l'AG (10 exécutions, moyenne ± écart-type) — medium, xlarge
E2  Influence des paramètres (population, mutation, croisement) — medium
E3  Comparaison des opérateurs (sélection, croisement) — medium
E4  Apport de chaque composant (AG pur, + réparation, + init. gloutonne, complet) — medium, xlarge
E5  Comparaison aux méthodes de référence sur les 4 instances
    (aléatoire, recherche aléatoire à budget égal, gloutonne, AG)
E6  Le planning final (meilleure exécution sur xlarge) : figures + Excel

E2 et E3 partent d'une population **aléatoire** (sans individus gloutons) pour que
l'effet des opérateurs ne soit pas masqué par une bonne initialisation.

Usage : python -m src.experiments [e1 e2 e3 e4 e5 e6] [--workers 3] [--quick]
Sorties : results/experiences/*.csv, *.png, RESULTATS.md
"""
from __future__ import annotations

import argparse
import json
import random
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .baseline import greedy_solution, random_search, random_solution  # noqa: E402
from .fitness import evaluate  # noqa: E402
from .ga import GAConfig, run_ga  # noqa: E402
from .generator import SIZES, generate  # noqa: E402
from .report import to_excel  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "results" / "experiences"
NO_STOP = 10**9  # désactive l'arrêt sur stagnation (courbes de même longueur)

# Palette catégorielle validée (ordre fixe), encres et surface — mode clair (rapport imprimé)
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "legend.frameon": False,
    "lines.linewidth": 2,
})

# =================================================================== exécution


_INSTANCES: dict = {}


def _instance(size: str):
    if size not in _INSTANCES:
        _INSTANCES[size] = generate(size)
    return _INSTANCES[size]


def run_task(task: dict) -> dict:
    """Une exécution (AG ou recherche aléatoire) → un enregistrement. Fonction de niveau
    module pour pouvoir être lancée dans un processus séparé."""
    inst = _instance(task["instance"])
    t0 = time.perf_counter()
    if task["kind"] == "ga":
        res = run_ga(inst, GAConfig(**task["cfg"]))
        ev, history = res.best, res.history
        gens, evals = res.generations_run, res.evaluations
    else:  # recherche aléatoire à budget égal
        slots = random_search(inst, task["n_evals"], random.Random(task["seed"]))
        ev, history, gens, evals = evaluate(inst, slots), [], 0, task["n_evals"]
    first_feasible = next((h["generation"] for h in history if h["best_hard"] == 0), None)
    rec = {k: task[k] for k in ("exp", "instance", "variant", "seed")}
    rec.update(cost=ev.cost, hard=ev.hard_total, soft=round(ev.soft_cost, 3), feasible=ev.feasible,
               generations=gens, evaluations=evals, seconds=round(time.perf_counter() - t0, 2),
               first_feasible_gen=first_feasible, slots=json.dumps(ev.schedule.slots))
    if task.get("keep_history"):
        rec["history"] = [(h["best_cost"], h["mean_cost"]) for h in history]
    return rec


def run_all(tasks: list[dict], workers: int) -> list[dict]:
    out, t0 = [], time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_task, t) for t in tasks]
        for k, f in enumerate(as_completed(futures), 1):
            r = f.result()
            out.append(r)
            print(f"  [{k:3d}/{len(tasks)}] {r['exp']} {r['instance']:7s} {r['variant']:28s} "
                  f"graine {r['seed']:2d} → coût {r['cost']:9.1f}  ({r['seconds']:.0f} s, "
                  f"total {time.perf_counter() - t0:.0f} s)", flush=True)
    return out


def ga_task(exp: str, instance: str, variant: str, seed: int, cfg: GAConfig, history=False) -> dict:
    return {"exp": exp, "instance": instance, "variant": variant, "seed": seed, "kind": "ga",
            "cfg": asdict(replace(cfg, seed=seed)), "keep_history": history}


def summarize(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    g = df.groupby(by, sort=False)
    s = g.agg(cout_moyen=("cost", "mean"), ecart_type=("cost", "std"), meilleur=("cost", "min"),
              pire=("cost", "max"), faisables=("feasible", "mean"), duree_s=("seconds", "mean"),
              evaluations=("evaluations", "mean")).reset_index()
    s["faisables"] = (s["faisables"] * 100).round(0).astype(int).astype(str) + " %"
    return s.round({"cout_moyen": 1, "ecart_type": 1, "meilleur": 1, "pire": 1, "duree_s": 1,
                    "evaluations": 0})


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def curves(records: list[dict], variant: str, col: int = 0) -> np.ndarray:
    return np.array([[h[col] for h in r["history"]] for r in records if r["variant"] == variant])


def band(ax, y: np.ndarray, color: str, label: str, ls="-") -> None:
    x = np.arange(y.shape[1])
    m, sd = y.mean(axis=0), y.std(axis=0)
    ax.plot(x, m, color=color, label=label, ls=ls)
    ax.fill_between(x, np.maximum(m - sd, 1), m + sd, color=color, alpha=0.15, lw=0)


# =================================================================== expériences


def e1(workers: int, seeds: int) -> str:
    base = GAConfig(generations=200, stagnation=NO_STOP)
    tasks = [ga_task("E1", size, "AG complet", s, base, history=True)
             for size in ("medium", "xlarge") for s in range(seeds)]
    recs = run_all(tasks, workers)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, size in zip(axes, ("medium", "xlarge")):
        rs = [r for r in recs if r["instance"] == size]
        inst = _instance(size)
        greedy = evaluate(inst, greedy_solution(inst)).cost
        band(ax, curves(rs, "AG complet", 0), C[0], "meilleur individu")
        band(ax, curves(rs, "AG complet", 1), C[1], "moyenne de la population", ls="--")
        ax.axhline(greedy, color=INK2, ls=":", lw=1.5, label="heuristique gloutonne")
        ax.set_yscale("log"); ax.set_title(f"Instance {size}")
        ax.set_xlabel("génération"); ax.set_ylabel("coût (échelle log)")
    axes[0].legend(loc="center right")
    fig.suptitle(f"E1 — Convergence de l'AG (moyenne ± écart-type sur {seeds} exécutions)")
    fig.tight_layout(); fig.savefig(OUT / "E1_convergence.png", dpi=160); plt.close(fig)
    df = pd.DataFrame(recs).drop(columns=["history"])
    df.to_csv(OUT / "E1_convergence.csv", index=False)
    tab = summarize(df, ["instance"])
    ff = df.groupby("instance", sort=False)["first_feasible_gen"].mean().round(1).values
    tab.insert(1, "1re génération faisable (moy.)", ff)
    return "## E1 — Convergence\n\n![](E1_convergence.png)\n\n" + md_table(tab)


E2_STUDIES = {
    "population": [(str(n), {"pop_size": n}) for n in (20, 40, 80, 120)],
    "mutation": [(str(p), {"gene_mutation_rate": p}) for p in (0.0, 0.01, 0.03, 0.06, 0.1)],
    "croisement": [(str(p), {"crossover_rate": p}) for p in (0.0, 0.4, 0.8, 1.0)],
}
E3_STUDIES = {
    "sélection": [("tournoi k=2", {"tournament_k": 2}), ("tournoi k=3", {"tournament_k": 3}),
                  ("tournoi k=5", {"tournament_k": 5}), ("roulette", {"selection": "roulette"})],
    "croisement": [(c, {"crossover": c}) for c in ("uniforme", "1 point", "2 points")],
}


def _run_param_study(exp: str, workers: int, seeds: int, studies: dict, fname: str) -> pd.DataFrame:
    base = GAConfig(generations=150, stagnation=NO_STOP, greedy_init_ratio=0.0)
    tasks = [ga_task(exp, "medium", f"{study}={label}", s, replace(base, **kw))
             for study, variants in studies.items() for label, kw in variants for s in range(seeds)]
    df = pd.DataFrame(run_all(tasks, workers))
    df.to_csv(OUT / f"{fname}.csv", index=False)
    return df


def _plot_param_study(df: pd.DataFrame, studies: dict, title: str, fname: str,
                      categorical: bool) -> pd.DataFrame:
    """Coût final moyen ± écart-type par variante. Les valeurs numériques sont reliées
    (tendance) ; les opérateurs (catégories) restent des points isolés."""
    fig, axes = plt.subplots(1, len(studies), figsize=(4 * len(studies), 3.8), sharey=True)
    axes = np.atleast_1d(axes)
    order = [f"{st}={lab}" for st, vs in studies.items() for lab, _ in vs]
    tab = summarize(df, ["variant"]).set_index("variant").loc[order].reset_index()
    for ax, (study, variants) in zip(axes, studies.items()):
        labels = [lab for lab, _ in variants]
        rows = tab[tab["variant"].str.startswith(study + "=")]
        x = np.arange(len(labels))
        ax.errorbar(x, rows["cout_moyen"], yerr=rows["ecart_type"], fmt="o" if categorical else "o-",
                    color=C[0], ms=9, capsize=4, lw=2, mec=SURFACE, mew=2)
        best = int(np.argmin(rows["cout_moyen"].values))
        ax.annotate(f"{rows['cout_moyen'].iloc[best]:.1f}", (x[best], rows["cout_moyen"].iloc[best]),
                    xytext=(10, -4), textcoords="offset points", fontsize=8, color=INK2)
        ax.set_xticks(x, [lab.replace(" k=", "\nk=") for lab in labels])
        ax.set_title(study); ax.grid(axis="x", visible=False)
        ax.set_xlim(-0.5, len(labels) - 0.5)
    axes[0].set_ylabel("coût final (moyenne ± écart-type)")
    fig.suptitle(title); fig.tight_layout(); fig.savefig(OUT / f"{fname}.png", dpi=160); plt.close(fig)
    return tab


def e2(workers: int, seeds: int, replot: bool = False) -> str:
    df = pd.read_csv(OUT / "E2_parametres.csv") if replot else \
        _run_param_study("E2", workers, seeds, E2_STUDIES, "E2_parametres")
    seeds = df["seed"].nunique()
    tab = _plot_param_study(df, E2_STUDIES,
                            f"E2 — Influence des paramètres (medium, 150 générations, {seeds} exécutions)",
                            "E2_parametres", categorical=False)
    return "## E2 — Paramètres\n\n![](E2_parametres.png)\n\n" + md_table(tab)


def e3(workers: int, seeds: int, replot: bool = False) -> str:
    df = pd.read_csv(OUT / "E3_operateurs.csv") if replot else \
        _run_param_study("E3", workers, seeds, E3_STUDIES, "E3_operateurs")
    seeds = df["seed"].nunique()
    tab = _plot_param_study(df, E3_STUDIES, f"E3 — Comparaison des opérateurs (medium, {seeds} exécutions)",
                            "E3_operateurs", categorical=True)
    return "## E3 — Opérateurs\n\n![](E3_operateurs.png)\n\n" + md_table(tab)


ABLATION = [
    ("AG pur", dict(greedy_init_ratio=0.0, repair=False)),
    ("+ réparation", dict(greedy_init_ratio=0.0, repair=True)),
    ("+ init. gloutonne", dict(greedy_init_ratio=0.2, repair=False)),
    ("AG complet", dict(greedy_init_ratio=0.2, repair=True)),
]


def _plot_e4(recs: list[dict]) -> None:
    """Courbes moyennes par composant ; la valeur finale de chaque courbe est donnée dans la
    légende (les fins de courbes sont trop proches pour être étiquetées directement)."""
    seeds = len({r["seed"] for r in recs})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, size in zip(axes, ("medium", "xlarge")):
        rs = [r for r in recs if r["instance"] == size]
        for color, (name, _) in zip(C, ABLATION):
            y = curves(rs, name).mean(axis=0)
            ax.plot(np.arange(len(y)), y, color=color, label=f"{name} — final {y[-1]:.0f}")
        ax.set_yscale("log"); ax.set_title(f"Instance {size}")
        ax.set_xlabel("génération"); ax.set_ylabel("meilleur coût (moyenne, log)")
        ax.legend(loc="upper right", fontsize=9)
    fig.suptitle(f"E4 — Apport de chaque composant (moyenne sur {seeds} exécutions)")
    fig.tight_layout(); fig.savefig(OUT / "E4_composants.png", dpi=160); plt.close(fig)


def e4(workers: int, seeds: int, replot: bool = False) -> str:
    hist_path = OUT / "E4_historiques.json"
    if replot:
        recs = json.loads(hist_path.read_text(encoding="utf-8"))
    else:
        base = GAConfig(generations=200, stagnation=NO_STOP)
        tasks = [ga_task("E4", size, name, s, replace(base, **kw), history=True)
                 for size in ("medium", "xlarge") for name, kw in ABLATION for s in range(seeds)]
        recs = run_all(tasks, workers)
        hist_path.write_text(json.dumps(recs), encoding="utf-8")
    _plot_e4(recs)
    df = pd.DataFrame(recs).drop(columns=["history"])
    df.to_csv(OUT / "E4_composants.csv", index=False)
    tab = summarize(df, ["instance", "variant"])
    ff = df.groupby(["instance", "variant"], sort=False)["first_feasible_gen"].mean().round(1).values
    tab.insert(2, "1re génération faisable (moy.)", ff)
    return "## E4 — Composants\n\n![](E4_composants.png)\n\n" + md_table(tab)


def e5(workers: int, seeds: int) -> str:
    sizes = list(SIZES)
    ga_recs = run_all([ga_task("E5", size, "AG", s, GAConfig()) for size in sizes for s in range(seeds)],
                      workers)
    budget = {size: int(np.mean([r["evaluations"] for r in ga_recs if r["instance"] == size]))
              for size in sizes}
    rs_tasks = [{"exp": "E5", "instance": size, "variant": "recherche aléatoire", "seed": s,
                 "kind": "random_search", "n_evals": budget[size]}
                for size in sizes for s in range(max(3, seeds // 2))]
    rs_recs = run_all(rs_tasks, workers)
    rows = []
    for size in sizes:
        inst = _instance(size)
        rng = random.Random(0)
        for k in range(30):
            ev = evaluate(inst, random_solution(inst, rng))
            rows.append({"exp": "E5", "instance": size, "variant": "aléatoire", "seed": k, "cost": ev.cost,
                         "hard": ev.hard_total, "soft": ev.soft_cost, "feasible": ev.feasible,
                         "evaluations": 1, "seconds": 0.0})
        t0 = time.perf_counter()
        ev = evaluate(inst, greedy_solution(inst))
        rows.append({"exp": "E5", "instance": size, "variant": "gloutonne", "seed": 0, "cost": ev.cost,
                     "hard": ev.hard_total, "soft": ev.soft_cost, "feasible": ev.feasible,
                     "evaluations": 1, "seconds": round(time.perf_counter() - t0, 3)})
    df = pd.concat([pd.DataFrame(rows), pd.DataFrame(rs_recs), pd.DataFrame(ga_recs)], ignore_index=True)
    df.to_csv(OUT / "E5_comparaison.csv", index=False)
    methods = ["aléatoire", "recherche aléatoire", "gloutonne", "AG"]
    tab = summarize(df, ["instance", "variant"])
    tab["variant"] = pd.Categorical(tab["variant"], methods, ordered=True)
    tab["instance"] = pd.Categorical(tab["instance"], sizes, ordered=True)
    tab = tab.sort_values(["instance", "variant"]).reset_index(drop=True)
    hard = df.groupby(["instance", "variant"])["hard"].mean().round(1)
    tab.insert(2, "violations dures (moy.)", [hard[(i, v)] for i, v in zip(tab["instance"], tab["variant"])])

    fig, ax = plt.subplots(figsize=(10, 4.4))
    width = 0.2
    x = np.arange(len(sizes))
    for k, (m, color) in enumerate(zip(methods, C)):
        vals = [tab[(tab["instance"] == s) & (tab["variant"] == m)]["cout_moyen"].iloc[0] for s in sizes]
        bars = ax.bar(x + (k - 1.5) * width, vals, width - 0.02, color=color, label=m)
        for b, v in zip(bars, vals):
            ax.annotate(f"{v:,.0f}".replace(",", " "), (b.get_x() + b.get_width() / 2, v),
                        xytext=(0, 2), textcoords="offset points", ha="center", fontsize=7, color=INK2)
    ax.set_yscale("log"); ax.set_xticks(x, [f"{s}\n({len(_instance(s).exams)} examens)" for s in sizes])
    ax.set_ylabel("coût moyen (échelle log)"); ax.grid(axis="x", visible=False)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    ax.set_title("E5 — Comparaison aux méthodes de référence (plus bas = meilleur)")
    fig.tight_layout(); fig.savefig(OUT / "E5_comparaison.png", dpi=160); plt.close(fig)
    return ("## E5 — Comparaison aux méthodes de référence\n\n![](E5_comparaison.png)\n\n"
            f"Budget de la recherche aléatoire = nombre moyen d'évaluations de l'AG : {budget}\n\n"
            + md_table(tab))


def e6() -> str:
    """Planning final : meilleure exécution de l'AG sur xlarge parmi celles d'E5 (ou une nouvelle)."""
    inst = _instance("xlarge")
    path = OUT / "E5_comparaison.csv"
    df = pd.read_csv(path) if path.exists() else pd.DataFrame()
    df = df[(df.get("variant") == "AG") & (df.get("instance") == "xlarge")] if len(df) else df
    if len(df):
        slots = json.loads(df.sort_values("cost").iloc[0]["slots"])
    else:
        slots = run_ga(inst, GAConfig(seed=1)).best_slots
    ev = evaluate(inst, slots)
    (OUT / "E6_planning_xlarge.xlsx").write_bytes(to_excel(inst, ev))

    # étudiants par créneau (jours × séances) — une seule teinte, clair → foncé
    students = np.zeros((len(inst.days), len(inst.periods)))
    for e in inst.exams:
        s = ev.schedule.slots[e.id]
        students[inst.day_of(s), inst.period_of(s)] += e.enrolled
    capacity = sum(r.capacity for r in inst.rooms)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("bleu", ["#eef4fc", "#86b6ef", "#2a78d6", "#104281"])
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"width_ratios": [1, 1.6]})
    im = ax1.imshow(students.T, cmap=cmap, vmin=0, vmax=capacity, aspect="auto")
    for d in range(len(inst.days)):
        for p in range(len(inst.periods)):
            v = students[d, p]
            ax1.text(d, p, f"{v:.0f}", ha="center", va="center", fontsize=8,
                     color="white" if v > capacity * 0.55 else INK)
    ax1.set_xticks(range(len(inst.days)), inst.days, rotation=45, ha="right")
    ax1.set_yticks(range(len(inst.periods)), inst.periods); ax1.grid(False)
    ax1.set_title(f"Étudiants par créneau (capacité {capacity})")
    fig.colorbar(im, ax=ax1, fraction=0.046)
    order = np.argsort(ev.schedule.duties)[::-1]
    duties = np.array(ev.schedule.duties)[order]
    maxd = np.array([inst.invigilators[i].max_duties for i in order])
    x = np.arange(len(order))
    ax2.bar(x, maxd, 0.8, color=GRID, label="maximum autorisé")
    ax2.bar(x, duties, 0.5, color=C[0], label="surveillances affectées")
    ax2.set_xticks([]); ax2.set_xlabel("surveillants (triés par charge)"); ax2.grid(axis="x", visible=False)
    ax2.set_title("Charge des surveillants"); ax2.legend(loc="upper right")
    fig.suptitle(f"E6 — Planning final xlarge : coût {ev.cost:.1f}, "
                 f"{ev.hard_total:.0f} violation dure")
    fig.tight_layout(); fig.savefig(OUT / "E6_planning.png", dpi=160); plt.close(fig)
    lines = [f"- **{k}** : {v:g}" for k, v in {**ev.hard, **ev.soft}.items()]
    return ("## E6 — Planning final (xlarge)\n\n![](E6_planning.png)\n\n"
            f"Coût {ev.cost:.1f} — classeur : `E6_planning_xlarge.xlsx`\n\n" + "\n".join(lines))


# =================================================================== main


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("which", nargs="*", default=["e1", "e2", "e3", "e4", "e5", "e6"])
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--quick", action="store_true", help="2 graines seulement (vérification)")
    parser.add_argument("--replot", action="store_true",
                        help="E2–E4 : retracer les figures à partir des fichiers sauvegardés, sans recalcul")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    seeds10, seeds5 = (2, 2) if args.quick else (10, 5)
    rp = args.replot
    runners = {"e1": lambda: e1(args.workers, seeds10), "e2": lambda: e2(args.workers, seeds5, rp),
               "e3": lambda: e3(args.workers, seeds5, rp), "e4": lambda: e4(args.workers, seeds5, rp),
               "e5": lambda: e5(args.workers, seeds10), "e6": e6}
    for name in args.which:
        t0 = time.perf_counter()
        print(f"\n=== {name.upper()} ===", flush=True)
        section = runners[name]()
        (OUT / f"{name.upper()}.md").write_text(section, encoding="utf-8")
        print(f"=== {name.upper()} terminé en {time.perf_counter() - t0:.0f} s", flush=True)
    parts = [p.read_text(encoding="utf-8") for k in ("E1", "E2", "E3", "E4", "E5", "E6")
             if (p := OUT / f"{k}.md").exists()]
    (OUT / "RESULTATS.md").write_text("# Résultats des expériences\n\n" + "\n\n".join(parts) + "\n",
                                      encoding="utf-8")


if __name__ == "__main__":
    main()
