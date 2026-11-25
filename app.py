"""Interface Streamlit — Planification des examens de l'ISI par algorithme génétique.

Lancer : streamlit run app.py
Démonstration / captures : EXAM_APP_AUTORUN=medium streamlit run app.py  (lance une optimisation
au premier chargement avec le réglage « Équilibré »).
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from src import ui
from src.baseline import greedy_solution, random_solution
from src.fitness import evaluate
from src.ga import GAConfig, run_ga
from src.generator import generate
from src.models import Instance
from src.report import (constraints_table, invigilator_table, planning_table, room_timetable,
                        to_excel)

st.set_page_config(page_title="Planification des examens — ISI", page_icon="🗓️", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown(ui.CSS, unsafe_allow_html=True)

SIZE_LABELS = {"small": "Petite — 20 examens", "medium": "Moyenne — 34 examens",
               "large": "Grande — 48 examens", "xlarge": "Très grande — 58 examens"}

# Réglages issus des expériences E2–E3 : tournoi k = 5, croisement 1 point, mutation 0,01
_OPS = dict(selection="tournoi", tournament_k=5, crossover="1 point", crossover_rate=0.8,
            gene_mutation_rate=0.01, swap_rate=0.3, elitism=2, repair=True, greedy_init_ratio=0.2)
PRESETS = {
    "Rapide": dict(pop_size=40, generations=100, stagnation=40, **_OPS),
    "Équilibré": dict(pop_size=80, generations=200, stagnation=80, **_OPS),
    "Qualité max": dict(pop_size=120, generations=400, stagnation=150, **_OPS),
}
PRESET_HELP = {
    "Rapide": "40 individus, 100 générations — quelques secondes.",
    "Équilibré": "80 individus, 200 générations — le bon compromis.",
    "Qualité max": "120 individus, 400 générations — le meilleur planning, plus long.",
}

# ------------------------------------------------------------------ état de session
ss = st.session_state
ss.setdefault("runs", [])
ss.setdefault("current", None)
ss.setdefault("preset", "Équilibré")
for k, v in PRESETS[ss["preset"]].items():
    ss.setdefault(f"p_{k}", v)


def apply_preset() -> None:
    for k, v in PRESETS[ss["preset"]].items():
        ss[f"p_{k}"] = v


@st.cache_resource
def load_generated(size: str) -> Instance:
    return generate(size)


@st.cache_data(show_spinner=False)
def references(_inst: Instance, key: str) -> dict:
    """Coûts des méthodes de référence pour une instance (calculés une fois)."""
    greedy = evaluate(_inst, greedy_solution(_inst))
    rand = evaluate(_inst, random_solution(_inst, random.Random(0)))
    return {"greedy": greedy, "random": rand}


def convergence_chart(history: list[dict], greedy_cost: float, height: int = 300) -> alt.Chart:
    df = pd.DataFrame(history)[["generation", "best_cost", "mean_cost"]]
    df = df.rename(columns={"best_cost": "Meilleur planning", "mean_cost": "Moyenne de la population"})
    df = df.melt("generation", var_name="Série", value_name="Coût")
    colors = alt.Scale(domain=["Meilleur planning", "Moyenne de la population"], range=["#2a78d6", "#eb6834"])
    lo = min(df["Coût"].min(), greedy_cost) * 0.9
    hi = max(df["Coût"].max(), greedy_cost) * 1.1
    base = alt.Chart(df).encode(
        x=alt.X("generation:Q", title="Génération"),
        y=alt.Y("Coût:Q", title="Coût (échelle log)",
                scale=alt.Scale(type="log", domain=[lo, hi], nice=False),
                axis=alt.Axis(format="~s", tickCount=5)),
        color=alt.Color("Série:N", scale=colors, legend=alt.Legend(orient="top", title=None)),
    )
    hover = alt.selection_point(fields=["generation"], nearest=True, on="mouseover", empty=False)
    lines = base.mark_line(strokeWidth=2)
    points = base.mark_point(size=40, filled=True).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("generation:Q", title="Génération"), "Série:N",
                 alt.Tooltip("Coût:Q", format=",.1f")]).add_params(hover)
    rule = alt.Chart(pd.DataFrame({"Coût": [greedy_cost], "label": ["Heuristique gloutonne"]})).mark_rule(
        strokeDash=[6, 4], color="gray").encode(y="Coût:Q", tooltip="label:N")
    return (lines + points + rule).properties(height=height)


# ------------------------------------------------------------------ barre latérale
with st.sidebar:
    st.markdown("### Données")
    use_file = st.toggle("Importer ma propre instance (JSON)", value=False)
    if use_file:
        up = st.file_uploader("Fichier d'instance", type="json", label_visibility="collapsed",
                              help="Même format que les fichiers du dossier data/")
        if up is None:
            st.info("Choisissez un fichier JSON, ou désactivez l'import pour utiliser un jeu généré.")
            st.stop()
        inst = Instance.from_dict(json.load(up))
        instance_key, instance_label = f"file:{up.name}:{up.size}", up.name
    else:
        label = st.selectbox("Jeu de données", list(SIZE_LABELS.values()), index=1)
        size = next(k for k, v in SIZE_LABELS.items() if v == label)
        inst = load_generated(size)
        instance_key, instance_label = f"gen:{size}", SIZE_LABELS[size].split(" — ")[0]

    st.markdown("### Optimisation")
    st.radio("Réglage", list(PRESETS), key="preset", on_change=apply_preset, horizontal=True)
    st.caption(PRESET_HELP[ss["preset"]])
    with st.expander("Paramètres avancés"):
        st.slider("Taille de la population", 20, 200, step=10, key="p_pop_size")
        st.slider("Générations maximum", 20, 1000, step=20, key="p_generations")
        st.slider("Arrêt sans progrès après (générations)", 10, 300, step=10, key="p_stagnation")
        st.radio("Sélection", ["tournoi", "roulette"], horizontal=True, key="p_selection")
        if ss["p_selection"] == "tournoi":
            st.slider("Taille du tournoi", 2, 8, key="p_tournament_k")
        st.selectbox("Croisement", ["1 point", "2 points", "uniforme"], key="p_crossover")
        st.slider("Probabilité de croisement", 0.0, 1.0, step=0.05, key="p_crossover_rate")
        st.slider("Mutation : déplacer un examen", 0.0, 0.2, step=0.01, key="p_gene_mutation_rate")
        st.slider("Mutation : échanger deux examens", 0.0, 1.0, step=0.05, key="p_swap_rate")
        st.slider("Élitisme (meilleurs conservés)", 0, 10, key="p_elitism")
        st.toggle("Réparer les plannings non valides", key="p_repair")
        st.slider("Part de départ gloutonne", 0.0, 1.0, step=0.05, key="p_greedy_init_ratio")
        seed = st.number_input("Graine aléatoire", 0, 10_000, 1)
    launch = st.button("Lancer l'optimisation", type="primary", use_container_width=True)
    st.caption("Algorithme génétique · Techniques de Calcul Intelligent · ISI")

# ------------------------------------------------------------------ en-tête
st.markdown(ui.header(
    "Planification des examens",
    "Placement des examens, des salles et des surveillants par algorithme génétique",
    [("examens", str(len(inst.exams))), ("groupes", str(len(inst.groups))),
     ("créneaux", f"{inst.n_slots}"), ("salles", str(len(inst.rooms))),
     ("surveillants", str(len(inst.invigilators)))]), unsafe_allow_html=True)

refs = references(inst, instance_key)

# ------------------------------------------------------------------ exécution
autorun = os.environ.get("EXAM_APP_AUTORUN")
if autorun and not ss.get("autorun_done") and not use_file and autorun == size:
    ss["autorun_done"] = True
    launch = True

# L'emplacement de la progression existe à chaque exécution : s'il n'apparaissait que pendant un
# lancement, les onglets changeraient de position dans la page et Streamlit reviendrait au premier
# onglet à chaque changement de filtre.
box = st.empty()
if launch:
    cfg = GAConfig(seed=int(seed), **{k: ss[f"p_{k}"] for k in PRESETS["Rapide"]})
    with box.container():
        st.markdown("**Optimisation en cours…**")
        progress = st.progress(0.0)
        chart_box = st.empty()
    rows: list[dict] = []

    def on_generation(row: dict) -> None:
        rows.append(row)
        g = row["generation"]
        progress.progress(min(g / cfg.generations, 1.0),
                          text=f"Génération {g} / {cfg.generations} — meilleur coût {ui.fr(row['best_cost'])}")
        if g % 5 == 0:
            chart_box.altair_chart(convergence_chart(rows, refs["greedy"].cost, 220), use_container_width=True)

    res = run_ga(inst, cfg, on_generation=on_generation)
    box.empty()
    ss["runs"].append({"id": len(ss["runs"]) + 1, "time": datetime.now().strftime("%H:%M:%S"),
                       "key": instance_key, "instance": instance_label, "preset": ss["preset"],
                       "cfg": cfg, "res": res})
    ss["current"] = len(ss["runs"]) - 1

run = ss["runs"][ss["current"]] if ss["current"] is not None else None
if run and run["key"] != instance_key:
    same = [i for i, r in enumerate(ss["runs"]) if r["key"] == instance_key]
    run = ss["runs"][same[-1]] if same else None

tabs = st.tabs(["Vue d'ensemble", "Calendrier", "Analyse", "Ressources", "Historique", "Données"])
NEED_RUN = "Lancez une optimisation depuis le panneau de gauche pour afficher cette vue."

# ------------------------------------------------------------------ vue d'ensemble
with tabs[0]:
    if run is None:
        st.markdown(ui.cards([
            ("1 · Le problème", "Placer chaque examen sans conflit",
             f"{len(inst.exams)} examens à répartir sur {inst.n_slots} créneaux, avec des salles de "
             "capacité limitée et des surveillants disponibles seulement certains jours."),
            ("2 · La méthode", "Un algorithme génétique",
             "Chaque planning est un chromosome (un créneau par examen). Sélection, croisement et "
             "mutation font évoluer une population de plannings, génération après génération."),
            ("3 · Le résultat", "Un planning valide et confortable",
             "Aucune contrainte obligatoire violée, puis le moins possible d'examens rapprochés, "
             "de places perdues et de déséquilibre entre surveillants."),
        ]), unsafe_allow_html=True)
        st.info("Choisissez un réglage dans le panneau de gauche puis cliquez sur **Lancer l'optimisation**.")
    else:
        res, best = run["res"], run["res"].best
        greedy = refs["greedy"]
        n_hard_ok = sum(1 for v in best.hard.values() if v == 0)
        if best.feasible:
            st.markdown(ui.banner(True, "Planning valide : toutes les contraintes obligatoires sont respectées",
                                  f"{len(inst.exams)} examens placés sur {inst.n_slots} créneaux · "
                                  f"coût de confort {ui.fr(best.soft_cost)}"), unsafe_allow_html=True)
        else:
            st.markdown(ui.banner(False, f"Planning non valide : {best.hard_total:.0f} violation(s) obligatoire(s)",
                                  "Augmentez le nombre de générations ou activez la réparation."),
                        unsafe_allow_html=True)
        gain = (greedy.cost - best.cost) / greedy.cost * 100 if greedy.cost else 0.0
        st.markdown(ui.kpis([
            ("Contraintes obligatoires", f"{n_hard_ok} / 5", "respectées"),
            ("Coût du planning", ui.fr(best.cost), "plus bas = meilleur"),
            ("Écart avec la méthode gloutonne", f"−{ui.fr(gain, 0)} %" if gain >= 0 else f"+{ui.fr(-gain, 0)} %",
             f"gloutonne : {ui.fr(greedy.cost)}"),
            ("Temps de calcul", f"{ui.fr(res.seconds, 1)} s", f"{res.generations_run} générations"),
        ]), unsafe_allow_html=True)
        left, right = st.columns([1, 1], gap="large")
        with left:
            st.markdown("##### Contraintes obligatoires")
            st.markdown(ui.hard_checklist(best), unsafe_allow_html=True)
        with right:
            st.markdown("##### Ce qui reste à améliorer (coût de confort)")
            st.markdown(ui.soft_breakdown(best), unsafe_allow_html=True)
        st.download_button("Télécharger le planning (Excel)", to_excel(inst, best),
                           file_name=f"planning_examens_{inst.name}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           type="primary")

# ------------------------------------------------------------------ calendrier
with tabs[1]:
    if run is None:
        st.info(NEED_RUN)
    else:
        best = run["res"].best
        sch = best.schedule
        f1, f2, f3, f4 = st.columns(4)
        cycle = f1.selectbox("Cycle", ["Tous"] + [n for n, _ in ui.CYCLES])
        group = f2.selectbox("Groupe", ["Tous"] + [g.name for g in inst.groups])
        room = f3.selectbox("Salle", ["Toutes"] + [r.name for r in inst.rooms])
        inv = f4.selectbox("Surveillant", ["Tous"] + sorted(i.name for i in inst.invigilators))
        gid = next((g.id for g in inst.groups if g.name == group), None)
        rid = next((r.id for r in inst.rooms if r.name == room), None)
        iid = next((i.id for i in inst.invigilators if i.name == inv), None)
        visible = {e.id for e in inst.exams
                   if cycle in ("Tous", ui.cycle_of(e))
                   and (gid is None or gid in e.groups)
                   and (rid is None or rid in sch.rooms[e.id])
                   and (iid is None or iid in sch.invigilators[e.id])}
        st.markdown(ui.legend(), unsafe_allow_html=True)
        st.caption(f"{len(visible)} examen(s) affiché(s) sur {len(inst.exams)} · survolez une étiquette "
                   "pour voir les groupes, les salles et les surveillants.")
        st.markdown(ui.calendar(inst, best, visible), unsafe_allow_html=True)
        with st.expander("Planning détaillé (tableau)"):
            st.dataframe(planning_table(inst, best), hide_index=True, use_container_width=True)

# ------------------------------------------------------------------ analyse
with tabs[2]:
    if run is None:
        st.info(NEED_RUN)
    else:
        res, best = run["res"], run["res"].best
        c1, c2 = st.columns([3, 2], gap="large")
        with c1:
            st.markdown("##### Convergence de l'algorithme")
            st.altair_chart(convergence_chart(res.history, refs["greedy"].cost), use_container_width=True)
            st.caption("Le meilleur planning ne se dégrade jamais (élitisme) ; l'écart avec la moyenne "
                       "montre la diversité conservée dans la population. Pointillés : méthode gloutonne.")
        with c2:
            st.markdown("##### Comparaison des méthodes")
            comp = pd.DataFrame([
                {"Méthode": n, "Coût": ui.fr(ev.cost),
                 "vs AG": "—" if ev is best else f"× {ui.fr(ev.cost / best.cost, 1)}",
                 "Violations": int(ev.hard_total)}
                for n, ev in (("Aléatoire", refs["random"]), ("Gloutonne", refs["greedy"]),
                              ("Algorithme génétique", best))])
            st.dataframe(comp, hide_index=True, use_container_width=True)
            st.caption("Aléatoire : un créneau tiré au hasard par examen. Gloutonne : les examens les plus "
                       "contraints placés en premier, chacun dans le meilleur créneau du moment.")
        with st.expander("Détail technique des contraintes et des poids"):
            st.dataframe(constraints_table(best), hide_index=True, use_container_width=True)
            st.json(run["cfg"].__dict__, expanded=False)

# ------------------------------------------------------------------ ressources
with tabs[3]:
    if run is None:
        st.info(NEED_RUN)
    else:
        best = run["res"].best
        inv_df = invigilator_table(inst, best)
        st.markdown("##### Charge des surveillants")
        chart_df = inv_df.assign(Reste=inv_df["Maximum"] - inv_df["Surveillances"])
        st.altair_chart(alt.Chart(chart_df).transform_fold(
            ["Surveillances", "Reste"], as_=["Mesure", "Nombre"]).mark_bar(cornerRadiusEnd=3).encode(
            x=alt.X("Surveillant:N", sort=alt.EncodingSortField("Surveillances", order="descending"),
                    title=None, axis=alt.Axis(labels=False, ticks=False)),
            y=alt.Y("Nombre:Q", title="Surveillances", stack="zero"),
            color=alt.Color("Mesure:N", scale=alt.Scale(domain=["Surveillances", "Reste"],
                                                        range=["#2a78d6", "#d5dbe3"]),
                            legend=alt.Legend(orient="top", title=None,
                                              labelExpr="datum.label == 'Reste' ? 'Quota restant' : 'Surveillances affectées'")),
            tooltip=["Surveillant", "Surveillances", "Maximum"],
        ).properties(height=240), use_container_width=True)
        st.dataframe(inv_df, hide_index=True, use_container_width=True)
        st.markdown("##### Occupation des salles")
        rt = room_timetable(inst, best)
        st.dataframe(rt.style.map(lambda v: f"background-color: {ui.rgba('#2a78d6', .16)}" if v else ""),
                     use_container_width=True, height=min(38 * (len(rt) + 1), 600))

# ------------------------------------------------------------------ historique
with tabs[4]:
    if not ss["runs"]:
        st.info("Aucun lancement pour l'instant. Chaque optimisation s'ajoute ici pour pouvoir les comparer.")
    else:
        hist = pd.DataFrame([{
            "N°": r["id"], "Heure": r["time"], "Instance": r["instance"], "Réglage": r["preset"],
            "Population": r["cfg"].pop_size, "Sélection": r["cfg"].selection,
            "Croisement": r["cfg"].crossover, "Mutation": r["cfg"].gene_mutation_rate,
            "Réparation": "oui" if r["cfg"].repair else "non",
            "Coût": round(r["res"].best.cost, 1), "Violations": int(r["res"].best.hard_total),
            "Durée (s)": round(r["res"].seconds, 1)} for r in ss["runs"]])
        st.dataframe(hist, hide_index=True, use_container_width=True)
        same = [i for i, r in enumerate(ss["runs"]) if r["key"] == instance_key]
        if same:
            choice = st.selectbox("Afficher le lancement", same[::-1],
                                  format_func=lambda i: f"N° {ss['runs'][i]['id']} — {ss['runs'][i]['time']} — "
                                                        f"coût {ui.fr(ss['runs'][i]['res'].best.cost)}",
                                  index=same[::-1].index(ss["current"]) if ss["current"] in same else 0)
            if choice != ss["current"]:
                ss["current"] = choice
                st.rerun()

# ------------------------------------------------------------------ données
with tabs[5]:
    st.markdown("##### Examens")
    st.dataframe(pd.DataFrame([{"Code": e.code, "Matière": e.name, "Cycle": ui.cycle_of(e),
                                "Inscrits": e.enrolled,
                                "Groupes": ", ".join(inst.groups[g].name for g in e.groups)}
                               for e in inst.exams]), hide_index=True, use_container_width=True)
    a, b = st.columns(2, gap="large")
    a.markdown("##### Salles")
    a.dataframe(pd.DataFrame([{"Salle": r.name, "Type": r.kind, "Capacité": r.capacity,
                               "Surveillants requis": r.invigilators_needed} for r in inst.rooms]),
                hide_index=True, use_container_width=True)
    b.markdown("##### Groupes")
    b.dataframe(pd.DataFrame([{"Groupe": g.name, "Effectif": g.size} for g in inst.groups]),
                hide_index=True, use_container_width=True)
    st.markdown("##### Surveillants")
    st.dataframe(pd.DataFrame([{"Surveillant": i.name, "Maximum": i.max_duties,
                                "Indisponible": ", ".join(inst.slot_label(s) for s in sorted(i.unavailable))}
                               for i in inst.invigilators]), hide_index=True, use_container_width=True)
    st.download_button("Télécharger l'instance (JSON)", json.dumps(inst.to_dict(), ensure_ascii=False, indent=1),
                       file_name=f"{inst.name}.json", mime="application/json")
