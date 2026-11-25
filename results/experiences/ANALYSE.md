# Analyse des résultats (campagne du 2026-11-17)

Chiffres détaillés : [RESULTATS.md](RESULTATS.md). Coût = 1000 × violations dures + coût de confort (à minimiser).

## 1. L'AG trouve toujours un planning valide (E5)
- **100 % des exécutions de l'AG sont faisables** sur les 4 instances (40 exécutions), contre
  0 % pour l'aléatoire et 0 % pour la gloutonne sur small, medium et xlarge (surveillants manquants).
- À **budget égal** (même nombre d'évaluations), la recherche aléatoire n'est faisable que dans
  0 à 100 % des cas selon l'instance (xlarge : 0 %) et son coût moyen reste 1,8 à 3,8 fois
  supérieur à celui de l'AG → le gain vient bien de la recherche guidée (sélection + croisement),
  pas seulement du nombre d'essais.
- Coût moyen AG vs gloutonne : small 487 vs 4 548 · medium 492 vs 1 513 · large 612 vs 645 ·
  xlarge 688 vs 5 729. Sur large, où la gloutonne est déjà faisable, l'AG améliore encore le confort de 5 %.
- **Stabilité** : écart-type faible (0 sur small — les 10 exécutions trouvent le même coût 487,1,
  probablement l'optimum ; 3–12 sur les autres).

## 2. Convergence (E1)
- Avec réparation + initialisation gloutonne, le meilleur individu est faisable **dès la génération 0** ;
  la suite de la recherche améliore le confort (medium : ≈ 510 → 493 ; xlarge : ≈ 745 → 695).
- La moyenne de la population reste bien au-dessus du meilleur : la mutation et le croisement
  maintiennent de la **diversité** (pas de convergence prématurée).

## 3. Paramètres (E2, population initiale aléatoire)
- **Population** : 80 est le meilleur compromis (493) ; 20 donne des résultats plus variables (± 7) ;
  120 n'apporte rien de plus pour un temps 30 % plus long.
- **Mutation par gène** : plus elle est forte, plus le résultat se dégrade (0,1 → 507). Les valeurs
  faibles (0 à 0,01) sont les meilleures car la **mutation par échange** (p = 0,3) et la réparation
  apportent déjà la diversité nécessaire. Une mutation forte détruit les bonnes solutions.
- **Taux de croisement** : effet faible (490–493) ; sans croisement (0,0) la variabilité augmente (± 5).

## 4. Opérateurs (E3)
- **Sélection** : le tournoi est nettement meilleur que la roulette (490–500 vs 514). Avec des coûts
  proches (≈ 500), les fitness 1/(1+coût) sont presque égales et la roulette n'exerce
  presque **aucune pression de sélection**. Plus le tournoi est grand (k = 5), plus la pression est forte.
- **Croisement** : 1 point (489) ≈ 2 points (490) < uniforme (493). Les examens d'un même niveau
  sont **contigus** dans le chromosome : le croisement à 1 point transmet des blocs entiers
  (un niveau planifié de façon cohérente), le croisement uniforme les casse.

## 5. Apport de chaque composant (E4)
| Variante | medium | xlarge | 1re génération faisable |
|---|---|---|---|
| AG pur (aléatoire, sans réparation) | 515 | 783 | 11 / 15 |
| + réparation | 492 | 694 | 0 |
| + initialisation gloutonne | 496 | 730 | 0 |
| AG complet | 493 | 693 | 0 |
- L'**AG pur atteint la faisabilité seul** (en ~11–15 générations) : l'approche génétique fonctionne
  sans aide.
- La **réparation** est le composant le plus utile (−4 % sur medium, −11 % sur xlarge) mais elle
  coûte du temps (≈ 3× plus lent).
- L'**initialisation gloutonne** fait gagner du temps (faisable immédiatement, 3× plus rapide que
  la réparation) mais seule elle améliore moins.

## 6. Planning final (E6, xlarge)
Coût 666,8 : **aucune violation dure** ; 9 paires d'examens le même jour (sur 31 groupes),
charge des surveillants équilibrée (écart-type 1,7), quotas respectés.

## Réglage recommandé (issu des expériences)
tournoi k = 5, croisement 1 point, mutation par gène 0,01, échange 0,3, population 80, élitisme 2,
réparation + 20 % d'initialisation gloutonne.

**Validation** (5 exécutions, 200 générations, mêmes conditions qu'E1) :
| Instance | Réglage initial (E1) | Réglage recommandé |
|---|---|---|
| medium | 492,8 ± 3,4 — 22 s | 491,8 ± 2,8 — 9 s |
| xlarge | 694,6 ± 13,3 — 30 s | **675,0 ± 9,0 — 14 s** (meilleur 660,2) |

Le réglage issu des expériences est meilleur sur la grande instance (−2,8 %) et **deux fois plus
rapide** (mutation plus faible → plus d'individus déjà évalués, réutilisés via le cache).
