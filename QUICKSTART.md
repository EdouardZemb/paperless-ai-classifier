# QuickStart - Paperless AI Classifier Niveaux 1, 2, 3

## ⚡ 5 Minutes pour Démarrer

### 1️⃣ Installation Rapide

```bash
# Cloner / naviguer vers le projet
cd /home/edouard/paperless/ai-classifier

# Installer les dépendances
pip install -r requirements.txt

# Optionnel: Installer Flask pour le webhook
pip install flask

# Vérifier installation
python3 test_levels.py
```

### 2️⃣ Configuration (30 secondes)

```bash
# Copier la config .env
cp webhook/.env webhook/.env.local

# Éditer avec vos paramètres Paperless
nano webhook/.env
# → PAPERLESS_TOKEN=votre_token_ici
# → PAPERLESS_URL=http://127.0.0.1:8010 (par défaut)
```

### 3️⃣ Démarrer le Webhook

```bash
# Option A: Direct
cd webhook
python3 paperless_webhook.py

# Option B: Systemd (production)
sudo systemctl start paperless-ai-classifier
sudo systemctl status paperless-ai-classifier
```

### 4️⃣ Accéder au Dashboard

```bash
# Dashboard (Steps C & D)
open http://localhost:5001/dashboard

# Health check
curl http://localhost:5001/health
```

### 5️⃣ Tester avec un Document

```bash
# Accéder à Paperless
open http://localhost:8010

# Uploader un document (facture, attestation, etc.)
# Le webhook le classifiera automatiquement

# Ou classifier manuellement:
curl -X POST http://localhost:5001/classify/123
```

---

## 🎯 Exemples d'Utilisation par Niveau

### Niveau 1: Taxonomie Enrichie

**Document:** Facture électricité EDF

```text
FACTURE EDF
Date: 2024-02-15
Consommation: 250 kWh
Montant TTC: 75.50 €
```

**Classification (Niveau 1):**
```json
{
  "category": "administrative",      # Catégorie
  "document_type": "facture_énergie", # Type enrichi (NEW)
  "sub_type": null,
  "confidence": 0.90,
  "action": "auto_classify"
}
```

✅ Automatiquement appliqué à Paperless (titre + tags)

---

### Niveau 2: Auto-Discovery & Apprentissage

**Scenario:** Ollama détecte un type "renouvellement_assurance" qui n'existe pas

**1. Stockage de suggestion**
```bash
POST /api/suggestions
# → Crée entry dans config/suggested_types.json
{
  "renouvellement_assurance": {
    "suggested_at": "2024-02-11T10:00:00",
    "total_suggestions": 1,
    "examples": [...]
  }
}
```

**2. Dashboard affiche la suggestion**
```bash
GET /api/suggestions
# → Retourne suggestions non-validées
# → UI Dashboard montre "1 new type to review"
```

**3. Validation & Ajout**
```bash
POST /api/suggestions/renouvellement_assurance/validate
{"category": "administrative"}

# → Type ajouté automatiquement à base-taxonomy.yaml
# → Patterns basiques créés
# → Prêt à l'emploi!
```

**4. Apprentissage des Corrections**
```bash
# Document similaire arrive
# Classifier compare avec les corrigés passés
# Score augmente si ressemblance > 0.3
# Après 3 corrections → patterns renforcés auto
```

---

### Niveau 3: Règles Métier & Embeddings

#### Règle Métier: Détection RIB

**Document:**
```text
IDENTITÉ BANCAIRE
IBAN: FR7630001007941234567890123
BIC: SOFRFRPP
Domiciliation: CIC
```

**Classification (Niveau 3):**
```bash
# Évaluation règles AVANT patterns
# Règle "RIB Detection" matchée:
# - contains_all: ["IBAN", "BIC"] ✅
# - not_contains: ["solde", "opérations"] ✅
# → Applique règle avec confidence 0.95

{
  "category": "financial",
  "document_type": "relevé_identité_bancaire",
  "sub_type": "identite_bancaire",
  "confidence": 0.95,
  "action": "auto_classify",
  "origin": "rule"  # NEW - vient d'une règle!
}
```

#### Embeddings: Trouver Similaires

**Document uploadé:** Facture EDF (nouveau)

**1. Générer embedding**
```bash
POST /classify/125
# → Ollama génère embedding vector
# → Stocké dans models/embeddings.json
{
  "125": {
    "embedding": [0.12, 0.34, ..., 0.89],
    "type": "facture_énergie",
    "timestamp": "2024-02-11T10:00:00"
  }
}
```

**2. Trouver documents similaires**
```bash
GET /api/embeddings/125
# → Compare avec tous les embeddings passés
# → Similarité cosinus > 0.75
[
  {
    "document_id": 50,
    "similarity": 0.89,    # Très similaire!
    "type": "facture_énergie",
    "sub_type": "energy_bill"
  },
  {
    "document_id": 45,
    "similarity": 0.78,
    "type": "facture_énergie"
  }
]

# Si doc #50 a une correction passée, utiliser le boost!
```

---

## 📚 Commandes Essentielles

### Tests

```bash
# Test complet (Niveaux 1, 2, 3)
python3 test_levels.py
# → ✅ TOUS LES TESTS PASSÉS!

# Test spécifique
python3 -c "from src.document_classifier import PaperlessAIClassifier; c = PaperlessAIClassifier(); print(c.rules)"
```

### API Endpoints

```bash
# Health check
curl http://localhost:5001/health

# Classifier manuellement
curl -X POST http://localhost:5001/classify/123

# Dashboard
curl http://localhost:5001/dashboard

# Niveau 2: Suggestions
curl http://localhost:5001/api/suggestions
curl -X POST http://localhost:5001/api/suggestions/type_x/validate -d '{"category":"administrative"}'

# Niveau 3: Embeddings
curl http://localhost:5001/api/embeddings/123

# Steps C & D: Metrics
curl http://localhost:5001/api/metrics
```

### Monitoring

```bash
# Logs webhook
journalctl -u paperless-ai-classifier -f

# Logs classifier
tail -f classifier.log

# Classifications effectuées
tail -f models/classifications.jsonl

# Corrections appliquées
tail -f models/corrections.jsonl
```

---

## 🔧 Configuration Avancée

### Changer le Modèle Ollama

```bash
# webhook/.env
OLLAMA_MODEL=mistral:latest      # Plus rapide (5-10s)
# ou
OLLAMA_MODEL=neural-chat:7b      # Plus précis (15-20s)
# ou
OLLAMA_MODEL=llama2:13b          # Très précis (30-60s)

# Augmenter timeout si besoin
OLLAMA_TIMEOUT=180
```

### Personnaliser les Règles Métier

```yaml
# config/rules.yaml
rules:
  - name: "Mon Entreprise - Facture"
    description: "Détecte factures de mon entreprise"
    conditions:
      contains_all: ["Mon Entreprise", "facture"]
      not_contains: null
    result:
      type: "facture"
      sub_type: "facture_client"
      confidence: 0.98
```

### Activer/Désactiver les Embeddings

```bash
# webhook/.env
ENABLE_EMBEDDINGS=false    # Désactiver si pas assez de RAM
EMBEDDINGS_SIMILARITY_THRESHOLD=0.70  # Moins strict
```

---

## 🚀 Workflow Complet

```
Nouveau document uploadé à Paperless
         ↓
Webhook déclenché (document_created event)
         ↓
1. Évaluer règles métier (config/rules.yaml)
   → Si matchée: appliquer (confidence élevée)
         ↓
2. Détecter patterns (base-taxonomy.yaml)
   → Si matchés: scorer
         ↓
3. Charger corrections passées (Niveau 2)
   → Si similaire trouvée: boost score
         ↓
4. Appeler Ollama (IA locale)
   → Générer embedding (Niveau 3)
   → Analyser sémantique
         ↓
5. Combiner résultats
   → Calculer confiance finale
         ↓
6. Déterminer action
   - auto_classify (≥85%) → Appliquer automatiquement
   - review_needed (60-84%) → Tag needs_ai_review
   - manual (< 60%) → Manuel
         ↓
7. Appliquer à Paperless (Niveau 3)
   → Créer tags s'ils n'existent pas
   → Créer types s'ils n'existent pas
   → Appliquer titre + tags + type
         ↓
Document classifié! 🎉
```

---

## 💡 Tips & Tricks

### Tip 1: Améliorer Précision
```bash
# Avec corrections passées:
# - Corriger 3 documents du même type
# → Patterns auto-renforcés (Niveau 2)
# → Confiance augmente automatiquement

# Avec règles métier:
# - Ajouter règle précise pour votre cas
# → Confidence 0.95+
# → Auto-classement garanti
```

### Tip 2: Déboguer une Classification

```bash
# Activer logs verbeux
LOG_LEVEL=DEBUG

# Relancer et checker logs
journalctl -u paperless-ai-classifier -f

# Vérifier classification directement
curl -X POST http://localhost:5001/classify/DOC_ID | jq .
```

### Tip 3: Valider les Suggestions Rapidement

```bash
# Dashboard montre suggestions
# Cliquer "Validate" → auto-ajoute à taxonomie
# Instant impact sur prochains documents!
```

### Tip 4: Monitorer Performance

```bash
# Accéder à /api/metrics (Steps C & D)
curl http://localhost:5001/api/metrics | jq .

# Vérifie:
# - % auto_classify (cible: >70%)
# - % review_needed (cible: 15-25%)
# - Accuracy (cible: >90%)
# - Drift (cible: stable)
```

---

## ❌ Erreurs Courantes

| Erreur | Cause | Solution |
|--------|-------|----------|
| `ModuleNotFoundError: flask` | Dépendance manquante | `pip install flask` |
| `Timeout after 30s` | Ollama trop lent | `OLLAMA_TIMEOUT=180` |
| `Config not found` | Chemin incorrect | `ls config/base-taxonomy.yaml` |
| `Rules not loaded` | rules.yaml absent | Fichier créé auto, optionnel |
| `API 403 Forbidden` | Webhook secret incorrect | Vérifier `WEBHOOK_SECRET` |

---

## 📖 Prochaines Lectures

- **Détails:** [README.md](./README.md)
- **Changements:** [CHANGELOG.md](./CHANGELOG.md)
- **Upgrade:** [UPGRADE_GUIDE.md](./UPGRADE_GUIDE.md)
- **Code:** [src/document_classifier.py](./src/document_classifier.py)

---

## 🎉 Vous êtes Prêt!

Votre système de classification IA local est maintenant:

✅ **Intelligent** — 73 types, 3 niveaux, règles métier
✅ **Auto-apprenant** — Embeddings, corrections, suggestions
✅ **Performant** — 120s timeout, configurable
✅ **Intégré** — Crée tags & types auto dans Paperless
✅ **Privé** — 100% local, aucun cloud

Commencez par uploader vos premiers documents et regardez la magie opérer! 🚀
