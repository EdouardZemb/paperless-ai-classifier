# BMAD Quick Spec — Paperless AI Classifier

## Objectif
Stabiliser et clarifier le workflow de classification (auto/review/manuel), avec une interface transparente et un suivi fiable des actions.

## Périmètre
- Dashboard AI (UI + workflow)
- Gouvernance des suggestions de types
- Fiabilité des métriques / review queue
- GitFlow + discipline de livraison

## Hors périmètre (pour l’instant)
- Refonte complète de l’IA / modèle Ollama
- Auth avancée / SSO
- Multi‑tenants

## Priorités (P0/P1/P2)
**P0** — Transparence UI / contexte des actions
**P0** — Cohérence du compteur review vs liste réelle
**P1** — Gouvernance des suggestions (valider/rejeter + ajout YAML)

## Critères d’acceptation
- La page Review explique clairement chaque action et ses effets.
- Le compteur Review = nombre réel de documents en attente.
- Les suggestions sont validables/rejetables depuis l’UI et mises à jour dans la taxonomie.
- Toute action est historisée (actions.jsonl).

## Stories (Quick Flow)
1. **[P0] UI Transparence**
   - Ajout d’un bloc explicatif sur le workflow
   - Aide rapide sur la page Review
   - Validation: le contexte est compréhensible sans doc externe

2. **[P0] Review Queue fiable**
   - Compteur basé sur « pending only »
   - Validation: compteur = liste affichée

3. **[P1] Suggestions gouvernées**
   - Page /dashboard/suggestions (valider/rejeter)
   - Validation: type ajouté au YAML + pattern minimal

## Tests rapides
- `python3 -m unittest tests/test_dashboard.py`
- Vérifier /dashboard, /dashboard/review, /dashboard/history, /dashboard/suggestions
