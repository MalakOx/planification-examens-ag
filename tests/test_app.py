"""Test de fumée de l'interface Streamlit (sans navigateur)."""
from streamlit.testing.v1 import AppTest

from src.fitness import evaluate
from src.generator import generate
from src.report import invigilator_table, room_timetable, to_excel


def test_app_runs_ga_on_small_instance():
    at = AppTest.from_file("app.py", default_timeout=180).run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Vue d'ensemble", "Calendrier", "Analyse", "Ressources",
                                          "Historique", "Données"]
    at.sidebar.selectbox[0].select_index(0)  # petite instance
    at.sidebar.radio[0].set_value("Rapide")
    at.run()
    assert at.session_state["p_generations"] == 100  # le préréglage remplit les paramètres avancés
    at.sidebar.slider[1].set_value(20)  # 20 générations
    at.sidebar.button[0].click()
    at.run()
    assert not at.exception
    assert len(at.session_state["runs"]) == 1
    html = " ".join(m.value for m in at.markdown)
    assert "Planning valide" in html or "Planning non valide" in html  # verdict affiché
    assert 'class="cal"' in html  # calendrier rendu


def test_report_views_and_excel_export():
    inst = generate("small")
    ev = evaluate(inst, [e.id % inst.n_slots for e in inst.exams])
    assert room_timetable(inst, ev).shape == (inst.n_slots, len(inst.rooms))
    assert invigilator_table(inst, ev)["Surveillances"].sum() == sum(ev.schedule.duties)
    assert to_excel(inst, ev)[:2] == b"PK"  # fichier xlsx = archive zip
