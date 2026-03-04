import json
import os
import threading
import urllib.request

from flask import Blueprint, Response, jsonify, render_template, request, stream_with_context

PROJECT_META = {
    'id': 'rag-chatbot',
    'name': 'D&D RAG',
    'description': 'Ask anything about D&D 5e. Semantic search across the Dungeon Master\'s Guide and Player\'s Handbook retrieves relevant rules, then Claude AI synthesizes a cited answer.',
    'icon': 'auto_stories',
    'color': '#6366f1',
    'category': 'Retrieval-Augmented Generation',
    'nav_group': 'GenAI',
    'tags': ['rag', 'llm', 'claude', 'anthropic', 'vector search', 'sqlite-vec', 'd&d'],
    'screenshot': 'rag_chatbot.png',
}

bp = Blueprint(
    'rag_chatbot',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='static',
    url_prefix='/rag-chatbot',
)

_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

# All PDF sources: add more entries here to expand the knowledge base
_SOURCES = [
    {'filename': 'dmg.pdf', 'label': 'DMG'},
    {'filename': 'phb.pdf', 'label': 'PHB'},
]

# Shared state for background indexing
_state = {
    'initialized': False,
    'indexing': False,
    'chunk_count': 0,
    'error': None,
    'sources': [],   # list of {label, found, indexed}
}
_state_lock = threading.Lock()


def _build_source_status(indexed_labels: set[str]) -> list[dict]:
    return [
        {
            'label':   s['label'],
            'found':   os.path.exists(os.path.join(_DATA_DIR, s['filename'])),
            'indexed': s['label'] in indexed_labels,
        }
        for s in _SOURCES
    ]


def _index_documents() -> None:
    """Index all present PDFs. Wipes the DB if the indexed set doesn't match present PDFs."""
    with _state_lock:
        if _state['indexing'] or _state['initialized']:
            return
        _state['indexing'] = True

    try:
        from .services.vectorstore import (
            get_chunk_count, get_indexed_sources, init_db, insert_chunks,
        )
        from .services.embeddings import encode
        from .services.pdf_processor import extract_chunks

        present = {
            s['label'] for s in _SOURCES
            if os.path.exists(os.path.join(_DATA_DIR, s['filename']))
        }
        indexed = get_indexed_sources()

        # Re-index if the set of present PDFs has changed
        if present and present == indexed:
            count = get_chunk_count()
            with _state_lock:
                _state['initialized'] = True
                _state['chunk_count'] = count
                _state['sources'] = _build_source_status(indexed)
                _state['indexing'] = False
            return

        # Wipe and rebuild
        db_path = os.path.join(_DATA_DIR, 'vectors.db')
        if os.path.exists(db_path):
            os.remove(db_path)
        init_db()

        total = 0
        for source in _SOURCES:
            pdf_path = os.path.join(_DATA_DIR, source['filename'])
            if not os.path.exists(pdf_path):
                continue
            chunks = extract_chunks(pdf_path)
            embeddings = encode([c['text'] for c in chunks])
            insert_chunks(chunks, embeddings, source['label'])
            total += len(chunks)

        with _state_lock:
            _state['initialized'] = True
            _state['chunk_count'] = total
            _state['sources'] = _build_source_status(present)

    except Exception as exc:
        with _state_lock:
            _state['error'] = str(exc)
    finally:
        with _state_lock:
            _state['indexing'] = False


# Kick off indexing at import time if at least one PDF is present
_any_pdf = any(
    os.path.exists(os.path.join(_DATA_DIR, s['filename'])) for s in _SOURCES
)
if _any_pdf:
    _t = threading.Thread(target=_index_documents, daemon=True)
    _t.start()


# ── Routes ────────────────────────────────────────────────────────

@bp.route('/')
def index():
    return render_template('rag_chatbot/index.html')


@bp.route('/api/status')
def status():
    with _state_lock:
        return jsonify({
            'initialized': _state['initialized'],
            'indexing':    _state['indexing'],
            'chunk_count': _state['chunk_count'],
            'error':       _state['error'],
            'sources':     _state['sources'],
        })


@bp.route('/api/anthropic-status')
def anthropic_status():
    try:
        with urllib.request.urlopen(
            'https://status.anthropic.com/api/v2/status.json', timeout=5
        ) as resp:
            data = json.loads(resp.read())
        return jsonify(data['status'])
    except Exception:
        return jsonify({'indicator': 'unknown', 'description': 'Status unavailable'}), 502


@bp.route('/api/chat', methods=['POST'])
def chat():
    with _state_lock:
        ready = _state['initialized']
        indexing = _state['indexing']

    if not ready:
        msg = 'Still indexing the rulebooks — please wait.' if indexing else 'Not initialized.'
        return jsonify({'error': msg}), 503

    data = request.get_json() or {}
    question = data.get('question', '').strip()
    if not question:
        return jsonify({'error': 'No question provided.'}), 400

    from .services.embeddings import encode_query
    from .services.llm import stream_answer
    from .services.vectorstore import search

    query_vec = encode_query(question)
    chunks = search(query_vec, top_k=5)
    sources = [
        {'page': c['page'], 'source': c['source'], 'text': c['text'][:350], 'score': c['score']}
        for c in chunks
    ]

    def generate():
        yield f'data: {json.dumps({"type": "sources", "sources": sources})}\n\n'
        yield from stream_answer(question, chunks)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )
