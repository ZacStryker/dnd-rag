import os
import sqlite3

import numpy as np
import sqlite_vec

_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'vectors.db')
_DIMS = 384


def _db_path() -> str:
    return os.path.abspath(_DB_PATH)


def _connect() -> sqlite3.Connection:
    db = sqlite3.connect(_db_path(), check_same_thread=False)
    db.execute('PRAGMA journal_mode=WAL')
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    return db


def _serialize(arr: np.ndarray) -> bytes:
    return arr.astype(np.float32).tobytes()


def init_db() -> None:
    """Create tables if they don't exist."""
    db = _connect()
    db.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            text        TEXT    NOT NULL,
            page_number INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            source      TEXT    NOT NULL DEFAULT ''
        )
    """)
    db.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunk_embeddings
        USING vec0(embedding float[{_DIMS}])
    """)
    db.commit()
    db.close()


def insert_chunks(chunks: list[dict], embeddings: np.ndarray, source: str) -> None:
    """Insert chunks and their embeddings for a given source label."""
    db = _connect()
    for chunk, emb in zip(chunks, embeddings):
        cursor = db.execute(
            'INSERT INTO chunks(text, page_number, chunk_index, source) VALUES (?, ?, ?, ?)',
            (chunk['text'], chunk['page'], chunk['chunk_index'], source),
        )
        chunk_id = cursor.lastrowid
        db.execute(
            'INSERT INTO chunk_embeddings(rowid, embedding) VALUES (?, ?)',
            (chunk_id, _serialize(emb)),
        )
    db.commit()
    db.close()


def search(query_embedding: np.ndarray, top_k: int = 5) -> list[dict]:
    """Return the top-k most similar chunks for a query embedding."""
    db = _connect()
    rows = db.execute("""
        SELECT c.id, c.text, c.page_number, c.source, knn.distance
        FROM (
            SELECT rowid, distance
            FROM chunk_embeddings
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
        ) knn
        JOIN chunks c ON c.id = knn.rowid
        ORDER BY knn.distance
    """, (_serialize(query_embedding), top_k)).fetchall()
    db.close()
    return [
        {'id': r[0], 'text': r[1], 'page': r[2], 'source': r[3], 'score': round(float(r[4]), 4)}
        for r in rows
    ]


def search_per_source(query_embedding: np.ndarray, top_k_per_source: int = 2) -> list[dict]:
    """Return top-k chunks per source, sorted by relevance within each source."""
    sources = get_indexed_sources()
    db = _connect()
    results = []
    for source in sources:
        rows = db.execute("""
            SELECT c.id, c.text, c.page_number, c.source, knn.distance
            FROM (
                SELECT rowid, distance
                FROM chunk_embeddings
                WHERE embedding MATCH ?
                ORDER BY distance
                LIMIT ?
            ) knn
            JOIN chunks c ON c.id = knn.rowid AND c.source = ?
            ORDER BY knn.distance
            LIMIT ?
        """, (_serialize(query_embedding), 200, source, top_k_per_source)).fetchall()
        results.extend(rows)
    db.close()
    results.sort(key=lambda r: r[4])
    return [
        {'id': r[0], 'text': r[1], 'page': r[2], 'source': r[3], 'score': round(float(r[4]), 4)}
        for r in results
    ]


def get_indexed_sources() -> set[str]:
    """Return the set of source labels currently in the DB."""
    if not os.path.exists(_db_path()):
        return set()
    try:
        db = _connect()
        rows = db.execute('SELECT DISTINCT source FROM chunks').fetchall()
        db.close()
        return {r[0] for r in rows}
    except Exception:
        return set()


def get_chunk_count() -> int:
    """Return total number of indexed chunks, or 0 if DB doesn't exist."""
    if not os.path.exists(_db_path()):
        return 0
    try:
        db = _connect()
        count = db.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]
        db.close()
        return int(count)
    except Exception:
        return 0
