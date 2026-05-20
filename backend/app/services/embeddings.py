"""Local embedding service using sentence-transformers."""
from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np
import os
import threading

# ── Model loading with background thread + readiness flag ──
_model = None
_model_ready = threading.Event()
_model_error = None

def _load_model_async():
    """Download/load model in background. Sets _model_ready when done."""
    global _model, _model_error
    try:
        os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")
        print("[embeddings] Loading model (background)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[embeddings] ✅ Model ready.")
        _model_ready.set()
    except Exception as e:
        _model_error = e
        print(f"[embeddings] ⚠️ Model load failed: {e}")
        _model_ready.set()  # Unblock waiters so they can raise the error

# Start background load immediately on module import
threading.Thread(target=_load_model_async, daemon=True).start()


def get_model() -> SentenceTransformer:
    """Return the loaded model, waiting for background load if needed."""
    global _model, _model_error
    _model_ready.wait()  # Block until background thread finishes
    if _model_error:
        raise RuntimeError(f"Model failed to load: {_model_error}")
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
