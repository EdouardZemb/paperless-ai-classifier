# Validation PR — format standard (Discord)

## Template
**[VALIDATION] PR #<num> — <titre>**
- ✅ **Résumé** : 2–3 puces
- 🧪 **Tests** : commande(s) exécutée(s) ou N/A
- ⚠️ **Risques** : None / Low / Medium / High

**Répondre :**
- **ALLOW** → merge
- **DISMISS** → pas de merge

---

## Exemple
**[VALIDATION] PR #12 — feat: add suggestions workflow**
- ✅ Ajout page suggestions + validation YAML
- ✅ Ajout tests review
- 🧪 `python3 -m unittest tests/test_dashboard.py`
- ⚠️ Risque: Low

Répondre: **ALLOW** / **DISMISS**
