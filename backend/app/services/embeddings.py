"""Local embedding service using sentence-transformers."""
from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np

# Load model once at module import (lazy singleton)
_model = None


def get_model() -> SentenceTransformer:
    """Lazy-load the embedding model with extended timeout."""
    global _model
    if _model is None:
        # Increase HF download timeout (default is 10s, bump to 120s)
        import os
        os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> List[float]:
    """Embed a single text string into a 384-dim vector."""
    model = get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed multiple texts in one batch call."""
    model = get_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return [emb.tolist() for emb in embeddings]
