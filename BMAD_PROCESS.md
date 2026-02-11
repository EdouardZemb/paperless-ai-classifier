# BMAD PROCESS — Autonomie cadrée

## Objectifs (actuels)
1) Stabiliser la review (compteur fiable + actions claires)
2) Gouvernance des suggestions (valider/rejeter + YAML)
3) Transparence UI (explication claire des actions)

> Un brief rapide est prévu régulièrement pour ajouter/affiner les objectifs.

## Horizon & cadence
- **Horizon** : continu
- **Cadence** : ~30 min / jour

## Mode d’exécution (autonome avec validation)
1. **Quick Spec** (BMAD)
2. **Stories** priorisées
3. **Implémentation par story** sur branche feature
4. **PR** ouverte + **DM Discord** pour validation
5. **Merge uniquement après validation**

## Règles de sécurité
- Pas de changements infra (Caddy/Docker/Secrets) sans accord explicite
- Pas de suppression de données
- PR obligatoire pour tout changement

## Definition of Done (DoD)
- Tests passés (unittest dashboard)
- UI cohérente
- Historique actions ok
- Documentation légère à jour

## Suivi
- Backlog : `BACKLOG.md`
- Quick Spec : `BMAD_QUICK_SPEC.md`
- PRs : GitHub
