# Planification des examens de l'ISI par algorithme génétique

Projet de TP — Techniques de Calcul Intelligent (approche AG).

## Installation
```
pip install -r requirements.txt
```

## Lancer
| Commande | Rôle |
|---|---|
| `streamlit run app.py` | **interface** : choix des données, réglage de l'AG, courbe en direct, planning, export Excel |
| `python -m src.generator` | génère les jeux de données `data/small.json`, `medium.json`, `large.json` |
| `python run_baselines.py` | évalue les méthodes de référence (aléatoire, gloutonne) → `results/` |
| `python run_ga.py medium` | lance l'AG (small, medium, large, xlarge) → courbe + planning dans `results/` |
| `python -m pytest` | lance les tests |
| `python -m src.experiments` | campagne d'expériences E1 à E6 → `results/experiences/` |

## Organisation du code
| Fichier | Contenu |
|---|---|
| `src/models.py` | salles, groupes, examens, surveillants, instance (JSON) |
| `src/generator.py` | jeux de données synthétiques inspirés de l'ISI |
| `src/decoder.py` | chromosome (créneau par examen) → salles + surveillants |
| `src/fitness.py` | contraintes dures H1–H5, souples S1–S5, coût |
| `src/baseline.py` | solution aléatoire et heuristique gloutonne |
| `src/operators.py` | sélection, croisements, mutations, réparation |
| `src/ga.py` | boucle de l'algorithme génétique (`GAConfig`, `run_ga`) |
| `src/report.py` | tableaux du planning (pandas) |
