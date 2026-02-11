# Guide d'Upgrade - Steps A-D → Niveaux 1, 2, 3

## 🎯 Objectif
Upgrader votre installation Paperless AI Classifier de la version précédente (Steps A-D) vers les Niveaux 1, 2, 3 sans perte de données.

## ✅ Bonnes Nouvelles
- **Aucune migration requise !** Tous les fichiers existants restent valides
- **Backward-compatible** : Les corrections et classifications existantes continuent de fonctionner
- **Incremental** : Vous pouvez activer les niveaux progressivement

## 🔄 Procédure d'Upgrade

### Étape 1: Sauvegarder votre Configuration Actuelle

```bash
cd /home/edouard/paperless/ai-classifier

# Créer un backup
mkdir -p backup/$(date +%Y-%m-%d)
cp config/base-taxonomy.yaml backup/$(date +%Y-%m-%d)/
cp models/classifications.jsonl backup/$(date +%Y-%m-%d)/ 2>/dev/null || true
cp models/corrections.jsonl backup/$(date +%Y-%m-%d)/ 2>/dev/null || true
cp webhook/.env backup/$(date +%Y-%m-%d)/ 2>/dev/null || true
```

### Étape 2: Mettre à Jour les Fichiers

#### Option A: Mise à jour Manuelle (Contrôle total)

```bash
# 1. Nouvelle taxonomie enrichie (73 types au lieu de 18)
# Les anciens types sont conservés, de nouveaux ajoutés
cp config/base-taxonomy.yaml config/base-taxonomy.yaml.old
# → base-taxonomy.yaml est déjà mis à jour avec enrichissements

# 2. Ajouter les règles métier (NEW)
cp config/rules.yaml .

# 3. Ajouter le .env avec variables (NEW)
cp webhook/.env webhook/.env.template
# → À customiser avec vos valeurs
```

#### Option B: Script d'Upgrade Automatique

```bash
#!/bin/bash
# install_levels.sh - Script d'upgrade automatique

set -e

echo "🔄 Upgrade Paperless AI Classifier → Niveaux 1, 2, 3"

# 1. Vérifier backup
if [ -f "models/classifications.jsonl" ]; then
    echo "💾 Backup des données existantes..."
    cp models/classifications.jsonl models/classifications.jsonl.bak
fi

if [ -f "models/corrections.jsonl" ]; then
    cp models/corrections.jsonl models/corrections.jsonl.bak
fi

# 2. Copier nouvelles resources
echo "📦 Installation des fichiers..."
cp config/base-taxonomy.yaml config/base-taxonomy.yaml  # Déjà enrichi
cp config/rules.yaml .                                   # NEW - Règles métier
cp webhook/.env webhook/.env                            # NEW - Config

# 3. Créer dossiers nécessaires
mkdir -p models
mkdir -p config
mkdir -p webhook

# 4. Installer dépendances
echo "📚 Installation des dépendances..."
pip install -r requirements.txt

# 5. Vérifier installation
echo "✅ Test de l'installation..."
python3 test_levels.py

echo "🎉 Upgrade terminé avec succès!"
echo ""
echo "Prochaines étapes:"
echo "1. Configurez webhook/.env avec vos paramètres Paperless"
echo "2. Testez: python3 test_levels.py"
echo "3. Redémarrez le service: systemctl restart paperless-ai-classifier"
```

### Étape 3: Configurer les Nouvelles Variables

#### .env - Ajouter les Variables de Configuration

```bash
# webhook/.env

# ─── Paperless (existant) ──────────────────────────────────
PAPERLESS_URL=http://127.0.0.1:8010
PAPERLESS_TOKEN=votre_token_ici
WEBHOOK_SECRET=votre_secret_ici

# ─── Ollama (existant, avec améliorations) ─────────────────
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b        # 🆕 Configurable!
OLLAMA_TIMEOUT=120               # 🆕 Augmenté de 30s

# ─── Niveaux 2-3 (NEW) ─────────────────────────────────────
ENABLE_EMBEDDINGS=true           # Niveau 3
EMBEDDINGS_SIMILARITY_THRESHOLD=0.75
PATTERN_REINFORCEMENT_THRESHOLD=3  # Niveau 2
```

#### rules.yaml - Nouvelles Règles Métier (Niveau 3)

Les règles pré-configurées dans `config/rules.yaml` incluent:
- ✅ RIB Detection (IBAN + BIC)
- ✅ Bank Statement (solde + mouvements)
- ✅ Payroll (salaire + cotisations)
- ✅ Energy Invoice (kWh + consommation)
- ✅ 7 autres...

**Aucune modification requise!** Utilisez les règles par défaut ou customisez:

```yaml
# config/rules.yaml
rules:
  - name: "Mon Entreprise"
    conditions:
      contains_all: ["Mon Entreprise", "facture"]
    result:
      type: "facture"
      confidence: 0.99
```

### Étape 4: Migrer les Données Existantes

#### Classifications.jsonl
```bash
# Vos classifications existantes sont déjà au bon format
# Aucune migration requise!

# Optionnel: Ré-classifier les anciens docs avec new patterns
python3 -c "
from src.document_classifier import PaperlessAIClassifier
classifier = PaperlessAIClassifier()
# ... code pour re-classifier si souhaité
"
```

#### Corrections.jsonl
```bash
# Vos corrections passées sont automatiquement chargées
# Elles sont utilisées pour booster les scores (Niveau 2)
# Aucune action requise!
```

### Étape 5: Tests et Validation

#### Test 1: Vérifier les Niveaux 1, 2, 3
```bash
python3 test_levels.py
# Résultat attendu: ✅ TOUS LES TESTS PASSÉS!
```

#### Test 2: Vérifier Backward Compatibility
```bash
# Test d'un document (comme avant)
curl -X POST http://localhost:5001/classify/123

# Résultat: Doit retourner classification avec:
# - category (NEW)
# - sub_type (NEW)
# - Tout le reste comme avant
```

#### Test 3: Tester les Nouveaux Endpoints
```bash
# Niveau 2: Suggestions
curl http://localhost:5001/api/suggestions

# Niveau 3: Embeddings
curl http://localhost:5001/api/embeddings/123
```

### Étape 6: Redémarrer le Service

```bash
# Arrêter le service actuel
systemctl stop paperless-ai-classifier

# Redémarrer avec nouvelle config
systemctl start paperless-ai-classifier

# Vérifier les logs
journalctl -u paperless-ai-classifier -f

# Attendu:
# - Config chargée
# - 73 types détectés
# - 11 règles chargées
# - Classifier ready
```

## 🎯 Étapes de Validation Post-Upgrade

### 1. Dashboard
```bash
# Accès au dashboard existant (Steps C & D toujours valides)
open http://localhost:5001/dashboard

# Doit afficher:
# - Métrics (inchangées)
# - Nouveau: suggestions (Niveau 2)
# - Nouveau: embeddings count (Niveau 3)
```

### 2. Classification d'un Document

```bash
# Document test (énergie)
curl -X POST http://localhost:5001/classify/123 \
  -H 'Content-Type: application/json'

# Résultat attendu (NEW):
{
  "final_recommendation": {
    "category": "administrative",           # NEW
    "document_type": "facture_énergie",     # NEW sous-type
    "sub_type": null,                       # NEW
    "confidence": 0.90,
    "action": "auto_classify"
  }
}
```

### 3. Règles Métier

```bash
# Document avec IBAN + BIC (teste règle)
curl -X POST http://localhost:5001/classify/124

# Résultat: doit matcher la règle "RIB Detection" (origin: rule)
```

### 4. Suggestions (Niveau 2)

```bash
# Vérifier suggestions (si Ollama détecte un type nouveau)
curl http://localhost:5001/api/suggestions

# Doit retourner suggestions en attente de validation
```

## ❌ Dépannage

### Problème: "ModuleNotFoundError: No module named 'flask'"
**Solution:**
```bash
pip install flask requests pyyaml python-dotenv
```

### Problème: "Ollama timeout"
**Solution:**
```bash
# Augmenter le timeout dans .env
OLLAMA_TIMEOUT=180  # ou plus selon votre modèle
```

### Problème: "Config not found"
**Solution:**
```bash
# Vérifier structure:
ls -la config/
ls -la webhook/.env
ls -la models/

# Créer si absent:
mkdir -p config models
```

### Problème: "Rules.yaml not found"
**Solution:**
```bash
# Les règles sont optionnelles. Si absent:
touch config/rules.yaml

# Ou copier l'exemple:
cp config/rules.yaml.template config/rules.yaml
```

## 📊 Avant/Après Upgrade

| Aspect | Avant (Steps A-D) | Après (Niveaux 1-3) |
|--------|-----------------|-------------------|
| Types | 18 | **73** |
| Niveaux classification | 1 | **3** |
| Patterns | 7 | **25+** |
| Timeout Ollama | 30s | **120s** |
| Règles métier | ❌ | **11** |
| Embeddings | ❌ | **✅** |
| Modèle configurable | ❌ | **✅** |
| Dashboard | ✅ | **✅** |
| Corrections | ✅ | **✅ + boost** |

## 🚀 Prochaines Étapes

Après upgrade, vous pouvez:

1. **Configurer votre modèle Ollama préféré**
   ```bash
   OLLAMA_MODEL=mistral:latest  # Plus rapide
   # ou
   OLLAMA_MODEL=neural-chat:7b  # Plus précis
   ```

2. **Ajouter vos propres règles métier**
   ```bash
   # Éditer config/rules.yaml avec vos règles
   ```

3. **Valider les suggestions détectées**
   ```bash
   POST /api/suggestions/mon_type/validate
   ```

4. **Monitorer les embeddings**
   ```bash
   curl http://localhost:5001/api/embeddings
   ```

## ✅ Checklist d'Upgrade

- [ ] Backup des données existantes
- [ ] Mise à jour des fichiers (base-taxonomy.yaml, rules.yaml)
- [ ] Configuration de .env (OLLAMA_MODEL, OLLAMA_TIMEOUT)
- [ ] Installation dépendances (pip install -r requirements.txt)
- [ ] Test d'intégration (python3 test_levels.py)
- [ ] Vérification backward compatibility
- [ ] Redémarrage du service
- [ ] Test d'un document real (vérifier category + sub_type)
- [ ] Vérification règles métier
- [ ] Vérification dashboard (Steps C & D)

---

## 🆘 Besoin d'Aide?

Consultez:
- `README.md` — Vue d'ensemble
- `CHANGELOG.md` — Détails des changements
- `test_levels.py` — Exemples d'utilisation
- Logs: `journalctl -u paperless-ai-classifier -f`

**Happy classifying! 🎉**
