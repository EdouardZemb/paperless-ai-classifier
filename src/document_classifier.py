#!/usr/bin/env python3
"""
Paperless Document Classifier - Niveaux 1, 2, 3
Service IA local pour classification automatique des documents
Support de la classification hiérarchique, apprentissage continu, et règles métier
"""

import requests
import yaml
import json
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from logging.handlers import RotatingFileHandler
from collections import defaultdict

class PaperlessAIClassifier:
    def __init__(self, config_path: str = None):
        """Initialize the classifier with taxonomy configuration"""
        if config_path is None:
            # Default to config in parent directory or current directory structure
            script_dir = Path(__file__).parent
            config_path = script_dir.parent / "config" / "base-taxonomy.yaml"
        
        self.config_path = Path(config_path)
        self.load_config()
        self.setup_logging()
        
        # Configuration from environment or defaults
        self.paperless_url = os.getenv('PAPERLESS_URL', "http://localhost:8010")
        self.ollama_url = os.getenv('OLLAMA_URL', "http://localhost:11434")
        self.ollama_model = os.getenv('OLLAMA_MODEL', "llama3.2:3b")  # Configurable model
        self.ollama_timeout = int(os.getenv('OLLAMA_TIMEOUT', "120"))  # 120s par défaut (augmenté)
        self.paperless_token = os.getenv('PAPERLESS_TOKEN', '')
        
        # Charger les corrections passées pour l'apprentissage (Niveau 2)
        self.past_corrections = self._load_corrections()
        self.past_classifications = self._load_classifications()
        
        # Charger les règles métier si disponibles (Niveau 3)
        self.rules = self._load_rules()
        
    def load_config(self):
        """Load taxonomy configuration"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            self.document_types = self.config['document_types']
            self.auto_tags = self.config['auto_tags']
            self.patterns = self.config['detection_patterns']
            self.thresholds = self.config['confidence_thresholds']
            
        except Exception as e:
            raise ValueError(f"Failed to load config: {e}")
    
    def _load_corrections(self) -> List[Dict]:
        """Charger les corrections passées pour l'apprentissage (Niveau 2)"""
        corrections_path = self.config_path.parent.parent / "models" / "corrections.jsonl"
        corrections = []
        if corrections_path.exists():
            try:
                with open(corrections_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                corrections.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass
            except Exception as e:
                self.logger.warning(f"Failed to load corrections: {e}")
        return corrections
    
    def _load_classifications(self) -> List[Dict]:
        """Charger les classifications passées pour analyse"""
        classifications_path = self.config_path.parent.parent / "models" / "classifications.jsonl"
        classifications = []
        if classifications_path.exists():
            try:
                with open(classifications_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                classifications.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass
            except Exception as e:
                self.logger.warning(f"Failed to load classifications: {e}")
        return classifications
    
    def _load_rules(self) -> Dict:
        """Charger les règles métier configurables (Niveau 3)"""
        rules_path = self.config_path.parent / "rules.yaml"
        if rules_path.exists():
            try:
                with open(rules_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    return config.get('rules', [])
            except Exception as e:
                self.logger.warning(f"Failed to load rules: {e}")
        return []
    
    def setup_logging(self):
        """Setup logging for the classifier"""
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        log_file = os.getenv('LOG_FILE', 'classifier.log')

        logger = logging.getLogger('PaperlessClassifier')
        logger.setLevel(getattr(logging, log_level, logging.INFO))

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Avoid duplicate handlers if already configured
        if not logger.handlers:
            file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5)
            file_handler.setFormatter(formatter)

            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)

            logger.addHandler(file_handler)
            logger.addHandler(stream_handler)

        self.logger = logger
    
    def analyze_document_text(self, text: str) -> Dict:
        """
        Analyze document text using local AI
        Hiérarchie d'évaluation:
        1. Règles métier (Niveau 3)
        2. Patterns enrichis (Niveau 1)
        3. AI Ollama avec corrections passées (Niveaux 2-3)
        """
        
        # 1. Évaluer les règles métier (Niveau 3)
        rule_match = self._evaluate_rules(text)
        
        # 2. Pattern-based pre-classification
        pattern_matches = self._detect_patterns(text)
        
        # 3. AI-enhanced analysis using Ollama
        ai_analysis = self._ollama_classify(text)
        
        # 4. Appliquer les corrections passées (Niveau 2)
        ai_analysis = self._apply_learned_corrections(text, ai_analysis)
        
        # 5. Combine results with confidence scoring
        classification = self._combine_results(pattern_matches, ai_analysis, text, rule_match)
        
        return classification
    
    def _evaluate_rules(self, text: str) -> Optional[Dict]:
        """
        Évaluer les règles métier avant patterns et IA (Niveau 3)
        Les règles sont des conditions précises qui ont haute confiance
        """
        text_lower = text.lower()
        
        for rule in self.rules:
            name = rule.get('name', 'unnamed')
            conditions = rule.get('conditions', {})
            result = rule.get('result', {})
            
            # Évaluer les conditions
            all_conditions_met = True
            
            # contains_all: tous ces mots doivent être présents
            contains_all = conditions.get('contains_all', [])
            if contains_all:
                for keyword in contains_all:
                    if keyword.lower() not in text_lower:
                        all_conditions_met = False
                        break
            
            # not_contains: aucun de ces mots ne doit être présent
            if all_conditions_met:
                not_contains = conditions.get('not_contains', [])
                for keyword in not_contains:
                    if keyword.lower() in text_lower:
                        all_conditions_met = False
                        break
            
            # min_confidence: score de confiance minimum
            if all_conditions_met:
                min_conf = conditions.get('min_confidence', 0)
                # Pour l'instant, on assume toujours 1.0 pour les règles
            
            # Si règle validée, retourner le résultat avec haute confiance
            if all_conditions_met:
                self.logger.info(f"Rule matched: {name}")
                return {
                    'rule_name': name,
                    'document_type': result.get('type'),
                    'sub_type': result.get('sub_type'),
                    'confidence': result.get('confidence', 0.95),
                    'method': 'rule'
                }
        
        return None
    
    def _apply_learned_corrections(self, text: str, ai_analysis: Dict) -> Dict:
        """
        Appliquer l'apprentissage des corrections passées (Niveau 2)
        Si un document ressemble à un déjà corrigé, augmenter le score
        """
        if not self.past_corrections:
            return ai_analysis
        
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))
        
        # Compter les mots-clés communs avec les corrections passées
        correction_scores = defaultdict(float)
        
        for correction in self.past_corrections:
            corrected_type = correction.get('corrected_type', '')
            # On assume que des mots-clés similaires → document similaire
            # Score = nombre de mots communs / nombre total de mots
            
            # En production, on utiliserait des embeddings (Niveau 3)
            # Pour l'instant, pattern simple
            if 'document_text' in correction:
                correction_words = set(re.findall(r'\b\w+\b', correction['document_text'].lower()))
                common_words = words & correction_words
                if common_words:
                    similarity = len(common_words) / max(len(words), len(correction_words))
                    # Si similarité > 0.3, considérer comme signal
                    if similarity > 0.3:
                        correction_scores[corrected_type] += similarity
        
        # Ajuster le score IA si une correction similaire existe
        if correction_scores:
            best_correction_type = max(correction_scores, key=correction_scores.get)
            boost = min(0.15, correction_scores[best_correction_type])  # Boost max 15%
            
            # Si l'IA a proposé un type différent, augmenter le score de celui corrigé
            if ai_analysis.get('document_type') != best_correction_type:
                # Créer une entrée pour le type corrigé
                if 'alternative_types' not in ai_analysis:
                    ai_analysis['alternative_types'] = []
                
                ai_analysis['alternative_types'].append({
                    'type': best_correction_type,
                    'confidence': ai_analysis.get('confidence', 0.5) + boost,
                    'reason': 'learned_from_corrections'
                })
        
        return ai_analysis
    
    def _detect_patterns(self, text: str) -> Dict:
        """Pattern-based document detection - Enrichis avec sous-types"""
        matches = {}
        text_lower = text.lower()
        
        for doc_type, patterns in self.patterns['document_identifiers'].items():
            match_count = 0
            matched_patterns = []
            
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    match_count += 1
                    matched_patterns.append(pattern)
            
            if match_count > 0:
                # Score ajusté: plus de patterns = plus de confiance
                confidence = min(0.9, match_count * 0.25)
                matches[doc_type] = {
                    'confidence': confidence,
                    'matches': match_count,
                    'matched_patterns': matched_patterns,
                    'method': 'pattern'
                }
        
        return matches
    
    def _ollama_classify(self, text: str) -> Dict:
        """Use Ollama for AI-enhanced classification (Niveaux 1-3)"""
        try:
            # Construct prompt for document classification
            # Version enrichie demandant aussi des sous-types
            prompt = f"""Analyse ce document et détermine:

1. Catégorie principale (administrative, financial, personal, professional, legal)
2. Type de document spécifique (facture, contrat, attestation, relevé, etc.)
3. Sous-type si applicable (ex: facture_énergie, relevé_compte, attestation_domicile)
4. Organisme probable (ne devine pas, uniquement si évident dans le texte)
5. Confiance (0.0-1.0)
6. Tags pertinents
7. Titre suggéré normalisé

Document:
{text[:2000]}

Réponds en JSON valide, sans balisage markdown:
{{
  "category": "administrative|financial|personal|professional|legal",
  "document_type": "type_détecté",
  "sub_type": "sous_type_si_applicable_sinon_null",
  "confidence": 0.0-1.0,
  "organization": "nom_si_évident_sinon_null",
  "suggested_title": "titre_normalisé",
  "tags": ["tag1", "tag2"],
  "reasoning": "explication_courte"
}}"""

            # Call Ollama API avec timeout configurable
            self.logger.info(f"Calling Ollama ({self.ollama_model}) with timeout {self.ollama_timeout}s")
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,  # Modèle configurable
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=self.ollama_timeout  # Timeout augmenté à 120s
            )
            
            if response.status_code == 200:
                result = response.json()
                try:
                    ai_result = json.loads(result.get('response', '{}'))
                    return ai_result
                except json.JSONDecodeError:
                    self.logger.warning("Failed to parse AI response as JSON")
                    return {}
            else:
                self.logger.warning(f"Ollama request failed: {response.status_code}")
                return {}
                
        except requests.exceptions.Timeout:
            self.logger.error(f"Ollama timeout after {self.ollama_timeout}s - model may be too large")
            return {}
        except Exception as e:
            self.logger.warning(f"AI classification failed: {e}")
            return {}
    
    def _combine_results(self, pattern_matches: Dict, ai_analysis: Dict, text: str, rule_match: Optional[Dict] = None) -> Dict:
        """
        Combine pattern, AI, and rule results with confidence scoring
        Priorité: Règles > Patterns > IA
        Support classification hiérarchique (catégorie/sous-type)
        """
        
        final_classification = {
            'timestamp': datetime.now().isoformat(),
            'method': 'hybrid',
            'pattern_matches': pattern_matches,
            'ai_analysis': ai_analysis,
            'rule_match': rule_match,
            'final_recommendation': {}
        }
        
        # 1. Si règle matchée, utiliser celle-ci (priorité maximale)
        if rule_match:
            recommendation = {
                'category': None,  # À déterminer
                'document_type': rule_match['document_type'],
                'sub_type': rule_match.get('sub_type'),
                'confidence': rule_match['confidence'],
                'organization': ai_analysis.get('organization'),
                'suggested_title': ai_analysis.get('suggested_title', self._generate_title(text, rule_match['document_type'])),
                'tags': self._suggest_tags(text, rule_match['document_type'], ai_analysis.get('tags', [])),
                'action': self._determine_action(rule_match['confidence']),
                'origin': 'rule'
            }
            final_classification['final_recommendation'] = recommendation
            return final_classification
        
        # 2. Déterminer le meilleur type (patterns vs IA)
        best_type = None
        best_confidence = 0
        best_method = None
        best_sub_type = None
        
        # Check pattern matches
        for doc_type, data in pattern_matches.items():
            if data['confidence'] > best_confidence:
                best_type = doc_type
                best_confidence = data['confidence']
                best_method = 'pattern'
        
        # Enhance with AI if available and confident
        if ai_analysis.get('document_type') and ai_analysis.get('confidence', 0) > 0.6:
            ai_confidence = ai_analysis['confidence']
            
            # Weight combination: pattern 40%, AI 60%
            combined_confidence = (best_confidence * 0.4) + (ai_confidence * 0.6)
            
            if combined_confidence > best_confidence or not best_type:
                best_type = ai_analysis['document_type']
                best_confidence = ai_confidence
                best_method = 'ai'
                best_sub_type = ai_analysis.get('sub_type')  # Récupérer le sous-type de l'IA
        
        # Déterminer la catégorie (si sous-type fourni)
        category = ai_analysis.get('category')
        if not category and best_type:
            # Trouver la catégorie du type détecté
            category = self._find_category_for_type(best_type)
        
        # Build final recommendation avec classification hiérarchique
        recommendation = {
            'category': category,
            'document_type': best_type,
            'sub_type': best_sub_type,
            'confidence': best_confidence,
            'organization': ai_analysis.get('organization'),
            'suggested_title': ai_analysis.get('suggested_title', self._generate_title(text, best_type)),
            'tags': self._suggest_tags(text, best_type, ai_analysis.get('tags', [])),
            'action': self._determine_action(best_confidence),
            'origin': best_method
        }
        
        final_classification['final_recommendation'] = recommendation
        return final_classification
    
    def _find_category_for_type(self, doc_type: str) -> Optional[str]:
        """Trouver la catégorie d'un type de document"""
        for category, types in self.document_types.items():
            if doc_type in types:
                return category
        return None
    
    def _generate_title(self, text: str, doc_type: str) -> str:
        """Generate a normalized title based on document content"""
        # Extract date if possible
        date_patterns = [
            r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}\b',
            r'\b\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}\b'
        ]
        
        found_date = None
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                found_date = match.group()
                break
        
        # Basic title generation
        if doc_type == 'facture':
            return f"Facture {found_date or datetime.now().strftime('%Y-%m')}"
        elif doc_type == 'contrat':
            return f"Contrat {found_date or datetime.now().strftime('%Y-%m')}"
        else:
            return f"{doc_type.title()} {found_date or datetime.now().strftime('%Y-%m')}"
    
    def _suggest_tags(self, text: str, doc_type: str, ai_tags: List[str]) -> List[str]:
        """Suggest relevant tags based on content"""
        suggested = set()
        
        # Add document type as base tag
        if doc_type:
            suggested.add(doc_type)
        
        # Add AI suggested tags
        for tag in ai_tags:
            if tag and len(tag) > 2:
                suggested.add(tag.lower())
        
        # Add auto-detected tags based on patterns
        text_lower = text.lower()
        
        # Urgency detection
        urgent_keywords = ['urgent', 'prioritaire', 'immédiat', 'rapide']
        if any(keyword in text_lower for keyword in urgent_keywords):
            suggested.add('urgent')
        
        # Period detection
        if any(word in text_lower for word in ['mensuel', 'monthly']):
            suggested.add('mensuel')
        elif any(word in text_lower for word in ['annuel', 'yearly', 'annual']):
            suggested.add('annuel')
        
        return list(suggested)[:10]  # Limit to 10 tags
    
    def _determine_action(self, confidence: float) -> str:
        """Determine what action to take based on confidence"""
        if confidence >= self.thresholds['auto_classify']:
            return 'auto_classify'
        elif confidence >= self.thresholds['review_needed']:
            return 'review_needed'
        else:
            return 'manual_classification'
    
    def process_document(self, document_id: int, text_content: str) -> Dict:
        """
        Main processing function for a new document
        """
        self.logger.info(f"Processing document ID: {document_id}")
        
        try:
            # Classify the document
            classification = self.analyze_document_text(text_content)
            
            # Log the classification result
            recommendation = classification['final_recommendation']
            self.logger.info(
                f"Document {document_id} classified as '{recommendation['document_type']}' "
                f"with {recommendation['confidence']:.2f} confidence - Action: {recommendation['action']}"
            )
            
            # Store classification for learning
            self._store_classification(document_id, classification)
            
            return classification
            
        except Exception as e:
            self.logger.error(f"Error processing document {document_id}: {e}")
            return {'error': str(e)}
    
    def _store_classification(self, document_id: int, classification: Dict):
        """Store classification results for learning purposes"""
        storage_path = self.config_path.parent.parent / "models" / "classifications.jsonl"
        storage_path.parent.mkdir(exist_ok=True, parents=True)
        
        record = {
            'document_id': document_id,
            'timestamp': datetime.now().isoformat(),
            'classification': classification
        }
        
        with open(storage_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    # ─── Niveau 2: Auto-discovery de catégories ────────────────────────────
    
    def suggest_new_type(self, text: str, detected_type: str, confidence: float):
        """
        Stocker une suggestion de type détecté par Ollama mais non dans la taxonomie
        Si confiance > 0.7, stocker pour validation humaine (Niveau 2)
        """
        if confidence < 0.7:
            return  # Pas assez confiant
        
        # Vérifier si le type existe déjà dans la taxonomie
        type_exists = any(
            detected_type in subtypes 
            for subtypes in self.document_types.values()
        )
        
        if type_exists:
            return  # Type déjà connu
        
        # Stocker la suggestion pour validation humaine
        suggestions_path = self.config_path.parent / "suggested_types.json"
        
        suggestions = {}
        if suggestions_path.exists():
            try:
                with open(suggestions_path, 'r', encoding='utf-8') as f:
                    suggestions = json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load suggestions: {e}")
        
        # Ajouter la suggestion
        if detected_type not in suggestions:
            suggestions[detected_type] = {
                'suggested_at': datetime.now().isoformat(),
                'examples': [],
                'total_suggestions': 0,
                'validated': False,
                'category': None
            }
        
        suggestion = suggestions[detected_type]
        suggestion['total_suggestions'] += 1
        
        # Ajouter exemple de texte
        if len(suggestion['examples']) < 3:
            suggestion['examples'].append({
                'text': text[:500],
                'confidence': confidence,
                'timestamp': datetime.now().isoformat()
            })
        
        # Sauvegarder
        try:
            with open(suggestions_path, 'w', encoding='utf-8') as f:
                json.dump(suggestions, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Suggestion stored for type: {detected_type}")
        except Exception as e:
            self.logger.error(f"Failed to save suggestion: {e}")
    
    def validate_and_add_type(self, detected_type: str, category: str) -> bool:
        """
        Valider une suggestion et l'ajouter à la taxonomie (Niveau 2)
        À appeler depuis le dashboard après validation humaine
        """
        suggestions_path = self.config_path.parent / "suggested_types.json"
        
        if not suggestions_path.exists():
            return False
        
        try:
            with open(suggestions_path, 'r', encoding='utf-8') as f:
                suggestions = json.load(f)
            
            if detected_type not in suggestions:
                return False
            
            # Charger la taxonomie actuelle
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if category not in config.get('document_types', {}):
                return False
            
            # Marquer comme validée
            suggestions[detected_type]['validated'] = True
            suggestions[detected_type]['validated_at'] = datetime.now().isoformat()
            suggestions[detected_type]['category'] = category
            
            # Ajouter à la taxonomie (YAML)
            if detected_type not in config['document_types'][category]:
                config['document_types'][category][detected_type] = None
            
            # Ajouter pattern basique
            config.setdefault('detection_patterns', {})
            config['detection_patterns'].setdefault('document_identifiers', {})
            if detected_type not in config['detection_patterns']['document_identifiers']:
                config['detection_patterns']['document_identifiers'][detected_type] = [
                    detected_type.replace('_', ' ')
                ]
            
            # Sauvegarder taxonomie
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            # Sauvegarder suggestions
            with open(suggestions_path, 'w', encoding='utf-8') as f:
                json.dump(suggestions, f, indent=2, ensure_ascii=False)
            
            # Recharger la config en mémoire
            self.load_config()
            
            self.logger.info(f"Type '{detected_type}' added to category '{category}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to validate type: {e}")
            return False
    
    # ─── Niveau 3: Embeddings de documents ─────────────────────────────────
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Générer un embedding pour un document (Niveau 3)
        Utilise l'API embeddings d'Ollama
        """
        if not os.getenv('ENABLE_EMBEDDINGS', 'true').lower() == 'true':
            return None
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={
                    "model": self.ollama_model,
                    "prompt": text[:2000]  # Limiter à 2000 chars
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                embedding = result.get('embedding')
                return embedding
            else:
                self.logger.warning(f"Embedding generation failed: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.warning(f"Failed to generate embedding: {e}")
            return None
    
    def find_similar_documents(self, embedding: List[float], threshold: float = 0.75) -> List[Dict]:
        """
        Trouver des documents similaires basé sur embeddings (Niveau 3)
        Retourne les documents qui ont un score de similarité > threshold
        """
        embeddings_path = self.config_path.parent.parent / "models" / "embeddings.json"
        
        if not embeddings_path.exists():
            return []
        
        try:
            with open(embeddings_path, 'r', encoding='utf-8') as f:
                all_embeddings = json.load(f)
            
            # Calculer similarité cosinus
            similar = []
            for doc_id, stored_data in all_embeddings.items():
                stored_embedding = stored_data.get('embedding')
                if stored_embedding:
                    similarity = self._cosine_similarity(embedding, stored_embedding)
                    if similarity > threshold:
                        similar.append({
                            'document_id': doc_id,
                            'similarity': round(similarity, 3),
                            'type': stored_data.get('type'),
                            'sub_type': stored_data.get('sub_type')
                        })
            
            return sorted(similar, key=lambda x: x['similarity'], reverse=True)
            
        except Exception as e:
            self.logger.warning(f"Failed to find similar documents: {e}")
            return []
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculer la similarité cosinus entre deux vecteurs"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        import math
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a ** 2 for a in vec1))
        magnitude2 = math.sqrt(sum(b ** 2 for b in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def store_embedding(self, document_id: int, embedding: List[float], classification: Dict):
        """Stocker l'embedding d'un document pour utilisation future (Niveau 3)"""
        embeddings_path = self.config_path.parent.parent / "models" / "embeddings.json"
        embeddings_path.parent.mkdir(parents=True, exist_ok=True)
        
        embeddings = {}
        if embeddings_path.exists():
            try:
                with open(embeddings_path, 'r', encoding='utf-8') as f:
                    embeddings = json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load embeddings: {e}")
        
        recommendation = classification.get('final_recommendation', {})
        embeddings[str(document_id)] = {
            'embedding': embedding,
            'timestamp': datetime.now().isoformat(),
            'type': recommendation.get('document_type'),
            'sub_type': recommendation.get('sub_type'),
            'confidence': recommendation.get('confidence')
        }
        
        try:
            with open(embeddings_path, 'w', encoding='utf-8') as f:
                json.dump(embeddings, f, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to store embedding: {e}")


def main():
    """Test the classifier"""
    classifier = PaperlessAIClassifier()
    
    # Test with sample text
    sample_text = """
    FACTURE N° 2024-001
    Date: 15/02/2024
    
    Société ABC
    Montant HT: 150.00 €
    TVA 20%: 30.00 €
    Total TTC: 180.00 €
    """
    
    result = classifier.analyze_document_text(sample_text)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()