# ✅ Checklist de validation (stabilisation)

> Objectif : vérifier rapidement que le workflow est stable après les changements.

## 1) Santé / Services
- [ ] `curl http://127.0.0.1:5001/health` retourne **healthy**
- [ ] Ollama est **connected**
- [ ] Paperless est **connected**

## 2) Dashboard (UI)
- [ ] `/dashboard` s'affiche
- [ ] `/dashboard/review` s'affiche
- [ ] `/dashboard/history` s'affiche
- [ ] `/dashboard/suggestions` s'affiche

## 3) Workflow “Review”
- [ ] Upload d’un document → action **review_needed**
- [ ] Boutons disponibles: **Valider / Corriger / Voir / Ignorer / Manuel**
- [ ] **Voir** ouvre Paperless en modal
- [ ] **Valider** applique le type dans Paperless
- [ ] **Corriger** applique le type corrigé dans Paperless
- [ ] Action visible dans `/dashboard/history`

## 4) Suggestions de types (Niveau 2)
- [ ] Un nouveau type est proposé (suggested_types.json)
- [ ] Validation via `/dashboard/suggestions` → le type est ajouté au YAML
- [ ] Rejet via `/dashboard/suggestions` → la suggestion est marquée rejetée

## 5) Logs & rotation
- [ ] `classifier.log` se remplit normalement
- [ ] Rotation automatique: `classifier.log.1`, `classifier.log.2` (max 5 fichiers)

---

### Commandes rapides
```bash
# Health
curl -s http://127.0.0.1:5001/health | python3 -m json.tool

# Pages
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/dashboard
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/dashboard/review
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/dashboard/history
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/dashboard/suggestions
```
