"""Mise en forme d'un planning évalué (tableaux pandas), réutilisée par la
démo console, l'interface Streamlit et le rapport."""
from __future__ import annotations

import io

import pandas as pd

from .fitness import HARD_LABELS, SOFT_LABELS, SOFT_WEIGHTS, W_HARD, Evaluation
from .models import Instance


def planning_table(inst: Instance, ev: Evaluation) -> pd.DataFrame:
    """Une ligne par examen, triée par créneau."""
    sch = ev.schedule
    rows = []
    for e in inst.exams:
        s = sch.slots[e.id]
        rows.append({
            "Créneau": s,
            "Jour": inst.days[inst.day_of(s)],
            "Séance": inst.periods[inst.period_of(s)],
            "Code": e.code,
            "Examen": e.name,
            "Groupes": ", ".join(inst.groups[g].name for g in e.groups),
            "Inscrits": e.enrolled,
            "Salles": ", ".join(inst.rooms[r].name for r in sch.rooms[e.id]),
            "Places": sum(inst.rooms[r].capacity for r in sch.rooms[e.id]),
            "Surveillants": ", ".join(inst.invigilators[i].name for i in sch.invigilators[e.id]),
            "Sans place": sch.unseated[e.id],
            "Surv. manquants": sch.missing_invigilators[e.id],
        })
    return pd.DataFrame(rows).sort_values(["Créneau", "Code"]).reset_index(drop=True)


def grid_table(inst: Instance, ev: Evaluation) -> pd.DataFrame:
    """Vue calendrier : jours en lignes, séances en colonnes, codes d'examens dans les cases."""
    grid = {p: ["" for _ in inst.days] for p in inst.periods}
    for e in inst.exams:
        s = ev.schedule.slots[e.id]
        cell = grid[inst.periods[inst.period_of(s)]][inst.day_of(s)]
        grid[inst.periods[inst.period_of(s)]][inst.day_of(s)] = (cell + " · " if cell else "") + e.code
    return pd.DataFrame(grid, index=inst.days)


def constraints_table(ev: Evaluation) -> pd.DataFrame:
    rows = [{"Contrainte": k, "Type": "dure", "Libellé": HARD_LABELS[k], "Valeur": v,
             "Poids": W_HARD, "Coût": W_HARD * v} for k, v in ev.hard.items()]
    rows += [{"Contrainte": k, "Type": "souple", "Libellé": SOFT_LABELS[k], "Valeur": v,
              "Poids": SOFT_WEIGHTS[k], "Coût": round(SOFT_WEIGHTS[k] * v, 2)} for k, v in ev.soft.items()]
    return pd.DataFrame(rows)


def room_timetable(inst: Instance, ev: Evaluation) -> pd.DataFrame:
    """Occupation des salles : une ligne par créneau, une colonne par salle."""
    data = {r.name: ["" for _ in range(inst.n_slots)] for r in inst.rooms}
    for e in inst.exams:
        s = ev.schedule.slots[e.id]
        for rid in ev.schedule.rooms[e.id]:
            data[inst.rooms[rid].name][s] = e.code
    return pd.DataFrame(data, index=[inst.slot_label(s) for s in range(inst.n_slots)])


def invigilator_table(inst: Instance, ev: Evaluation) -> pd.DataFrame:
    """Charge de chaque surveillant et créneaux où il surveille."""
    where: dict[int, list[tuple[int, str]]] = {i.id: [] for i in inst.invigilators}
    for e in inst.exams:
        s = ev.schedule.slots[e.id]
        for i in ev.schedule.invigilators[e.id]:
            where[i].append((s, e.code))
    rows = [{"Surveillant": inv.name,
             "Surveillances": ev.schedule.duties[inv.id],
             "Maximum": inv.max_duties,
             "Indisponibilités": len(inv.unavailable),
             "Créneaux": " ; ".join(f"{inst.slot_label(s)} ({c})" for s, c in sorted(where[inv.id]))}
            for inv in inst.invigilators]
    return pd.DataFrame(rows).sort_values("Surveillances", ascending=False).reset_index(drop=True)


def to_excel(inst: Instance, ev: Evaluation) -> bytes:
    """Classeur Excel : calendrier, planning détaillé, salles, surveillants, contraintes."""
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    # dans le classeur, un examen par ligne dans chaque case du calendrier
    calendar = grid_table(inst, ev).apply(lambda col: col.str.replace(" · ", "\n", regex=False))
    calendar.index.name = "Jour"
    sheets = [("Calendrier", calendar, True), ("Planning", planning_table(inst, ev), False),
              ("Salles", room_timetable(inst, ev), True),
              ("Surveillants", invigilator_table(inst, ev), False),
              ("Contraintes", constraints_table(ev), False)]
    head_fill = PatternFill("solid", fgColor="DCE8F8")
    thin = Side(style="thin", color="C9CED6")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df, with_index in sheets:
            df.to_excel(xw, sheet_name=name, index=with_index)
            ws = xw.sheets[name]
            for row in ws.iter_rows():
                for cell in row:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
                    cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.fill = head_fill
            for k, col in enumerate(ws.columns, 1):
                longest = max(max((len(line) for line in str(c.value or "").split("\n")), default=0)
                              for c in col)
                ws.column_dimensions[get_column_letter(k)].width = min(max(10, longest + 2), 55)
            ws.freeze_panes = "B2" if with_index else "A2"
            ws.page_setup.orientation = "landscape"
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 0
            ws.sheet_properties.pageSetUpPr.fitToPage = True
    return buf.getvalue()


def group_timetable(inst: Instance, ev: Evaluation, group_id: int) -> pd.DataFrame:
    rows = [{"Jour": inst.days[inst.day_of(ev.schedule.slots[e.id])],
             "Séance": inst.periods[inst.period_of(ev.schedule.slots[e.id])],
             "Créneau": ev.schedule.slots[e.id], "Examen": e.name, "Code": e.code}
            for e in inst.exams if group_id in e.groups]
    return pd.DataFrame(rows).sort_values("Créneau").drop(columns="Créneau").reset_index(drop=True)
