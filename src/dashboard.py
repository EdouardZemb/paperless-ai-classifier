from flask import Flask, request, jsonify
from datetime import datetime
import json

app = Flask(__name__)

actions_log_file = 'models/actions.jsonl'

@app.route('/dashboard/action', methods=['POST'])
def handle_action():
    data = request.json
    document_id = data.get('document_id')
    action = data.get('action')
    notes = data.get('notes')

    if action not in ['valider', 'corriger', 'ignorer', 'forcer_manuel', 'reporter']:
        return jsonify({'error': 'Invalid action'}), 400

    # Log the action
    log_action(document_id, action, notes)

    return jsonify({'message': 'Action processed'}), 200

@app.route('/dashboard/history', methods=['GET'])
def get_history():
    with open(actions_log_file, 'r') as f:
        actions = f.readlines()
    actions = [json.loads(action) for action in actions]
    return jsonify(actions), 200

def log_action(document_id, action, notes):
    log_entry = {
        'document_id': document_id,
        'action': action,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'notes': notes
    }
    with open(actions_log_file, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')

if __name__ == '__main__':
    app.run(debug=True)