import numpy as np
from sentence_transformers import SentenceTransformer

_model = None
_MODEL_NAME = 'all-MiniLM-L6-v2'


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def encode(texts: list[str]) -> np.ndarray:
    """Encode a list of texts into L2-normalized 384-dim float32 embeddings."""
    model = _get_model()
    return model.encode(
        texts,
        batch_size=64,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)


def encode_query(text: str) -> np.ndarray:
    """Encode a single query string."""
    return encode([text])[0]
