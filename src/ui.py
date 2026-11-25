"""Composants visuels HTML/CSS de l'interface Streamlit.

Les couleurs de texte sont héritées du thème Streamlit et les fonds sont des teintes
semi-transparentes : l'interface reste lisible en mode clair comme en mode sombre.
Les statuts (valide / non valide) ont toujours une icône et un libellé, jamais la couleur seule.
"""
from __future__ import annotations

from html import escape

from .fitness import SOFT_WEIGHTS, Evaluation
from .models import Exam, Instance

# Palette catégorielle validée, ordre fixe — une couleur par cycle d'études
CYCLES = [
    ("Licence LSI", "#2a78d6"),
    ("Licence LIG", "#eb6834"),
    ("Ingénieur", "#1baf7a"),
    ("Mastère", "#eda100"),
    ("Examens communs", "#e87ba4"),
]
CYCLE_COLOR = dict(CYCLES)
GOOD, CRITICAL = "#0ca30c", "#d03b3b"

DAY_NAMES = {"Lun": "Lundi", "Mar": "Mardi", "Mer": "Mercredi", "Jeu": "Jeudi", "Ven": "Vendredi",
             "Sam": "Samedi"}


# ------------------------------------------------------------------ formats


def fr(x: float, decimals: int = 1) -> str:
    """Nombre au format français : 1 234,5"""
    s = f"{x:,.{decimals}f}".replace(",", " ").replace(".", ",")
    return s


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def cycle_of(exam: Exam) -> str:
    code = exam.code
    if code.startswith("COM-") or "-TC-" in code:
        return "Examens communs"
    if "LSI" in code and code.startswith("L"):
        return "Licence LSI"
    if "LIG" in code:
        return "Licence LIG"
    if code.startswith("M"):
        return "Mastère"
    return "Ingénieur"


def day_label(day: str) -> tuple[str, str]:
    """'S1-Lun' -> ('Lundi', 'Semaine 1')"""
    week, d = day.split("-")
    return DAY_NAMES.get(d, d), f"Semaine {week[1:]}"


# ------------------------------------------------------------------ CSS

CSS = """
<style>
footer, [data-testid="stDecoration"], .stDeployButton {visibility: hidden; height: 0;}
.block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1400px;}
[data-testid="stSidebar"] h3 {font-size: 0.95rem; text-transform: uppercase; letter-spacing: .04em;
  opacity: .75; margin: 1.2rem 0 .2rem;}
.app-head {display:flex; align-items:flex-end; justify-content:space-between; gap:1rem; flex-wrap:wrap;
  border-bottom: 1px solid rgba(128,128,128,.25); padding-bottom: .8rem; margin-bottom: 1rem;}
.app-head h1 {font-size: 1.65rem; margin: 0; padding: 0; line-height: 1.2;}
.app-head .sub {opacity: .7; font-size: .92rem; margin-top: .25rem;}
.facts {display:flex; gap:.4rem; flex-wrap:wrap;}
.fact {border:1px solid rgba(128,128,128,.28); border-radius: 999px; padding:.15rem .7rem; font-size:.82rem;
  white-space:nowrap;}
.fact b {font-weight: 650;}
.banner {border-radius: 10px; padding: .9rem 1.1rem; margin: .2rem 0 1rem; display:flex; gap:.9rem;
  align-items:center;}
.banner .icon {font-size: 1.35rem; width: 2.1rem; height: 2.1rem; border-radius: 50%; display:flex;
  align-items:center; justify-content:center; color: white; flex: none; font-weight: 700;}
.banner .title {font-weight: 650; font-size: 1.05rem;}
.banner .detail {opacity: .8; font-size: .9rem; margin-top: .1rem;}
.kpis {display:grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap:.8rem; margin-bottom:1.2rem;}
.kpi {border:1px solid rgba(128,128,128,.22); border-radius: 10px; padding: .75rem .95rem;
  background: rgba(128,128,128,.04);}
.kpi .label {font-size: .8rem; opacity: .7;}
.kpi .value {font-size: 1.55rem; font-weight: 650; line-height: 1.25; margin-top: .15rem;}
.kpi .hint {font-size: .78rem; opacity: .65; margin-top: .1rem;}
.cards {display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: .9rem; margin: .4rem 0 1rem;}
.card {border:1px solid rgba(128,128,128,.22); border-radius: 10px; padding: 1rem 1.1rem;
  background: rgba(128,128,128,.04);}
.card .step {font-size:.75rem; font-weight:650; letter-spacing:.05em; text-transform:uppercase; color:#2a78d6;}
.card h4 {margin:.25rem 0 .4rem; font-size: 1.02rem; padding:0;}
.card p {font-size:.9rem; opacity:.85; margin:0;}
.checks {display:flex; flex-direction:column; gap:.35rem;}
.check {display:flex; gap:.6rem; align-items:baseline; font-size:.92rem;}
.check .mark {font-weight:700; width:1.1rem; flex:none;}
.check .num {margin-left:auto; opacity:.7; font-variant-numeric: tabular-nums; white-space:nowrap;}
.soft {display:grid; grid-template-columns: 1fr auto; gap:.15rem .8rem; font-size:.9rem; margin-bottom:.55rem;}
.soft .bar {grid-column: 1 / span 2; height: 6px; border-radius: 3px; background: rgba(128,128,128,.15);
  overflow:hidden;}
.soft .bar span {display:block; height:100%; border-radius:3px; background:#2a78d6;}
.soft .cost {opacity:.7; font-variant-numeric: tabular-nums;}
.legend {display:flex; gap:1rem; flex-wrap:wrap; font-size:.84rem; margin:.2rem 0 .6rem;}
.legend i {display:inline-block; width:.8rem; height:.8rem; border-radius:3px; margin-right:.35rem;
  vertical-align:-1px;}
.cal-wrap {overflow-x:auto; border:1px solid rgba(128,128,128,.22); border-radius:10px;}
table.cal {border-collapse:collapse; width:100%; table-layout:fixed; min-width: 900px; margin:0;}
table.cal th, table.cal td {border:1px solid rgba(128,128,128,.18); vertical-align:top; padding:.4rem;}
table.cal thead th {font-size:.85rem; font-weight:650; text-align:left; background: rgba(128,128,128,.06);}
table.cal thead th span {display:block; font-weight:400; opacity:.65; font-size:.75rem;}
table.cal tbody th {width:4.2rem; font-size:.85rem; font-weight:650; background: rgba(128,128,128,.06);}
table.cal td.empty {background: repeating-linear-gradient(45deg, transparent, transparent 6px,
  rgba(128,128,128,.05) 6px, rgba(128,128,128,.05) 12px);}
.chip {border-left:4px solid; border-radius:6px; padding:.3rem .45rem; margin-bottom:.35rem; font-size:.78rem;
  line-height:1.25; cursor: default;}
.chip b {display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
  font-weight:600; font-size:.8rem; margin-bottom:.1rem; overflow-wrap:anywhere; hyphens:auto;}
.chip span {opacity:.75;}
</style>
"""


# ------------------------------------------------------------------ blocs


def header(title: str, subtitle: str, facts: list[tuple[str, str]]) -> str:
    chips = "".join(f'<span class="fact"><b>{escape(v)}</b> {escape(k)}</span>' for k, v in facts)
    return (f'<div class="app-head"><div><h1>{escape(title)}</h1><div class="sub">{escape(subtitle)}</div>'
            f'</div><div class="facts">{chips}</div></div>')


def banner(ok: bool, title: str, detail: str) -> str:
    color = GOOD if ok else CRITICAL
    icon = "✓" if ok else "!"
    return (f'<div class="banner" style="background:{rgba(color, .09)};border:1px solid {rgba(color, .35)}">'
            f'<div class="icon" style="background:{color}">{icon}</div>'
            f'<div><div class="title">{escape(title)}</div><div class="detail">{escape(detail)}</div></div></div>')


def kpis(items: list[tuple[str, str, str]]) -> str:
    cells = "".join(f'<div class="kpi"><div class="label">{escape(l)}</div><div class="value">{escape(v)}</div>'
                    f'<div class="hint">{escape(h)}</div></div>' for l, v, h in items)
    return f'<div class="kpis">{cells}</div>'


def cards(items: list[tuple[str, str, str]]) -> str:
    cells = "".join(f'<div class="card"><div class="step">{escape(s)}</div><h4>{escape(t)}</h4>'
                    f'<p>{escape(p)}</p></div>' for s, t, p in items)
    return f'<div class="cards">{cells}</div>'


HARD_PLAIN = {
    "H1": "Aucun groupe n'a deux examens en même temps",
    "H2": "Chaque examen a assez de places",
    "H3": "Une salle n'accueille qu'un examen à la fois",
    "H4": "Aucun surveillant à deux endroits ni pendant une indisponibilité",
    "H5": "Chaque salle a son nombre de surveillants",
}


def hard_checklist(ev: Evaluation) -> str:
    rows = []
    for k, label in HARD_PLAIN.items():
        v = ev.hard[k]
        ok = v == 0
        mark = f'<span class="mark" style="color:{GOOD if ok else CRITICAL}">{"✓" if ok else "✕"}</span>'
        num = "respectée" if ok else f"{v:.0f} violation(s)"
        rows.append(f'<div class="check">{mark}<span>{escape(label)}</span><span class="num">{num}</span></div>')
    return f'<div class="checks">{"".join(rows)}</div>'


def soft_breakdown(ev: Evaluation) -> str:
    s = ev.soft
    texts = {
        "S1": f"{s['S1']:.0f} fois deux examens le même jour pour un groupe",
        "S2": f"{s['S2']:.0f} examens sur deux jours consécutifs",
        "S3": f"{s['S3']:.0f} jours de retard cumulés pour les gros examens",
        "S4": f"écart de {fr(s['S4'], 2)} surveillance entre enseignants (écart-type)",
        "S5": f"{s['S5']:.0f} places inoccupées dans les salles utilisées",
    }
    costs = {k: SOFT_WEIGHTS[k] * v for k, v in s.items()}
    total = sum(costs.values()) or 1.0
    rows = []
    for k in sorted(costs, key=costs.get, reverse=True):
        share = costs[k] / total * 100
        rows.append(f'<div class="soft"><span>{escape(texts[k])}</span><span class="cost">{fr(costs[k])}</span>'
                    f'<div class="bar"><span style="width:{share:.1f}%"></span></div></div>')
    return "".join(rows)


def legend() -> str:
    return '<div class="legend">' + "".join(
        f'<span><i style="background:{c}"></i>{escape(n)}</span>' for n, c in CYCLES) + "</div>"


def calendar(inst: Instance, ev: Evaluation, visible: set[int]) -> str:
    """Grille jours × séances ; une étiquette par examen visible, colorée par cycle.
    Le survol d'une étiquette affiche groupes, salles et surveillants."""
    sch = ev.schedule
    cells: dict[int, list[str]] = {s: [] for s in range(inst.n_slots)}
    for e in sorted(inst.exams, key=lambda e: -e.enrolled):
        if e.id not in visible:
            continue
        s = sch.slots[e.id]
        color = CYCLE_COLOR[cycle_of(e)]
        rooms = ", ".join(inst.rooms[r].name for r in sch.rooms[e.id])
        tip = (f"{e.name} ({e.code})\n{e.enrolled} étudiants\nGroupes : "
               f"{', '.join(inst.groups[g].name for g in e.groups)}\nSalles : {rooms}\nSurveillants : "
               f"{', '.join(inst.invigilators[i].name for i in sch.invigilators[e.id])}")
        cells[s].append(
            f'<div class="chip" style="border-color:{color};background:{rgba(color, .13)}" '
            f'title="{escape(tip).replace(chr(10), "&#10;")}"><b>{escape(e.name)}</b>'
            f'<span>{escape(e.code)} · {e.enrolled} étud.</span></div>')
    head = "".join(f"<th>{d}<span>{w}</span></th>" for d, w in (day_label(day) for day in inst.days))
    body = []
    for p, period in enumerate(inst.periods):
        tds = []
        for d in range(len(inst.days)):
            s = d * len(inst.periods) + p
            content = "".join(cells[s])
            tds.append(f'<td>{content}</td>' if content else '<td class="empty"></td>')
        body.append(f"<tr><th>{period}</th>{''.join(tds)}</tr>")
    return (f'<div class="cal-wrap" lang="fr"><table class="cal"><thead><tr><th></th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')
