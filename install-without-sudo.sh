#!/bin/bash
# Installation sans sudo - Steps A & B partiels
# Paperless + IA Classification locale (Ollama manuel)

set -e

echo "🚀 Installation Paperless AI Classifier - Steps A & B (sans Ollama)"
echo "================================================================"

# Vérification que l'environnement Python existe
if [ ! -f "venv/bin/activate" ]; then
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
else
    echo "✅ Environnement Python déjà configuré"
    source venv/bin/activate
fi

# Test des imports Python
echo "🔍 Test des dépendances Python..."
python3 -c "
import requests
import yaml
import json
import pathlib
from flask import Flask
print('✅ Toutes les dépendances Python OK')
"

# Test du classifier
echo "🧪 Test du classifier..."
python3 -c "
from src.document_classifier import PaperlessAIClassifier
classifier = PaperlessAIClassifier()
print('✅ Classifier chargé avec succès')
print(f'📊 Taxonomie: {len(classifier.document_types)} catégories')
"

# Configuration des permissions
echo "🔑 Configuration des permissions..."
chmod +x src/document_classifier.py
chmod +x webhook/paperless_webhook.py

# Test de connectivité Paperless
echo "🔍 Test de connectivité Paperless..."
if curl -s http://localhost:8010/api/ > /dev/null; then
    echo "✅ Paperless accessible"
else
    echo "⚠️  Paperless non accessible sur localhost:8010"
    echo "   Vérifiez que Paperless est démarré avec:"
    echo "   cd /home/edouard/paperless && docker-compose up -d"
fi

# Test de connectivité Ollama (optionnel)
echo "🔍 Test de connectivité Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "✅ Ollama accessible"
else
    echo "⚠️  Ollama non accessible - installation manuelle requise"
fi

echo ""
echo "🎉 Installation partielle terminée !"
echo "====================================="
echo "Steps A & B (partiel) complétés :"
echo "  ✅ Step A: Taxonomie neutre configurée"
echo "  ✅ Step B: Service IA local configuré (sans Ollama)"
echo ""
echo "❗ Installation manuelle requise pour Ollama:"
echo ""
echo "1. Installer Ollama (nécessite sudo):"
echo "   curl -fsSL https://ollama.ai/install.sh | sh"
echo ""
echo "2. Démarrer Ollama:"
echo "   ollama serve &"
echo ""
echo "3. Télécharger le modèle IA:"
echo "   ollama pull llama3.2:3b"
echo ""
echo "4. Relancer la configuration complète:"
echo "   ./configure-integration.sh"
echo ""
echo "Pour tester sans IA (mode pattern uniquement) :"
echo "  python3 src/document_classifier.py"
echo ""