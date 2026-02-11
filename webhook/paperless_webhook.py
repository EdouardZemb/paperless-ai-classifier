#!/usr/bin/env python3
"""
Paperless Webhook - Auto-classification
Écoute les nouveaux documents et déclenche la classification IA
Niveaux 1, 2, 3: Taxonomie enrichie, apprentissage, embeddings, règles métier
"""

from flask import Flask, request, jsonify
import requests
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Load environment variables from .env
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        # python-dotenv not available, read manually
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    value = value.strip()
                    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    os.environ[key.strip()] = value

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.document_classifier import PaperlessAIClassifier

app = Flask(__name__)

# Register dashboard blueprint (Steps C & D)
from dashboard import dashboard as dashboard_bp
app.register_blueprint(dashboard_bp)

# Configuration from environment or defaults
PAPERLESS_URL = os.getenv('PAPERLESS_URL', 'http://localhost:8010')
PAPERLESS_TOKEN = os.getenv('PAPERLESS_TOKEN', '')  # À configurer
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'paperless-ai-secret')

# Initialize classifier
classifier = PaperlessAIClassifier()

def get_paperless_headers():
    """Get headers for Paperless API calls"""
    headers = {
        'Content-Type': 'application/json'
    }
    
    if PAPERLESS_TOKEN:
        headers['Authorization'] = f'Token {PAPERLESS_TOKEN}'
    
    return headers

def get_document_content(document_id: int) -> str:
    """Fetch document content from Paperless API"""
    try:
        url = f"{PAPERLESS_URL}/api/documents/{document_id}/"
        response = requests.get(url, headers=get_paperless_headers())
        
        if response.status_code == 200:
            doc_data = response.json()
            content = doc_data.get('content', '')
            
            if not content:
                # Try to get OCR content
                content_url = f"{PAPERLESS_URL}/api/documents/{document_id}/content/"
                content_response = requests.get(content_url, headers=get_paperless_headers())
                if content_response.status_code == 200:
                    content = content_response.text
            
            return content
        else:
            classifier.logger.error(f"Failed to fetch document {document_id}: {response.status_code}")
            return ""
            
    except Exception as e:
        classifier.logger.error(f"Error fetching document {document_id}: {e}")
        return ""

def create_tag_if_needed(tag_name: str) -> Optional[int]:
    """Créer un tag dans Paperless s'il n'existe pas (Niveau 3)"""
    try:
        headers = get_paperless_headers()
        
        # Chercher le tag
        response = requests.get(
            f"{PAPERLESS_URL}/api/tags/?name={tag_name}",
            headers=headers
        )
        
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results:
                return results[0]['id']
        
        # Créer le tag s'il n'existe pas
        create_response = requests.post(
            f"{PAPERLESS_URL}/api/tags/",
            json={'name': tag_name},
            headers=headers
        )
        
        if create_response.status_code == 201:
            return create_response.json()['id']
        else:
            classifier.logger.warning(f"Failed to create tag '{tag_name}'")
            return None
            
    except Exception as e:
        classifier.logger.warning(f"Error managing tag '{tag_name}': {e}")
        return None

def create_document_type_if_needed(type_name: str) -> Optional[int]:
    """Créer un type de document dans Paperless s'il n'existe pas (Niveau 3)"""
    try:
        headers = get_paperless_headers()
        
        # Chercher le type
        response = requests.get(
            f"{PAPERLESS_URL}/api/document_types/?name={type_name}",
            headers=headers
        )
        
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results:
                return results[0]['id']
        
        # Créer le type s'il n'existe pas
        create_response = requests.post(
            f"{PAPERLESS_URL}/api/document_types/",
            json={'name': type_name},
            headers=headers
        )
        
        if create_response.status_code == 201:
            return create_response.json()['id']
        else:
            classifier.logger.warning(f"Failed to create document type '{type_name}'")
            return None
            
    except Exception as e:
        classifier.logger.warning(f"Error managing document type '{type_name}': {e}")
        return None

def apply_classification(document_id: int, classification: dict) -> bool:
    """Apply classification results to Paperless document (Niveaux 1-3)"""
    try:
        recommendation = classification.get('final_recommendation', {})
        
        if recommendation.get('action') == 'auto_classify':
            # Auto-apply classification
            update_data = {}
            doc_url = f"{PAPERLESS_URL}/api/documents/{document_id}/"
            
            # Get existing document data
            doc_response = requests.get(doc_url, headers=get_paperless_headers())
            if doc_response.status_code != 200:
                classifier.logger.error(f"Failed to fetch document {document_id}")
                return False
            
            doc_data = doc_response.json()
            existing_tags = doc_data.get('tags', [])
            
            # 1. Set title if suggested (Niveau 1)
            if recommendation.get('suggested_title'):
                update_data['title'] = recommendation['suggested_title']
            
            # 2. Créer et appliquer le type de document (Niveau 3)
            doc_type = recommendation.get('document_type')
            if doc_type:
                # Créer le type s'il n'existe pas
                type_id = create_document_type_if_needed(doc_type)
                if type_id:
                    update_data['document_type'] = type_id
            
            # 3. Set tags (Niveau 1)
            if recommendation.get('tags'):
                # Créer les tags s'ils n'existent pas et les ajouter
                tag_ids = []
                for tag_name in recommendation['tags']:
                    tag_id = create_tag_if_needed(tag_name)
                    if tag_id:
                        tag_ids.append(tag_id)
                
                # Merger avec les tags existants
                existing_tag_ids = doc_data.get('tags', [])
                all_tag_ids = list(set(existing_tag_ids + tag_ids))
                if all_tag_ids:
                    update_data['tags'] = all_tag_ids
            
            # Apply updates to Paperless
            if update_data:
                update_response = requests.patch(
                    doc_url, 
                    json=update_data,
                    headers=get_paperless_headers()
                )
                
                if update_response.status_code == 200:
                    classifier.logger.info(
                        f"Auto-classified document {document_id} as '{doc_type}' "
                        f"(confidence: {recommendation.get('confidence', 0):.2f})"
                    )
                    
                    # Générer et stocker embedding si disponible (Niveau 3)
                    try:
                        content = get_document_content(document_id)
                        embedding = classifier.generate_embedding(content)
                        if embedding:
                            classifier.store_embedding(document_id, embedding, classification)
                    except Exception as e:
                        classifier.logger.debug(f"Could not store embedding: {e}")
                    
                    return True
                else:
                    classifier.logger.error(f"Failed to update document {document_id}: {update_response.status_code}")
                    return False
        
        elif recommendation.get('action') == 'review_needed':
            # Add "needs_ai_review" tag for manual validation
            doc_url = f"{PAPERLESS_URL}/api/documents/{document_id}/"
            doc_response = requests.get(doc_url, headers=get_paperless_headers())
            
            if doc_response.status_code == 200:
                doc_data = doc_response.json()
                existing_tags = doc_data.get('tags', [])
                
                # Créer le tag s'il n'existe pas
                review_tag_id = create_tag_if_needed('needs_ai_review')
                
                if review_tag_id and review_tag_id not in existing_tags:
                    existing_tags.append(review_tag_id)
                    
                    update_response = requests.patch(
                        doc_url,
                        json={'tags': existing_tags},
                        headers=get_paperless_headers()
                    )
                    
                    classifier.logger.info(f"Marked document {document_id} for AI review")
                    return update_response.status_code == 200
        
        return True
        
    except Exception as e:
        classifier.logger.error(f"Error applying classification to document {document_id}: {e}")
        return False

@app.route('/webhook/paperless', methods=['POST'])
def paperless_webhook():
    """Handle Paperless webhook for new documents"""
    
    try:
        # Verify webhook secret (basic security)
        if request.headers.get('X-Webhook-Secret') != WEBHOOK_SECRET:
            return jsonify({'error': 'Invalid webhook secret'}), 403
        
        data = request.get_json()
        
        # Check if this is a document creation event
        if data.get('event') == 'document_created':
            document_id = data.get('document_id')
            
            if not document_id:
                return jsonify({'error': 'No document_id provided'}), 400
            
            classifier.logger.info(f"New document webhook received: {document_id}")
            
            # Give Paperless time to finish OCR processing
            import time
            time.sleep(2)
            
            # Fetch document content
            content = get_document_content(document_id)
            
            if content:
                # Process with AI classifier
                classification = classifier.process_document(document_id, content)
                
                # Apply classification if successful
                if 'error' not in classification:
                    success = apply_classification(document_id, classification)
                    
                    return jsonify({
                        'status': 'success',
                        'document_id': document_id,
                        'classification_applied': success,
                        'recommendation': classification.get('final_recommendation', {})
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'document_id': document_id,
                        'error': classification['error']
                    }), 500
            else:
                return jsonify({
                    'status': 'error',
                    'document_id': document_id,
                    'error': 'Could not fetch document content'
                }), 500
        
        else:
            # Ignore other webhook events
            return jsonify({'status': 'ignored', 'event': data.get('event')})
    
    except Exception as e:
        classifier.logger.error(f"Webhook error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'classifier': 'ready',
            'paperless_connection': check_paperless_connection(),
            'ollama_connection': check_ollama_connection()
        }
    })

def check_paperless_connection() -> str:
    """Check if Paperless is accessible"""
    try:
        response = requests.get(f"{PAPERLESS_URL}/api/", headers=get_paperless_headers(), timeout=5)
        return 'connected' if response.status_code == 200 else 'error'
    except:
        return 'disconnected'

def check_ollama_connection() -> str:
    """Check if Ollama is accessible"""
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        return 'connected' if response.status_code == 200 else 'error'
    except:
        return 'disconnected'

@app.route('/classify/<int:document_id>', methods=['POST'])
def manual_classify(document_id: int):
    """Manual classification endpoint for testing"""
    try:
        content = get_document_content(document_id)
        
        if content:
            classification = classifier.process_document(document_id, content)
            return jsonify(classification)
        else:
            return jsonify({'error': 'Could not fetch document content'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    """Get suggested document types (Niveau 2)"""
    try:
        suggestions_path = Path(__file__).parent.parent / "config" / "suggested_types.json"
        
        if not suggestions_path.exists():
            return jsonify({'suggestions': {}})
        
        with open(suggestions_path, 'r', encoding='utf-8') as f:
            suggestions = json.load(f)
        
        # Filtrer les suggestions non validées
        unvalidated = {k: v for k, v in suggestions.items() if not v.get('validated')}
        
        return jsonify({
            'total': len(unvalidated),
            'suggestions': unvalidated
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/suggestions/<type_name>/validate', methods=['POST'])
def validate_suggestion(type_name: str):
    """Validate and add a suggested type to taxonomy (Niveau 2)"""
    try:
        data = request.get_json()
        category = data.get('category')
        
        if not category:
            return jsonify({'error': 'Category required'}), 400
        
        # Validate and add the type
        success = classifier.validate_and_add_type(type_name, category)
        
        if success:
            classifier.logger.info(f"Suggestion '{type_name}' validated and added to category '{category}'")
            return jsonify({
                'status': 'success',
                'type': type_name,
                'category': category
            })
        else:
            return jsonify({'error': 'Failed to validate type'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/suggestions/<type_name>/reject', methods=['POST'])
def reject_suggestion(type_name: str):
    """Reject a suggested type (Niveau 2)"""
    try:
        suggestions_path = Path(__file__).parent.parent / "config" / "suggested_types.json"
        
        if not suggestions_path.exists():
            return jsonify({'error': 'No suggestions found'}), 404
        
        with open(suggestions_path, 'r', encoding='utf-8') as f:
            suggestions = json.load(f)
        
        if type_name not in suggestions:
            return jsonify({'error': 'Suggestion not found'}), 404
        
        # Marquer comme rejetée
        suggestions[type_name]['rejected'] = True
        suggestions[type_name]['rejected_at'] = datetime.now().isoformat()
        
        with open(suggestions_path, 'w', encoding='utf-8') as f:
            json.dump(suggestions, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'status': 'rejected',
            'type': type_name
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/embeddings/<int:document_id>', methods=['GET'])
def get_similar_documents(document_id: int):
    """Find similar documents based on embeddings (Niveau 3)"""
    try:
        embeddings_path = Path(__file__).parent.parent / "models" / "embeddings.json"
        
        if not embeddings_path.exists():
            return jsonify({'similar_documents': [], 'message': 'No embeddings available yet'})
        
        with open(embeddings_path, 'r', encoding='utf-8') as f:
            all_embeddings = json.load(f)
        
        # Chercher l'embedding du document
        doc_embedding = all_embeddings.get(str(document_id))
        if not doc_embedding:
            return jsonify({'error': 'Document embedding not found'}), 404
        
        # Trouver les documents similaires
        similar = classifier.find_similar_documents(doc_embedding['embedding'])
        
        return jsonify({
            'document_id': document_id,
            'similar_documents': similar,
            'threshold': 0.75
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Paperless AI Classifier Webhook")
    print(f"📋 Paperless URL: {PAPERLESS_URL}")
    print(f"🧠 Classifier ready")
    print(f"🔒 Webhook secret configured: {'Yes' if WEBHOOK_SECRET != 'paperless-ai-secret' else 'Using default (change recommended)'}")
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=5001,  # Port différent de Paperless
        debug=False
    )