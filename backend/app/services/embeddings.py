"""Local embedding service using sentence-transformers."""
from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np
import os

# ── Model loaded once at module import (synchronous, one-time) ──
print("[embeddings] Loading model...")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")
_model = SentenceTransformer("all-MiniLM-L6-v2")
print("[embeddings] ✅ Model ready.")


def embed_text(text: str) -> List[float]:
    """Embed a single text string into a 384-dim vector."""
    embedding = _model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed multiple texts in one batch call."""
    embeddings = _model.encode(texts, convert_to_numpy=True)
    return [emb.tolist() for emb in embeddings]
