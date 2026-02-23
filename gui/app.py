"""
app.py – Flask backend for the Crypto Trading Bot Strategy Comparison UI.
Uses Firebase Firestore for persistence.

Endpoints:
  GET  /           → Serves the single-page frontend
  POST /run        → Executes user Python code, parses metrics, stores in Firestore
  GET  /methods    → Returns all stored methods as JSON
  DELETE /methods/<id> → Deletes a method by ID
"""

import json
import os
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, jsonify, render_template, request

from runner import run_user_code

app = Flask(__name__)

# ─── Firebase Init ───────────────────────────────────────────────────────────

# Place your Firebase service account key JSON in gui/firebase-key.json
KEY_PATH = os.path.join(os.path.dirname(__file__), 'firebase-key.json')

if not firebase_admin._apps:
    cred = credentials.Certificate(KEY_PATH)
    firebase_admin.initialize_app(cred)

db = firestore.client()
COLLECTION = 'methods'  # Firestore collection name


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/run', methods=['POST'])
def run_code():
    """Execute user code, parse the JSON output, store in Firestore."""
    data = request.get_json()
    if not data or 'code' not in data:
        return jsonify({'error': 'No code provided.'}), 400

    code = data['code']

    # Run the user script
    result = run_user_code(code, timeout=120)

    stdout = result['stdout']
    stderr = result['stderr']
    returncode = result['returncode']

    response = {
        'stdout': stdout,
        'stderr': stderr,
        'returncode': returncode,
        'metrics': None,
        'error': None,
    }

    if returncode != 0:
        response['error'] = 'Script exited with errors. Check stderr output.'
        return jsonify(response), 200

    # Parse the last non-empty line of stdout as JSON
    lines = [l.strip() for l in stdout.strip().splitlines() if l.strip()]
    if not lines:
        response['error'] = 'Script produced no output. Please print the required JSON.'
        return jsonify(response), 200

    last_line = lines[-1]
    try:
        metrics = json.loads(last_line)
    except json.JSONDecodeError:
        response['error'] = (
            f'Could not parse the last line of stdout as JSON.\n'
            f'Got: {last_line[:200]}\n\n'
            f'Expected format: {{"method_name": "...", "accuracy": ..., "one_year_gain": ...}}'
        )
        return jsonify(response), 200

    # Validate required fields
    required = ['method_name', 'accuracy', 'one_year_gain']
    missing = [f for f in required if f not in metrics]
    if missing:
        response['error'] = f'Missing required fields in JSON output: {", ".join(missing)}'
        return jsonify(response), 200

    # Store in Firestore
    doc_data = {
        'method_name': str(metrics['method_name']),
        'accuracy': float(metrics['accuracy']),
        'one_year_gain': float(metrics['one_year_gain']),
        'total_return': metrics.get('total_return'),
        'max_drawdown': metrics.get('max_drawdown'),
        'sharpe_ratio': metrics.get('sharpe_ratio'),
        'sortino_ratio': metrics.get('sortino_ratio'),
        'total_trades': metrics.get('total_trades'),
        'created_at': datetime.now().isoformat(),
    }

    doc_ref = db.collection(COLLECTION).add(doc_data)
    # doc_ref is a tuple (timestamp, DocumentReference)
    doc_id = doc_ref[1].id
    metrics['id'] = doc_id

    response['metrics'] = metrics
    return jsonify(response), 200


@app.route('/methods', methods=['GET'])
def get_methods():
    """Return all stored methods from Firestore."""
    docs = db.collection(COLLECTION).order_by('created_at', direction=firestore.Query.DESCENDING).stream()
    methods = []
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        methods.append(d)
    return jsonify(methods), 200


@app.route('/methods/<method_id>', methods=['DELETE'])
def delete_method(method_id):
    """Delete a method by Firestore document ID."""
    db.collection(COLLECTION).document(method_id).delete()
    return jsonify({'success': True}), 200


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("Starting Crypto Strategy Lab on http://localhost:5000")
    app.run(debug=True, port=5000)
