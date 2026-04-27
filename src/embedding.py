import os

import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = os.getenv("SBERT_MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        try:
            _MODEL = SentenceTransformer(MODEL_NAME, local_files_only=True)
        except Exception:
            _MODEL = SentenceTransformer(MODEL_NAME)
    return _MODEL


def generate_embeddings(texts):
    """Generate SBERT embeddings for sentence-level texts."""
    texts = [str(text) for text in texts if str(text).strip()]
    if not texts:
        raise ValueError("임베딩할 문장이 없습니다.")

    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(embeddings)
