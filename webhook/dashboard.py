#!/usr/bin/env python3
"""
Dashboard pour Paperless AI Classifier
Workflow multi-action: Valider, Corriger, Voir, Ignorer, Forcer manuel
"""

import json
import os
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter, defaultdict
from flask import Blueprint, render_template_string, request, jsonify, redirect

dashboard = Blueprint('dashboard', __name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config" / "base-taxonomy.yaml"
CLASSIFICATIONS_PATH = BASE_DIR / "models" / "classifications.jsonl"
ACTIONS_PATH = BASE_DIR / "models" / "actions.jsonl"
CORRECTIONS_PATH = BASE_DIR / "models" / "corrections.jsonl"
THRESHOLD_OVERRIDES_PATH = BASE_DIR / "config" / "threshold_overrides.json"
SUGGESTIONS_PATH = BASE_DIR / "config" / "suggested_types.json"

# Base path (for reverse proxy /ai)
BASE_PATH = os.getenv('DASHBOARD_BASE_PATH', '').rstrip('/')

def bp(path: str) -> str:
    return f"{BASE_PATH}{path}"

# ─── Helpers ───────────────────────────────────────────────────────────────────

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_config(cfg):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

def load_threshold_overrides():
    if THRESHOLD_OVERRIDES_PATH.exists():
        with open(THRESHOLD_OVERRIDES_PATH, 'r') as f:
            return json.load(f)
    return {}

def save_threshold_overrides(overrides):
    THRESHOLD_OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(THRESHOLD_OVERRIDES_PATH, 'w') as f:
        json.dump(overrides, f, indent=2, ensure_ascii=False)

def load_jsonl(path):
    records = []
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return records

def append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')

def load_classifications():
    return load_jsonl(CLASSIFICATIONS_PATH)

def load_corrections():
    return load_jsonl(CORRECTIONS_PATH)

def load_actions():
    return load_jsonl(ACTIONS_PATH)

def save_action(action_record):
    """Enregistre une action dans l'historique unifié"""
    append_jsonl(ACTIONS_PATH, action_record)

def save_correction(correction):
    """Backward compat: enregistre aussi dans corrections.jsonl"""
    append_jsonl(CORRECTIONS_PATH, correction)

def get_paperless_url():
    """URL externe Paperless pour les liens utilisateur"""
    return os.getenv('PAPERLESS_EXTERNAL_URL', 'https://paperless.home.arpa')

def get_all_document_types(cfg):
    types = []
    for category, subtypes in cfg.get('document_types', {}).items():
        for st in subtypes:
            types.append(st)
    return sorted(set(types))

def load_suggestions():
    if SUGGESTIONS_PATH.exists():
        try:
            with open(SUGGESTIONS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_suggestions(suggestions):
    SUGGESTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SUGGESTIONS_PATH, 'w', encoding='utf-8') as f:
        json.dump(suggestions, f, indent=2, ensure_ascii=False)

def validate_suggested_type(type_name, category, cfg):
    suggestions = load_suggestions()
    if type_name not in suggestions:
        return False, "Suggestion introuvable"
    if category not in cfg.get('document_types', {}):
        return False, "Catégorie invalide"

    suggestions[type_name]['validated'] = True
    suggestions[type_name]['validated_at'] = datetime.now().isoformat()
    suggestions[type_name]['category'] = category

    # Ajouter au YAML taxonomie
    if type_name not in cfg['document_types'][category]:
        cfg['document_types'][category][type_name] = None

    # Ajouter un pattern minimal
    cfg.setdefault('detection_patterns', {})
    cfg['detection_patterns'].setdefault('document_identifiers', {})
    if type_name not in cfg['detection_patterns']['document_identifiers']:
        cfg['detection_patterns']['document_identifiers'][type_name] = [type_name.replace('_', ' ')]

    save_config(cfg)
    save_suggestions(suggestions)
    return True, "Suggestion validée"

def reject_suggested_type(type_name):
    suggestions = load_suggestions()
    if type_name not in suggestions:
        return False, "Suggestion introuvable"
    suggestions[type_name]['rejected'] = True
    suggestions[type_name]['rejected_at'] = datetime.now().isoformat()
    save_suggestions(suggestions)
    return True, "Suggestion rejetée"

def get_resolved_ids():
    """IDs de documents déjà traités (toute action sauf 'reporter')"""
    actions = load_actions()
    return {a['document_id'] for a in actions if a.get('action') != 'reporter'}

def compute_metrics(classifications, corrections, actions=None):
    total = len(classifications)
    if total == 0:
        return {'total': 0, 'auto': 0, 'review': 0, 'manual': 0,
                'auto_pct': 0, 'review_pct': 0, 'manual_pct': 0,
                'corrected': 0, 'accuracy': 100.0, 'by_type': {}}

    if actions is None:
        actions = load_actions()
    resolved = {a['document_id'] for a in actions if a.get('action') != 'reporter'}

    action_counts = Counter()
    by_type = defaultdict(lambda: {'total': 0, 'auto': 0, 'review': 0, 'manual': 0})

    for rec in classifications:
        cl = rec.get('classification', {})
        reco = cl.get('final_recommendation', {})
        action = reco.get('action', 'manual_classification')
        doc_type = reco.get('document_type', 'unknown')
        action_counts[action] += 1
        by_type[doc_type]['total'] += 1
        if action == 'auto_classify':
            by_type[doc_type]['auto'] += 1
        elif action == 'review_needed':
            # Pending review only
            if rec.get('document_id') not in resolved:
                by_type[doc_type]['review'] += 1
            else:
                # already handled -> count as manual bucket
                by_type[doc_type]['manual'] += 1
        else:
            by_type[doc_type]['manual'] += 1

    corrected_ids = {c['document_id'] for c in corrections}
    auto_count = action_counts.get('auto_classify', 0)
    auto_corrected = sum(1 for c in corrections
                         if any(r.get('document_id') == c['document_id']
                                and r.get('classification', {}).get('final_recommendation', {}).get('action') == 'auto_classify'
                                for r in classifications))
    accuracy = ((auto_count - auto_corrected) / auto_count * 100) if auto_count > 0 else 100.0

    review_pending = sum(1 for rec in classifications
                         if rec.get('classification', {}).get('final_recommendation', {}).get('action') == 'review_needed'
                         and rec.get('document_id') not in resolved)

    return {
        'total': total,
        'auto': action_counts.get('auto_classify', 0),
        'review': review_pending,
        'manual': action_counts.get('manual_classification', 0) + (action_counts.get('review_needed', 0) - review_pending),
        'auto_pct': round(action_counts.get('auto_classify', 0) / total * 100, 1),
        'review_pct': round(review_pending / total * 100, 1),
        'manual_pct': round((action_counts.get('manual_classification', 0) + (action_counts.get('review_needed', 0) - review_pending)) / total * 100, 1),
        'corrected': len(corrected_ids),
        'accuracy': round(accuracy, 1),
        'by_type': dict(by_type),
    }

def detect_drift(classifications, window_days=7):
    if len(classifications) < 5:
        return None
    cutoff = (datetime.now() - timedelta(days=window_days)).isoformat()
    all_conf = []
    recent_conf = []
    for rec in classifications:
        conf = rec.get('classification', {}).get('final_recommendation', {}).get('confidence', 0)
        ts = rec.get('timestamp', '')
        all_conf.append(conf)
        if ts >= cutoff:
            recent_conf.append(conf)
    if not recent_conf:
        return None
    overall_avg = sum(all_conf) / len(all_conf)
    recent_avg = sum(recent_conf) / len(recent_conf)
    drift = recent_avg - overall_avg
    return {
        'overall_avg': round(overall_avg, 3),
        'recent_avg': round(recent_avg, 3),
        'drift': round(drift, 3),
        'status': 'stable' if abs(drift) < 0.05 else ('improving' if drift > 0 else 'degrading')
    }

def reinforce_patterns(cfg, corrections):
    type_corrections = defaultdict(list)
    for c in corrections:
        if c.get('corrected_type'):
            type_corrections[c['corrected_type']].append(c)

    min_samples = cfg.get('learning', {}).get('minimum_samples', 3)
    patterns = cfg.get('detection_patterns', {}).get('document_identifiers', {})
    updated = False

    for doc_type, corrs in type_corrections.items():
        if len(corrs) >= min_samples and doc_type not in patterns:
            patterns[doc_type] = [doc_type.replace('_', ' ')]
            updated = True

    if updated:
        cfg['detection_patterns']['document_identifiers'] = patterns
        save_config(cfg)
    return updated

def apply_to_paperless(document_id, doc_type, tags=None):
    """Applique le type et les tags dans Paperless via l'API"""
    import requests as req
    paperless_url = os.getenv('PAPERLESS_URL', 'http://127.0.0.1:8010')
    token = os.getenv('PAPERLESS_TOKEN', '')
    if not token:
        return False
    headers = {'Authorization': f'Token {token}', 'Content-Type': 'application/json'}
    try:
        # Mettre à jour le document avec le type
        req.patch(
            f"{paperless_url}/api/documents/{document_id}/",
            headers=headers,
            json={'title': doc_type},
            timeout=10
        )
        return True
    except Exception:
        return False


# ─── HTML Templates ────────────────────────────────────────────────────────────

STYLE = """
<style>
  :root { --bg: #f5f5f5; --card: #fff; --accent: #2563eb; --green: #16a34a; --yellow: #ca8a04; --red: #dc2626; --gray: #6b7280; --purple: #7c3aed; --orange: #ea580c; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: #1f2937; padding: 1rem; max-width: 1200px; margin: 0 auto; }
  h1 { margin-bottom: 0.5rem; }
  .subtitle { color: var(--gray); margin-bottom: 1.5rem; }
  .grid { display: grid; gap: 1rem; }
  .grid-4 { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
  .grid-2 { grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); }
  .card { background: var(--card); border-radius: 8px; padding: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  .card h2 { font-size: 1rem; color: var(--gray); margin-bottom: 0.5rem; }
  .big-number { font-size: 2rem; font-weight: 700; }
  .green { color: var(--green); } .yellow { color: var(--yellow); } .red { color: var(--red); } .blue { color: var(--accent); } .purple { color: var(--purple); }
  table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
  th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #e5e7eb; font-size: 0.9rem; }
  th { font-weight: 600; color: var(--gray); }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.8rem; font-weight: 600; }
  .badge-auto { background: #dcfce7; color: var(--green); }
  .badge-review { background: #fef3c7; color: var(--yellow); }
  .badge-manual { background: #fee2e2; color: var(--red); }
  .badge-stable { background: #dcfce7; color: var(--green); }
  .badge-degrading { background: #fee2e2; color: var(--red); }
  .badge-improving { background: #dbeafe; color: var(--accent); }
  .badge-valider { background: #dcfce7; color: var(--green); }
  .badge-corriger { background: #dbeafe; color: var(--accent); }
  .badge-ignorer { background: #f3f4f6; color: var(--gray); }
  .badge-reporter { background: #fef3c7; color: var(--yellow); }
  .badge-forcer_manuel { background: #fee2e2; color: var(--red); }
  nav { margin-bottom: 1.5rem; }
  nav a { display: inline-block; padding: 0.5rem 1rem; background: var(--accent); color: white; text-decoration: none; border-radius: 6px; margin-right: 0.5rem; font-size: 0.9rem; margin-bottom: 0.25rem; }
  nav a.secondary { background: #e5e7eb; color: #374151; }
  form label { display: block; margin-bottom: 0.25rem; font-weight: 500; font-size: 0.9rem; }
  form input, form select, form textarea { padding: 0.4rem 0.6rem; border: 1px solid #d1d5db; border-radius: 4px; font-size: 0.9rem; margin-bottom: 0.75rem; }
  form input[type=number] { width: 80px; }
  button, .btn { padding: 0.5rem 1rem; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500; text-decoration: none; display: inline-block; }
  .btn-primary { background: var(--accent); color: white; }
  .btn-success { background: var(--green); color: white; }
  .btn-warning { background: var(--yellow); color: white; }
  .btn-danger { background: var(--red); color: white; }
  .btn-secondary { background: #e5e7eb; color: #374151; }
  .btn-purple { background: var(--purple); color: white; }
  .btn-sm { padding: 0.25rem 0.5rem; font-size: 0.8rem; }
  .btn-group { display: flex; gap: 0.35rem; flex-wrap: wrap; }
  .flash { padding: 0.75rem 1rem; border-radius: 6px; margin-bottom: 1rem; }
  .flash-success { background: #dcfce7; color: var(--green); }
  .flash-error { background: #fee2e2; color: var(--red); }
  .flash-info { background: #dbeafe; color: var(--accent); }
  .progress-bar { height: 8px; border-radius: 4px; background: #e5e7eb; overflow: hidden; margin-top: 0.25rem; }
  .progress-fill { height: 100%; border-radius: 4px; }
  .mt { margin-top: 1rem; } .mb { margin-bottom: 1rem; }
  .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; justify-content: center; align-items: center; }
  .modal-overlay.active { display: flex; }
  .modal { background: white; border-radius: 12px; width: 90%; max-width: 900px; height: 80vh; display: flex; flex-direction: column; overflow: hidden; }
  .modal-header { padding: 1rem 1.25rem; border-bottom: 1px solid #e5e7eb; display: flex; justify-content: space-between; align-items: center; }
  .modal-header h3 { margin: 0; }
  .modal-close { background: none; border: none; font-size: 1.5rem; cursor: pointer; color: var(--gray); padding: 0.25rem; }
  .modal-body { flex: 1; overflow: hidden; }
  .modal-body iframe { width: 100%; height: 100%; border: none; }
  .doc-detail { background: #f9fafb; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 0.75rem; font-size: 0.9rem; }
  .doc-detail strong { color: var(--accent); }
</style>
"""

LAYOUT_START = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Paperless AI - Dashboard</title>
""" + STYLE + """
</head>
<body>
<h1>🧠 Paperless AI Classifier</h1>
<p class="subtitle">Dashboard</p>
<nav>
  <a href="{{ base_path }}/dashboard">📊 Dashboard</a>
  <a href="{{ base_path }}/dashboard/thresholds" class="secondary">⚙️ Seuils</a>
  <a href="{{ base_path }}/dashboard/review" class="secondary">📋 À revoir</a>
  <a href="{{ base_path }}/dashboard/suggestions" class="secondary">🧪 Suggestions</a>
  <a href="{{ base_path }}/dashboard/history" class="secondary">📜 Historique</a>
  <a href="{{ base_path }}/health" class="secondary">❤️ Santé</a>
</nav>
"""

LAYOUT_END = """
</body>
</html>"""

FLASH_HTML = """
{% if flash %}
<div class="flash flash-{{ flash.type }}">{{ flash.message }}</div>
{% endif %}
"""

# ─── Page: Dashboard ───────────────────────────────────────────────────────────

PAGE_DASHBOARD = LAYOUT_START + FLASH_HTML + """
<div class="grid grid-4 mb">
  <div class="card">
    <h2>Documents classés</h2>
    <div class="big-number blue">{{ m.total }}</div>
  </div>
  <div class="card">
    <h2>Auto-classés</h2>
    <div class="big-number green">{{ m.auto }} <small style="font-size:0.9rem">({{ m.auto_pct }}%)</small></div>
    <div class="progress-bar"><div class="progress-fill" style="width:{{ m.auto_pct }}%;background:var(--green)"></div></div>
  </div>
  <div class="card">
    <h2>En review</h2>
    <div class="big-number yellow">{{ m.review }} <small style="font-size:0.9rem">({{ m.review_pct }}%)</small></div>
    <div class="progress-bar"><div class="progress-fill" style="width:{{ m.review_pct }}%;background:var(--yellow)"></div></div>
  </div>
  <div class="card">
    <h2>Manuels</h2>
    <div class="big-number red">{{ m.manual }} <small style="font-size:0.9rem">({{ m.manual_pct }}%)</small></div>
    <div class="progress-bar"><div class="progress-fill" style="width:{{ m.manual_pct }}%;background:var(--red)"></div></div>
  </div>
</div>

<div class="card mb">
  <h2>🧭 Processus de classification (transparent)</h2>
  <ol style="margin-left:1.2rem;line-height:1.5">
    <li><strong>Règles & patterns</strong> détectent rapidement les types évidents</li>
    <li><strong>IA (Ollama)</strong> complète la classification et propose un type</li>
    <li><strong>Seuils</strong> déterminent auto / review / manuel</li>
    <li><strong>Actions humaines</strong> (valider/corriger) alimentent l'apprentissage</li>
  </ol>
  <p style="color:var(--gray);font-size:0.85rem;margin-top:0.5rem">
    Objectif : rendre chaque décision traçable et compréhensible.
  </p>
</div>

<div class="grid grid-2 mb">
  <div class="card">
    <h2>📈 Précision & Drift</h2>
    <p>Précision auto-classement: <strong>{{ m.accuracy }}%</strong></p>
    <p>Corrections humaines: <strong>{{ m.corrected }}</strong></p>
    {% if drift %}
    <p class="mt">Drift (7j): <span class="badge badge-{{ drift.status }}">{{ drift.status }}</span>
      Δ = {{ drift.drift }} (récent {{ drift.recent_avg }} vs global {{ drift.overall_avg }})</p>
    {% else %}
    <p class="mt" style="color:var(--gray)">Pas assez de données pour le drift</p>
    {% endif %}
  </div>
  <div class="card">
    <h2>📊 Par type de document</h2>
    {% if m.by_type %}
    <table>
      <tr><th>Type</th><th>Total</th><th>Auto</th><th>Review</th><th>Manuel</th></tr>
      {% for t, d in m.by_type.items() %}
      <tr><td>{{ t }}</td><td>{{ d.total }}</td><td class="green">{{ d.auto }}</td><td class="yellow">{{ d.review }}</td><td class="red">{{ d.manual }}</td></tr>
      {% endfor %}
    </table>
    {% else %}
    <p style="color:var(--gray)">Aucune classification encore</p>
    {% endif %}
  </div>
</div>
""" + LAYOUT_END

# ─── Page: Review (multi-action) ──────────────────────────────────────────────

PAGE_REVIEW = LAYOUT_START + FLASH_HTML + """
<div class="card">
  <h2>📋 Documents à revoir</h2>
  <p style="color:var(--gray);font-size:0.85rem;margin-bottom:0.75rem">
    {{ items|length }} document(s) en attente de décision
  </p>
  <div class="doc-detail">
    <strong>🔎 Aide rapide</strong><br>
    Seuils: <strong>auto ≥ {{ (thresholds.auto_classify * 100)|int }}%</strong> · review ≥ {{ (thresholds.review_needed * 100)|int }}%<br>
    <ul style="margin:0.4rem 0 0 1.2rem">
      <li><strong>Valider</strong> : confirme le type et applique dans Paperless</li>
      <li><strong>Corriger</strong> : change le type (apprentissage)</li>
      <li><strong>Ignorer</strong> : retire de la file sans changement</li>
      <li><strong>Manuel</strong> : force le flux manuel</li>
      <li><strong>Voir</strong> : prévisualise le document</li>
    </ul>
  </div>
  {% if items %}
  <table>
    <tr>
      <th>ID</th>
      <th>Date</th>
      <th>Type détecté</th>
      <th>Confiance</th>
      <th style="min-width:320px">Actions</th>
    </tr>
    {% for item in items %}
    <tr>
      <td><strong>#{{ item.document_id }}</strong></td>
      <td>{{ item.timestamp[:16] }}</td>
      <td>{{ item.doc_type }}</td>
      <td>
        <span class="badge {% if item.confidence >= 0.75 %}badge-auto{% elif item.confidence >= 0.6 %}badge-review{% else %}badge-manual{% endif %}">
          {{ (item.confidence * 100)|round(1) }}%
        </span>
      </td>
      <td>
        <div class="btn-group">
          <form method="POST" action="{{ base_path }}/dashboard/action" style="display:inline">
            <input type="hidden" name="document_id" value="{{ item.document_id }}">
            <input type="hidden" name="doc_type" value="{{ item.doc_type }}">
            <input type="hidden" name="action" value="valider">
            <button type="submit" class="btn btn-success btn-sm" title="Confirmer le type détecté et appliquer">✅ Valider</button>
          </form>
          <a href="{{ base_path }}/dashboard/correct/{{ item.document_id }}?current_type={{ item.doc_type }}" class="btn btn-primary btn-sm" title="Modifier le type de document">✏️ Corriger</a>
          <button onclick="openDocModal({{ item.document_id }})" class="btn btn-secondary btn-sm" title="Voir le document dans Paperless">👁️ Voir</button>
          <form method="POST" action="{{ base_path }}/dashboard/action" style="display:inline">
            <input type="hidden" name="document_id" value="{{ item.document_id }}">
            <input type="hidden" name="doc_type" value="{{ item.doc_type }}">
            <input type="hidden" name="action" value="ignorer">
            <button type="submit" class="btn btn-secondary btn-sm" title="Ignorer ce document (masquer de la file)">⏭️ Ignorer</button>
          </form>
          <form method="POST" action="{{ base_path }}/dashboard/action" style="display:inline">
            <input type="hidden" name="document_id" value="{{ item.document_id }}">
            <input type="hidden" name="doc_type" value="{{ item.doc_type }}">
            <input type="hidden" name="action" value="forcer_manuel">
            <button type="submit" class="btn btn-danger btn-sm" title="Forcer la classification manuelle">🔒 Manuel</button>
          </form>
        </div>
      </td>
    </tr>
    {% endfor %}
  </table>
  {% else %}
  <p style="color:var(--gray);margin-top:0.5rem">Aucun document en attente de review 🎉</p>
  {% endif %}
</div>

<!-- Modal pour voir le document -->
<div class="modal-overlay" id="docModal">
  <div class="modal">
    <div class="modal-header">
      <h3>📄 Document <span id="modalDocId"></span></h3>
      <div style="display:flex;gap:0.5rem;align-items:center">
        <a id="docOpenLink" class="btn btn-secondary btn-sm" target="_blank" href="#">Ouvrir dans Paperless</a>
        <button class="modal-close" onclick="closeDocModal()">✕</button>
      </div>
    </div>
    <div class="modal-body">
      <iframe id="docIframe" src="about:blank"></iframe>
    </div>
  </div>
</div>

<script>
function openDocModal(docId) {
  document.getElementById('modalDocId').textContent = '#' + docId;
  const url = '{{ paperless_url }}/documents/' + docId + '/';
  document.getElementById('docIframe').src = url;
  document.getElementById('docOpenLink').href = url;
  document.getElementById('docModal').classList.add('active');
}
function closeDocModal() {
  document.getElementById('docModal').classList.remove('active');
  document.getElementById('docIframe').src = 'about:blank';
}
document.getElementById('docModal').addEventListener('click', function(e) {
  if (e.target === this) closeDocModal();
});
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeDocModal();
});
</script>
""" + LAYOUT_END

# ─── Page: Correct (enrichi) ──────────────────────────────────────────────────

PAGE_CORRECT = LAYOUT_START + FLASH_HTML + """
<div class="card" style="max-width:600px">
  <h2>✏️ Corriger le document #{{ document_id }}</h2>

  <div class="doc-detail">
    <strong>Type détecté :</strong> {{ current_type }}<br>
    <a href="javascript:void(0)" onclick="openDocModal({{ document_id }})" style="font-size:0.85rem">👁️ Voir le document dans Paperless</a>
  </div>

  <form method="POST" action="{{ base_path }}/dashboard/correct/{{ document_id }}">
    <label>Nouveau type</label>
    <select name="corrected_type" style="width:100%">
      {% for dt in doc_types %}
      <option value="{{ dt }}" {% if dt == current_type %}selected{% endif %}>{{ dt }}</option>
      {% endfor %}
    </select>

    <label>Notes (optionnel)</label>
    <textarea name="notes" placeholder="Raison de la correction..." style="width:100%;height:60px;resize:vertical"></textarea>

    <div style="display:flex;gap:0.5rem;margin-top:0.75rem">
      <button type="submit" class="btn btn-success">✅ Appliquer la correction</button>
      <a href="{{ base_path }}/dashboard/review" class="btn btn-secondary">← Retour</a>
    </div>
  </form>
</div>

<!-- Modal pour voir le document -->
<div class="modal-overlay" id="docModal">
  <div class="modal">
    <div class="modal-header">
      <h3>📄 Document <span id="modalDocId">#{{ document_id }}</span></h3>
      <div style="display:flex;gap:0.5rem;align-items:center">
        <a id="docOpenLink" class="btn btn-secondary btn-sm" target="_blank" href="#">Ouvrir dans Paperless</a>
        <button class="modal-close" onclick="closeDocModal()">✕</button>
      </div>
    </div>
    <div class="modal-body">
      <iframe id="docIframe" src="about:blank"></iframe>
    </div>
  </div>
</div>

<script>
function openDocModal(docId) {
  const url = '{{ paperless_url }}/documents/' + docId + '/';
  document.getElementById('docIframe').src = url;
  document.getElementById('docOpenLink').href = url;
  document.getElementById('docModal').classList.add('active');
}
function closeDocModal() {
  document.getElementById('docModal').classList.remove('active');
  document.getElementById('docIframe').src = 'about:blank';
}
document.getElementById('docModal').addEventListener('click', function(e) { if (e.target === this) closeDocModal(); });
document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closeDocModal(); });
</script>
""" + LAYOUT_END

# ─── Page: Historique des actions ──────────────────────────────────────────────

PAGE_HISTORY = LAYOUT_START + FLASH_HTML + """
<div class="card">
  <h2>📜 Historique des actions</h2>
  <p style="color:var(--gray);font-size:0.85rem;margin-bottom:0.75rem">
    {{ actions|length }} action(s) enregistrée(s)
  </p>
  {% if actions %}
  <table>
    <tr><th>Date</th><th>Doc ID</th><th>Action</th><th>Type original</th><th>Type final</th><th>Notes</th></tr>
    {% for a in actions %}
    <tr>
      <td>{{ a.timestamp[:16] }}</td>
      <td><strong>#{{ a.document_id }}</strong></td>
      <td><span class="badge badge-{{ a.action }}">{{ a.action_label }}</span></td>
      <td>{{ a.original_type or '-' }}</td>
      <td>{% if a.final_type and a.final_type != a.original_type %}<strong>{{ a.final_type }}</strong>{% elif a.final_type %}{{ a.final_type }}{% else %}-{% endif %}</td>
      <td style="color:var(--gray);font-size:0.85rem">{{ a.notes or '' }}</td>
    </tr>
    {% endfor %}
  </table>
  {% else %}
  <p style="color:var(--gray);margin-top:0.5rem">Aucune action enregistrée</p>
  {% endif %}
</div>
""" + LAYOUT_END

# ─── Page: Suggestions (Niveau 2) ─────────────────────────────────────────────

PAGE_SUGGESTIONS = LAYOUT_START + FLASH_HTML + """
<div class="card">
  <h2>🧪 Suggestions de nouveaux types</h2>
  <p style="color:var(--gray);font-size:0.85rem;margin-bottom:0.75rem">
    {{ pending|length }} suggestion(s) en attente · {{ validated_count }} validée(s) · {{ rejected_count }} rejetée(s)
  </p>

  {% if pending %}
  <table>
    <tr><th>Type</th><th>Occurrences</th><th>Exemple</th><th>Catégorie</th><th>Actions</th></tr>
    {% for s in pending %}
    <tr>
      <td><strong>{{ s.type_name }}</strong></td>
      <td>{{ s.total_suggestions }}</td>
      <td style="color:var(--gray);font-size:0.85rem">{{ (s.examples[0].text if s.examples) | default('') | truncate(140) }}</td>
      <td>
        <form method="POST" action="{{ base_path }}/dashboard/suggestions/validate" style="display:flex;gap:0.5rem;align-items:center">
          <input type="hidden" name="type_name" value="{{ s.type_name }}">
          <select name="category">
            {% for cat in categories %}
              <option value="{{ cat }}" {% if s.category == cat %}selected{% endif %}>{{ cat }}</option>
            {% endfor %}
          </select>
          <button type="submit" class="btn btn-success btn-sm">✅ Valider</button>
        </form>
      </td>
      <td>
        <form method="POST" action="{{ base_path }}/dashboard/suggestions/reject" style="display:inline">
          <input type="hidden" name="type_name" value="{{ s.type_name }}">
          <button type="submit" class="btn btn-danger btn-sm">⛔ Rejeter</button>
        </form>
      </td>
    </tr>
    {% endfor %}
  </table>
  {% else %}
  <p style="color:var(--gray);margin-top:0.5rem">Aucune suggestion en attente 🎉</p>
  {% endif %}
</div>
""" + LAYOUT_END

# ─── Page: Seuils ─────────────────────────────────────────────────────────────

PAGE_THRESHOLDS = LAYOUT_START + FLASH_HTML + """
<div class="card mb">
  <h2>⚙️ Seuils de confiance globaux</h2>
  <form method="POST" action="{{ base_path }}/dashboard/thresholds">
    <div style="display:flex;gap:2rem;flex-wrap:wrap;margin-top:0.5rem">
      <div>
        <label>Auto-classement (≥)</label>
        <input type="number" name="auto_classify" value="{{ (thresholds.auto_classify * 100)|int }}" min="50" max="100" step="1"> %
      </div>
      <div>
        <label>Review (≥)</label>
        <input type="number" name="review_needed" value="{{ (thresholds.review_needed * 100)|int }}" min="20" max="99" step="1"> %
      </div>
    </div>
    <button type="submit" class="btn btn-primary mt">💾 Enregistrer</button>
  </form>
</div>

<div class="card">
  <h2>🎯 Seuils par catégorie</h2>
  <p style="color:var(--gray);font-size:0.9rem;margin-bottom:0.75rem">Laissez vide pour utiliser les seuils globaux.</p>
  <form method="POST" action="{{ base_path }}/dashboard/thresholds/overrides">
    <table>
      <tr><th>Type</th><th>Auto (≥ %)</th><th>Review (≥ %)</th></tr>
      {% for dt in doc_types %}
      <tr>
        <td>{{ dt }}</td>
        <td><input type="number" name="auto_{{ dt }}" value="{{ overrides.get(dt, {}).get('auto_classify', '') }}" min="50" max="100" step="1" placeholder="-" style="width:70px"></td>
        <td><input type="number" name="review_{{ dt }}" value="{{ overrides.get(dt, {}).get('review_needed', '') }}" min="20" max="99" step="1" placeholder="-" style="width:70px"></td>
      </tr>
      {% endfor %}
    </table>
    <button type="submit" class="btn btn-primary mt">💾 Enregistrer</button>
  </form>
</div>
""" + LAYOUT_END


# ─── Routes ────────────────────────────────────────────────────────────────────

ACTION_LABELS = {
    'valider': '✅ Validé',
    'corriger': '✏️ Corrigé',
    'ignorer': '⏭️ Ignoré',
    'forcer_manuel': '🔒 Manuel',
    'reporter': '⏸️ Reporté',
}

def _flash(msg, ftype='success'):
    return {'type': ftype, 'message': msg}


@dashboard.route('/dashboard')
def index():
    classifications = load_classifications()
    corrections = load_corrections()
    m = compute_metrics(classifications, corrections)
    drift = detect_drift(classifications)
    flash_msg = request.args.get('flash')
    flash = _flash(flash_msg) if flash_msg else None
    return render_template_string(PAGE_DASHBOARD, m=m, drift=drift, flash=flash, base_path=BASE_PATH)


@dashboard.route('/dashboard/review')
def review():
    classifications = load_classifications()
    resolved = get_resolved_ids()
    cfg = load_config()
    thresholds = cfg.get('confidence_thresholds', {})
    items = []
    for rec in classifications:
        reco = rec.get('classification', {}).get('final_recommendation', {})
        if reco.get('action') == 'review_needed' and rec.get('document_id') not in resolved:
            items.append({
                'document_id': rec['document_id'],
                'timestamp': rec.get('timestamp', ''),
                'doc_type': reco.get('document_type', 'unknown'),
                'confidence': reco.get('confidence', 0),
            })
    items.sort(key=lambda x: x['timestamp'], reverse=True)
    flash_msg = request.args.get('flash')
    flash = _flash(flash_msg) if flash_msg else None
    return render_template_string(PAGE_REVIEW, items=items, flash=flash,
                                  paperless_url=get_paperless_url(), base_path=BASE_PATH, thresholds=thresholds)


@dashboard.route('/dashboard/action', methods=['POST'])
def handle_action():
    """Route unique pour toutes les actions rapides (valider, ignorer, forcer_manuel)"""
    document_id = int(request.form.get('document_id', 0))
    action = request.form.get('action', '')
    doc_type = request.form.get('doc_type', 'unknown')

    if action not in ('valider', 'ignorer', 'forcer_manuel', 'reporter'):
        return redirect(bp('/dashboard/review?flash=Action+inconnue'))

    action_record = {
        'document_id': document_id,
        'timestamp': datetime.now().isoformat(),
        'action': action,
        'action_label': ACTION_LABELS.get(action, action),
        'original_type': doc_type,
        'final_type': doc_type if action == 'valider' else None,
        'notes': '',
    }

    # Logique spécifique par action
    if action == 'valider':
        # Confirmer le type détecté et appliquer dans Paperless
        apply_to_paperless(document_id, doc_type)
        action_record['notes'] = 'Type confirmé et appliqué dans Paperless'
        # Aussi enregistrer comme correction positive (pour l'apprentissage)
        save_correction({
            'document_id': document_id,
            'timestamp': datetime.now().isoformat(),
            'original_type': doc_type,
            'corrected_type': doc_type,
            'notes': 'Validation humaine — type confirmé',
        })

    elif action == 'ignorer':
        action_record['notes'] = 'Document ignoré par l\'utilisateur'

    elif action == 'forcer_manuel':
        action_record['notes'] = 'Classement forcé en mode manuel'

    elif action == 'reporter':
        action_record['notes'] = 'Décision reportée'

    save_action(action_record)

    labels = {'valider': 'validé ✅', 'ignorer': 'ignoré ⏭️', 'forcer_manuel': 'forcé en manuel 🔒', 'reporter': 'reporté ⏸️'}
    return redirect(bp(f'/dashboard/review?flash=Document+{document_id}+{labels.get(action, action)}'))


@dashboard.route('/dashboard/correct/<int:document_id>', methods=['GET', 'POST'])
def correct(document_id):
    cfg = load_config()
    doc_types = get_all_document_types(cfg)

    if request.method == 'POST':
        corrected_type = request.form.get('corrected_type', '')
        notes = request.form.get('notes', '')

        classifications = load_classifications()
        original_type = 'unknown'
        for rec in classifications:
            if rec.get('document_id') == document_id:
                original_type = rec.get('classification', {}).get('final_recommendation', {}).get('document_type', 'unknown')
                break

        # Enregistrer la correction
        correction = {
            'document_id': document_id,
            'timestamp': datetime.now().isoformat(),
            'original_type': original_type,
            'corrected_type': corrected_type,
            'notes': notes,
        }
        save_correction(correction)

        # Enregistrer l'action dans l'historique
        save_action({
            'document_id': document_id,
            'timestamp': datetime.now().isoformat(),
            'action': 'corriger',
            'action_label': ACTION_LABELS['corriger'],
            'original_type': original_type,
            'final_type': corrected_type,
            'notes': notes,
        })

        # Appliquer dans Paperless
        apply_to_paperless(document_id, corrected_type)

        # Renforcer les patterns
        corrections = load_corrections()
        reinforce_patterns(cfg, corrections)

        return redirect(bp(f'/dashboard/review?flash=Document+{document_id}+corrigé+✅'))

    current_type = request.args.get('current_type', 'unknown')
    flash_msg = request.args.get('flash')
    flash = _flash(flash_msg) if flash_msg else None
    return render_template_string(PAGE_CORRECT,
                                  document_id=document_id,
                                  current_type=current_type,
                                  doc_types=doc_types,
                                  flash=flash,
                                  paperless_url=get_paperless_url(),
                                  base_path=BASE_PATH)


@dashboard.route('/dashboard/history')
def history():
    actions = load_actions()
    actions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    flash_msg = request.args.get('flash')
    flash = _flash(flash_msg) if flash_msg else None
    return render_template_string(PAGE_HISTORY, actions=actions, flash=flash, base_path=BASE_PATH)


@dashboard.route('/dashboard/suggestions')
def suggestions():
    cfg = load_config()
    suggestions = load_suggestions()

    pending = []
    validated_count = 0
    rejected_count = 0

    for type_name, data in suggestions.items():
        if data.get('validated'):
            validated_count += 1
            continue
        if data.get('rejected'):
            rejected_count += 1
            continue
        pending.append({
            'type_name': type_name,
            **data
        })

    pending.sort(key=lambda x: x.get('total_suggestions', 0), reverse=True)

    flash_msg = request.args.get('flash')
    flash = _flash(flash_msg) if flash_msg else None
    categories = list(cfg.get('document_types', {}).keys())

    return render_template_string(
        PAGE_SUGGESTIONS,
        pending=pending,
        validated_count=validated_count,
        rejected_count=rejected_count,
        categories=categories,
        flash=flash,
        base_path=BASE_PATH
    )


@dashboard.route('/dashboard/suggestions/validate', methods=['POST'])
def suggestions_validate():
    type_name = request.form.get('type_name', '').strip()
    category = request.form.get('category', '').strip()
    if not type_name or not category:
        return redirect(bp('/dashboard/suggestions?flash=Type+ou+catégorie+manquant'))

    cfg = load_config()
    ok, msg = validate_suggested_type(type_name, category, cfg)
    return redirect(bp('/dashboard/suggestions?flash=' + msg.replace(' ', '+')))


@dashboard.route('/dashboard/suggestions/reject', methods=['POST'])
def suggestions_reject():
    type_name = request.form.get('type_name', '').strip()
    if not type_name:
        return redirect(bp('/dashboard/suggestions?flash=Type+manquant'))

    ok, msg = reject_suggested_type(type_name)
    return redirect(bp('/dashboard/suggestions?flash=' + msg.replace(' ', '+')))


@dashboard.route('/dashboard/thresholds', methods=['GET', 'POST'])
def thresholds():
    cfg = load_config()
    if request.method == 'POST':
        auto_val = int(request.form.get('auto_classify', 85)) / 100
        review_val = int(request.form.get('review_needed', 60)) / 100
        cfg['confidence_thresholds']['auto_classify'] = round(auto_val, 2)
        cfg['confidence_thresholds']['review_needed'] = round(review_val, 2)
        cfg['confidence_thresholds']['manual_only'] = round(review_val, 2)
        save_config(cfg)
        return redirect(bp('/dashboard/thresholds?flash=Seuils+mis+à+jour+✅'))

    overrides = load_threshold_overrides()
    doc_types = get_all_document_types(cfg)
    flash_msg = request.args.get('flash')
    flash = _flash(flash_msg) if flash_msg else None
    return render_template_string(PAGE_THRESHOLDS,
                                  thresholds=cfg['confidence_thresholds'],
                                  overrides=overrides,
                                  doc_types=doc_types,
                                  flash=flash,
                                  base_path=BASE_PATH)


@dashboard.route('/dashboard/thresholds/overrides', methods=['POST'])
def thresholds_overrides():
    cfg = load_config()
    doc_types = get_all_document_types(cfg)
    overrides = {}
    for dt in doc_types:
        auto_val = request.form.get(f'auto_{dt}', '').strip()
        review_val = request.form.get(f'review_{dt}', '').strip()
        if auto_val or review_val:
            entry = {}
            if auto_val:
                entry['auto_classify'] = int(auto_val)
            if review_val:
                entry['review_needed'] = int(review_val)
            overrides[dt] = entry
    save_threshold_overrides(overrides)
    return redirect(bp('/dashboard/thresholds?flash=Overrides+enregistrés+✅'))


# ─── API Endpoints ─────────────────────────────────────────────────────────────

@dashboard.route('/api/metrics')
def api_metrics():
    classifications = load_classifications()
    corrections = load_corrections()
    m = compute_metrics(classifications, corrections)
    drift = detect_drift(classifications)
    return jsonify({'metrics': m, 'drift': drift})

@dashboard.route('/api/thresholds', methods=['GET', 'PUT'])
def api_thresholds():
    cfg = load_config()
    if request.method == 'PUT':
        data = request.get_json()
        if 'auto_classify' in data:
            cfg['confidence_thresholds']['auto_classify'] = data['auto_classify']
        if 'review_needed' in data:
            cfg['confidence_thresholds']['review_needed'] = data['review_needed']
            cfg['confidence_thresholds']['manual_only'] = data['review_needed']
        save_config(cfg)
    return jsonify(cfg['confidence_thresholds'])

@dashboard.route('/api/action', methods=['POST'])
def api_action():
    data = request.get_json()
    if not data or 'document_id' not in data or 'action' not in data:
        return jsonify({'error': 'document_id and action required'}), 400

    action = data['action']
    if action not in ('valider', 'corriger', 'ignorer', 'forcer_manuel', 'reporter'):
        return jsonify({'error': f'Unknown action: {action}'}), 400

    document_id = data['document_id']
    doc_type = data.get('doc_type', 'unknown')
    corrected_type = data.get('corrected_type', doc_type)
    notes = data.get('notes', '')

    action_record = {
        'document_id': document_id,
        'timestamp': datetime.now().isoformat(),
        'action': action,
        'action_label': ACTION_LABELS.get(action, action),
        'original_type': doc_type,
        'final_type': corrected_type if action in ('valider', 'corriger') else None,
        'notes': notes,
    }
    save_action(action_record)

    if action in ('valider', 'corriger'):
        save_correction({
            'document_id': document_id,
            'timestamp': datetime.now().isoformat(),
            'original_type': doc_type,
            'corrected_type': corrected_type,
            'notes': notes,
        })
        apply_to_paperless(document_id, corrected_type)

    return jsonify({'status': 'ok', 'action': action_record})

@dashboard.route('/api/history')
def api_history():
    actions = load_actions()
    actions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return jsonify({'actions': actions})
