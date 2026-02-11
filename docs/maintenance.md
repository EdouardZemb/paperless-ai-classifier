# Maintenance — Workflow quotidien

## Objectif
Exécuter un check quotidien léger + générer un rapport markdown.

## Script
```
./scripts/maintenance_check.sh
```

## Sortie
- Rapport dans `_bmad-output/implementation-artifacts/maintenance-report-YYYY-MM-DD.md`

## Contenu du rapport
- Health des services (Paperless / Ollama / Classifier)
- Compteurs (review pending, auto, manual)
- Suggestions en attente/validées/rejetées

## Automatisation
Cron installé (utilisateur):
- Daily: 08:30 → maintenance_check.sh
- Weekly (lundi): 08:45 → weekly_report.sh

Logs: /tmp/paperless-ai-maintenance.log et /tmp/paperless-ai-weekly.log
