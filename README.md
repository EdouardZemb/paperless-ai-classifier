# Paperless AI Classifier - Niveaux 1, 2, 3 ✅

[![BMAD Quick Flow](https://img.shields.io/badge/BMAD-Quick%20Flow-blue)](./BMAD_QUICK_SPEC.md)
[![GitFlow](https://img.shields.io/badge/GitFlow-enabled-brightgreen)](./CONTRIBUTING.md)

## 🎯 Objectif
Workflow IA local pour la classification automatique de documents dans Paperless-ngx avec apprentissage continu et validation humaine seulement en cas d'incertitude.

## 🚀 3 Niveaux d'Amélioration (Steps E, F, G)

### **Niveau 1 — Quick Wins** ✅
Amélioration immédiate sans refactorisation majeure:
- 📊 **Taxonomie enrichie** : 73 sous-types de documents (facture_énergie, relevé_compte, attestation_domicile, etc.)
- 🔍 **Patterns ultra-spécifiques** : 25+ patterns avec mots-clés discriminants (IBAN, BIC, RIB → identité bancaire, etc.)
- ⏱️ **Timeout Ollama** : Augmenté de 30s → 120s
- 🏛️ **Classification hiérarchique** : Retourne catégorie + sous-type (ex: `financial/relevé_identité_bancaire`)

### **Niveau 2 — Intelligence Artificielle** ✅
Apprentissage réel et adaptation dynamique:
- 🎯 **Auto-discovery** : Ollama détecte un type nouveau → stockage dans `suggested_types.json` → validation humaine → ajout auto à la taxonomie
- 🧠 **Apprentissage des corrections** : Les corrections passées alimentent les nouveaux scores (similarité document)
- ⚙️ **Modèle configurable** : Changer le modèle Ollama dans `.env` (`OLLAMA_MODEL=mistral:latest`)

### **Niveau 3 — Production-Ready** ✅
Déploiement professionnel et optimisation:
- 🔗 **Embeddings** : API Ollama `/api/embeddings` → similarité cosinus → détecte documents similaires + corrections passées
- 📋 **Règles métier** : `config/rules.yaml` avec conditions précises (ex: IBAN+BIC+pas solde = identité bancaire avec 95% confiance)
- 🔌 **Application Paperless** : Crée automatiquement tags et types si absents + applique via API (quand `auto_classify`)

---

## 📈 Nouvelles Fonctionnalités - Niveaux 1, 2, 3

### **Niveau 1: Taxonomie et Patterns Enrichis**
```yaml
# config/base-taxonomy.yaml - 73 types détaillés
administrative:
  - facture_énergie          # Électricité, gaz, eau
  - facture_télécoms         # Internet, mobile, etc.
  - attestation_domicile     # Preuve de domicile
  - attestation_employeur    # Contrat travail
  - attestation_sécu         # Affiliation sécurité sociale

financial:
  - relevé_identité_bancaire # IBAN, BIC, RIB
  - relevé_compte            # Solde, opérations
  - fiche_paie               # Bulletin salaire
  - avis_imposition          # Impôts
  # ... et 10 autres
```

### **Niveau 2: Auto-Discovery & Apprentissage**
```bash
# Suggestion de nouveau type
POST /api/suggestions/type_detect?confidence=0.75
# ↓ stocke dans config/suggested_types.json
# ↓ affichage dashboard pour validation

# Valider la suggestion
POST /api/suggestions/mon_nouveau_type/validate
{"category": "administrative"}
# ↓ ajoute auto à la taxonomie
```

### **Niveau 3: Règles Métier & Embeddings**
```yaml
# config/rules.yaml - règles métier avant patterns
rules:
  - name: "RIB Detection"
    conditions:
      contains_all: ["IBAN", "BIC"]
      not_contains: ["solde", "opérations"]
    result:
      type: "relevé_identité_bancaire"
      confidence: 0.95

# Embeddings stockés
models/embeddings.json
  "123": {
    "embedding": [0.1, 0.2, ...],
    "type": "facture",
    "similarity": 0.89
  }
```

---

## ✅ Steps A & B - État Actuel

### **Step A: Taxonomie Neutre** ✅
- 📁 **Configuration**: `config/base-taxonomy.yaml`
- 📊 **5 catégories** de documents : administrative, financial, personal, professional, legal
- 🏷️ **Tags automatiques** : urgency, status, period
- 🔍 **Patterns de détection** pour factures, contrats, attestations, relevés
- ⚖️ **Seuils de confiance** configurables (auto: ≥85%, review: 60-84%, manual: <60%)

### **Step B: Service IA Local** ✅
- 🐍 **Classifier Python** : `src/document_classifier.py`
- 🔗 **Webhook Paperless** : `webhook/paperless_webhook.py`
- 🧠 **IA hybride** : Patterns + Ollama (local)
- 📝 **Classification automatique** avec title, tags, organization
- 💾 **Stockage apprentissage** : `models/classifications.jsonl`

## 🚀 Fonctionnalités Opérationnelles

### Classification Hybride
- ✅ **Détection par patterns** (marche sans IA)
- ⏳ **IA locale Ollama** (nécessite installation manuelle)
- 🎯 **Scoring combiné** (patterns 40% + IA 60%)
- 📊 **Confiance mesurée** avec actions automatiques

### Intégration Paperless
- ✅ **API Paperless** connectée et testée
- 🔗 **Webhook endpoint** prêt (`/webhook/paperless`)
- 📋 **Health check** (`/health`)
- 🧪 **Classification manuelle** (`/classify/<doc_id>`)

## 📋 Test Réalisé
```bash
Document test: "FACTURE N° 2024-001, Montant TTC: 180.00 €"
Résultat: 
- Type: "facture" (90% confiance)
- Action: "auto_classify"  
- Titre: "Facture 15/02/2024"
- Tags: ["facture"]
```

## ⚠️ Installation Manuelle Requise

### Ollama (IA Locale)
```bash
# Installation (nécessite sudo)
curl -fsSL https://ollama.ai/install.sh | sh

# Démarrage
ollama serve &

# Modèle léger français/anglais
ollama pull llama3.2:3b
```

### Intégration Paperless
```bash
# Configuration finale
./configure-integration.sh

# Service systemd automatique
sudo systemctl enable paperless-ai-classifier
```

## ✅ Steps C & D - Dashboard & Apprentissage Continu

### **Step C: Interface de Configuration des Seuils** ✅
- 🌐 **Dashboard web** accessible sur `http://localhost:5001/dashboard`
- ⚙️ **Seuils globaux** modifiables (auto/review) via `/dashboard/thresholds`
- 🎯 **Seuils par catégorie** (overrides par type de document)
- 📊 **KPIs en temps réel** : taux auto/review/manual, précision, drift detection

### **Step D: Apprentissage Continu** ✅
- 📋 **Documents à revoir** : `/dashboard/review` — liste les docs en zone review
- ✏️ **Corrections humaines** : modifier le type détecté avec notes
- 🔄 **Renforcement patterns** : les corrections alimentent automatiquement les règles
- 📈 **Drift detection** : compare confiance récente (7j) vs historique
- 📝 **Historique corrections** : `/dashboard/corrections`
- 🔌 **API REST** : `/api/metrics`, `/api/thresholds`, `/api/correct`

## 📁 Structure des Fichiers
```
ai-classifier/
├── config/
│   └── base-taxonomy.yaml          # Step A - Taxonomie
├── src/
│   └── document_classifier.py      # Step B - Classifier
├── webhook/
│   ├── paperless_webhook.py        # Step B - Webhook + Blueprint registration
│   ├── dashboard.py                # Steps C & D - Dashboard & learning
│   └── .env                        # Configuration
├── models/
│   ├── classifications.jsonl       # Apprentissage
│   └── corrections.jsonl           # Corrections humaines (Step D)
├── install.sh                      # Installation complète
├── install-without-sudo.sh         # Installation partielle
└── configure-integration.sh        # Configuration finale
```

## 🔧 Configuration (Niveaux 1, 2, 3)

### Variables d'Environnement (.env)
```bash
# Paperless
PAPERLESS_URL=http://127.0.0.1:8010
PAPERLESS_TOKEN=your_token_here
WEBHOOK_SECRET=change-me-in-production

# Ollama (Niveau 1)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b            # Configurable! Peut être mistral, phi, etc.
OLLAMA_TIMEOUT=120                   # Augmenté de 30s pour modèles plus lents

# Embeddings (Niveau 3)
ENABLE_EMBEDDINGS=true
EMBEDDINGS_SIMILARITY_THRESHOLD=0.75

# Apprentissage (Niveau 2)
PATTERN_REINFORCEMENT_THRESHOLD=3    # Corrections avant renforcement pattern
```

## 🆕 Nouveaux Endpoints API (Niveaux 2, 3)

### Niveau 2: Auto-Discovery & Suggestions
```bash
# Lister les suggestions non validées
curl http://localhost:5001/api/suggestions

# Valider et ajouter une suggestion à la taxonomie
curl -X POST http://localhost:5001/api/suggestions/mon_type/validate \
  -H 'Content-Type: application/json' \
  -d '{"category": "administrative"}'

# Rejeter une suggestion
curl -X POST http://localhost:5001/api/suggestions/mon_type/reject
```

### Niveau 3: Embeddings & Similarité
```bash
# Trouver les documents similaires
curl http://localhost:5001/api/embeddings/123
# → retourne documents avec similarité cosinus > 0.75
```

## 🔧 Commandes Utiles

### Tests
```bash
# Test complet des Niveaux 1, 2, 3
python3 test_levels.py

# Test classifier seul
python3 src/document_classifier.py

# Tests dashboard (Steps C & D)
python -m pytest tests/test_dashboard.py -v

# Test health check
curl http://localhost:5001/health

# Classification manuelle
curl -X POST http://localhost:5001/classify/123

# Dashboard
open http://localhost:5001/dashboard

# API endpoints (Steps C & D)
curl http://localhost:5001/api/metrics
curl http://localhost:5001/api/thresholds
curl -X POST http://localhost:5001/api/correct -H 'Content-Type: application/json' -d '{"document_id":1,"corrected_type":"contrat"}'
```

### Logs & Monitoring
```bash
# Logs service
sudo journalctl -u paperless-ai-classifier -f

# Classifications effectuées
tail -f models/classifications.jsonl

# Logs classifier (rotation auto: 5 fichiers de 5MB)
tail -f classifier.log
ls -lh classifier.log*
```

## 🎉 Résumé Complet

### Steps A-D (Fondation)
✅ **Step A** : Taxonomie neutre + patterns de détection  
✅ **Step B** : Classifier IA hybride + webhook Paperless  
✅ **Step C** : Dashboard web + configuration seuils par catégorie  
✅ **Step D** : Apprentissage continu, corrections humaines, drift detection  

### Niveaux 1-3 (Évolutions)
✅ **Niveau 1** : Taxonomie enrichie (73 types), patterns discriminants, timeout 120s, classification hiérarchique  
✅ **Niveau 2** : Auto-discovery de types, apprentissage des corrections passées, modèle Ollama configurable  
✅ **Niveau 3** : Embeddings & similarité cosinus, règles métier (rules.yaml), création auto tags/types dans Paperless  

### Garanties
✅ **Privacy-first** : Tout tourne en local, aucun cloud  
✅ **Backward-compatible** : Ne casse pas l'existant (Steps A-D)  
✅ **Testable** : Suite complète de tests (test_levels.py + pytest)  
✅ **Bien documenté** : Code français commenté, README à jour  

**Toute la chaîne est opérationnelle ! Lancez le webhook et accédez au dashboard sur `/dashboard` 🚀**

---

## 📚 Documentation Technique

### Architecture Niveaux 1-3
1. **Règles métier** (Niveau 3) — évaluation première
2. **Patterns enrichis** (Niveau 1) — détection rapide
3. **Apprentissage** (Niveau 2) — boost scores si document similaire
4. **Ollama IA** — analyse sémantique (timeout 120s)
5. **Embeddings** (Niveau 3) — similarité avec documents passés

### Hiérarchie Classification
```python
# Retournée par classifier
{
  "category": "financial",           # Niveau 1
  "document_type": "facture_énergie", # Niveau 1
  "sub_type": "energy_bill",         # Niveau 1+
  "confidence": 0.90,                # Combinée
  "action": "auto_classify"          # Seuil ≥ 85%
}
```

### Flux Apprentissage (Niveau 2)
```
Document → Classification → Confiance basse?
                              ↓
                         Review manuelle
                              ↓
                         Correction stockée
                              ↓
                         3+ corrections même type?
                              ↓
                         Patterns renforcés automatiquement
```

## 🔮 Évolutions Futures
- [ ] Fine-tuning local Ollama sur documents d'Édouard
- [ ] Classification par OCR + analyse d'images
- [ ] Règles conditionnelles (if-then-else)
- [ ] Export/import taxonomie JSON
- [ ] UI de gestion des rules.yaml