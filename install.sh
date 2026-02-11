#!/bin/bash
# Installation automatique - Steps A & B
# Paperless + IA Classification locale

set -e

echo "🚀 Installation Paperless AI Classifier - Steps A & B"
echo "=================================================="

# Vérification des prérequis
echo "📋 Vérification des prérequis..."

# Docker (déjà installé pour Paperless)
if ! command -v docker &> /dev/null; then
    echo "❌ Docker non trouvé - requis pour Paperless"
    exit 1
fi

# Python 3
if ! command -v python3 &> /dev/null; then
    echo "📦 Installation de Python 3..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv
fi

# Step 1: Configuration de l'environnement Python
echo "🐍 Configuration environnement Python..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

# Dépendances Python
pip install \
    requests \
    PyYAML \
    pathlib \
    python-dateutil \
    watchdog \
    flask

echo "✅ Environnement Python configuré"

# Step 2: Installation d'Ollama (IA locale)
echo "🧠 Installation d'Ollama pour IA locale..."

if ! command -v ollama &> /dev/null; then
    echo "📦 Installation d'Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
else
    echo "✅ Ollama déjà installé"
fi

# Démarrage du service Ollama
echo "🔧 Configuration du service Ollama..."
sudo systemctl enable ollama || echo "Service ollama non disponible en systemd, démarrage manuel..."

# Démarrage d'Ollama en arrière-plan si pas déjà running
if ! pgrep -f "ollama serve" > /dev/null; then
    echo "🚀 Démarrage d'Ollama..."
    ollama serve &
    sleep 5
fi

# Step 3: Téléchargement du modèle IA (léger, local)
echo "📥 Téléchargement du modèle IA local (llama3.2:3b)..."
ollama pull llama3.2:3b

echo "✅ Modèle IA installé"

# Step 4: Configuration des permissions
echo "🔑 Configuration des permissions..."
chmod +x src/document_classifier.py
chmod +x webhook/paperless_webhook.py

# Step 5: Test de connectivité Paperless
echo "🔍 Test de connectivité Paperless..."
if curl -s http://localhost:8010/api/ > /dev/null; then
    echo "✅ Paperless accessible"
else
    echo "⚠️  Paperless non accessible sur localhost:8010"
    echo "   Vérifiez que Paperless est démarré avec:"
    echo "   cd /home/edouard/paperless && docker-compose up -d"
fi

# Step 6: Test de connectivité Ollama
echo "🔍 Test de connectivité Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "✅ Ollama accessible"
else
    echo "⚠️  Ollama non accessible sur localhost:11434"
    echo "   Le service sera démarré automatiquement"
fi

echo ""
echo "🎉 Installation terminée !"
echo "==============================================="
echo "Steps A & B complétés :"
echo "  ✅ Step A: Taxonomie neutre configurée"
echo "  ✅ Step B: Service IA local installé"
echo ""
echo "Prochaines étapes (Steps C & D) :"
echo "  🔄 Step C: Configuration seuils de confiance"
echo "  🧠 Step D: Boucle d'apprentissage continu"
echo ""
echo "Pour tester la classification :"
echo "  cd $(pwd)"
echo "  source venv/bin/activate"
echo "  python3 src/document_classifier.py"
echo ""
echo "Pour démarrer le webhook Paperless :"
echo "  python3 webhook/paperless_webhook.py"