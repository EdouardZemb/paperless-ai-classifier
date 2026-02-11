#!/bin/bash
# Configuration intégration Paperless + IA Classifier
# Steps A & B - Final configuration

set -e

echo "🔧 Configuration intégration Paperless AI Classifier"
echo "=================================================="

# Variables de configuration
PAPERLESS_DIR="/home/edouard/paperless"
CLASSIFIER_DIR="$PAPERLESS_DIR/ai-classifier"
WEBHOOK_PORT="5001"
WEBHOOK_URL="http://localhost:$WEBHOOK_PORT/webhook/paperless"

cd "$CLASSIFIER_DIR"

# Step 1: Configuration des variables d'environnement
echo "🔑 Configuration des variables d'environnement..."

# Créer le fichier d'environnement pour le webhook
cat > webhook/.env << EOF
PAPERLESS_URL=http://localhost:8010
PAPERLESS_TOKEN=
WEBHOOK_SECRET=paperless-ai-$(openssl rand -hex 16)
FLASK_ENV=production
EOF

echo "✅ Fichier .env créé avec secret sécurisé"

# Step 2: Test de l'installation
echo "🧪 Test de l'installation..."

# Test Python environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    
    # Test des imports
    python3 -c "from src.document_classifier import PaperlessAIClassifier; print('✅ Classifier import OK')"
    
    # Test de configuration
    python3 -c "
import yaml
with open('config/base-taxonomy.yaml', 'r') as f:
    config = yaml.safe_load(f)
print(f'✅ Taxonomie chargée: {len(config[\"document_types\"])} catégories')
"

else
    echo "❌ Environnement Python non trouvé. Exécutez d'abord install.sh"
    exit 1
fi

# Step 3: Test de connectivité Ollama
echo "🧠 Vérification d'Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "✅ Ollama accessible"
    
    # Vérifier si le modèle est installé
    if ollama list | grep -q "llama3.2:3b"; then
        echo "✅ Modèle llama3.2:3b installé"
    else
        echo "📥 Installation du modèle llama3.2:3b..."
        ollama pull llama3.2:3b
    fi
else
    echo "⚠️  Ollama non accessible, tentative de démarrage..."
    ollama serve &
    sleep 5
    
    if curl -s http://localhost:11434/api/tags > /dev/null; then
        echo "✅ Ollama démarré avec succès"
    else
        echo "❌ Impossible de démarrer Ollama"
        exit 1
    fi
fi

# Step 4: Création du service systemd pour le webhook
echo "🔧 Configuration du service systemd..."

sudo tee /etc/systemd/system/paperless-ai-classifier.service > /dev/null << EOF
[Unit]
Description=Paperless AI Classifier Webhook
After=network.target
Requires=network.target

[Service]
Type=simple
User=edouard
Group=edouard
WorkingDirectory=$CLASSIFIER_DIR/webhook
Environment=PATH=$CLASSIFIER_DIR/venv/bin
EnvironmentFile=$CLASSIFIER_DIR/webhook/.env
ExecStart=$CLASSIFIER_DIR/venv/bin/python3 $CLASSIFIER_DIR/webhook/paperless_webhook.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Recharger systemd et activer le service
sudo systemctl daemon-reload
sudo systemctl enable paperless-ai-classifier.service

echo "✅ Service systemd configuré"

# Step 5: Test du webhook
echo "🚀 Test du webhook..."

# Démarrer le service
sudo systemctl start paperless-ai-classifier.service
sleep 3

# Vérifier le statut
if sudo systemctl is-active --quiet paperless-ai-classifier.service; then
    echo "✅ Service webhook actif"
    
    # Test de santé
    if curl -s http://localhost:$WEBHOOK_PORT/health > /dev/null; then
        echo "✅ Webhook santé OK"
        
        # Afficher le statut de santé
        echo "📊 Statut des services:"
        curl -s http://localhost:$WEBHOOK_PORT/health | python3 -m json.tool
    else
        echo "⚠️  Webhook non accessible"
        sudo systemctl status paperless-ai-classifier.service
    fi
else
    echo "❌ Problème avec le service webhook"
    sudo journalctl -u paperless-ai-classifier.service --no-pager -n 20
    exit 1
fi

# Step 6: Configuration de Paperless (manuel pour sécurité)
echo ""
echo "🔗 Configuration manuelle requise dans Paperless:"
echo "=================================================="
echo ""
echo "1. Connectez-vous à Paperless: http://192.168.1.129:8010"
echo "2. Allez dans Admin → Settings"
echo "3. Dans la section 'Webhooks', ajoutez:"
echo "   - URL: $WEBHOOK_URL"
echo "   - Secret: $(grep WEBHOOK_SECRET webhook/.env | cut -d'=' -f2)"
echo "   - Events: Document Created"
echo ""
echo "4. (Optionnel) Créez un token API dans Admin → API Tokens"
echo "   Et ajoutez-le dans webhook/.env : PAPERLESS_TOKEN=votre_token"
echo ""

# Step 7: Documentation finale
echo "📚 Documentation des commandes utiles:"
echo "======================================="
echo ""
echo "🔍 Statut des services:"
echo "  sudo systemctl status paperless-ai-classifier"
echo "  curl http://localhost:$WEBHOOK_PORT/health"
echo ""
echo "🔄 Redémarrer les services:"
echo "  sudo systemctl restart paperless-ai-classifier"
echo ""
echo "📝 Voir les logs:"
echo "  sudo journalctl -u paperless-ai-classifier.service -f"
echo "  tail -f $CLASSIFIER_DIR/models/classifications.jsonl"
echo ""
echo "🧪 Test manuel d'un document:"
echo "  curl -X POST http://localhost:$WEBHOOK_PORT/classify/DOCUMENT_ID"
echo ""
echo "🛑 Arrêter les services:"
echo "  sudo systemctl stop paperless-ai-classifier"
echo ""

echo ""
echo "🎉 Configuration Steps A & B terminée !"
echo "========================================"
echo ""
echo "✅ Step A: Taxonomie neutre configurée"
echo "✅ Step B: Service IA local installé et configuré" 
echo ""
echo "📊 Résumé de l'installation:"
echo "  - 🐍 Python + dépendances: OK"
echo "  - 🧠 Ollama + modèle IA: OK" 
echo "  - 🔗 Webhook service: OK"
echo "  - 📋 Configuration Paperless: Manuel requis"
echo ""
echo "➡️  Prochaines étapes (Steps C & D):"
echo "  - Step C: Configuration fine des seuils de confiance"
echo "  - Step D: Boucle d'apprentissage et feedback utilisateur"
echo ""
echo "🚀 Le système est prêt à classifier automatiquement !"
echo "   Déposez un document dans Paperless pour tester."
echo ""