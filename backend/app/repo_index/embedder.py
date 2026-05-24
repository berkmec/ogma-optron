"""fastembed wrapper.

fastembed ships ONNX models that run on CPU with no torch dependency. The
default model (BAAI/bge-small-en-v1.5, 384-dim, ~130 MB) is small enough to
keep the install footprint reasonable while still being strong on code +
prose retrieval.

The embedder is a process-wide singleton: model load is ~1-2 s, we do not
want to pay that on every index call.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import numpy as np
from fastembed import TextEmbedding

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384


@lru_cache(maxsize=2)
def _engine(model_name: str = DEFAULT_MODEL) -> TextEmbedding:
    return TextEmbedding(model_name=model_name)


def embed_texts(
    texts: Iterable[str], model_name: str = DEFAULT_MODEL
) -> np.ndarray:
    """Return an (n, EMBED_DIM) float32 matrix. fastembed already L2-normalizes."""
    items = list(texts)
    if not items:
        return np.zeros((0, EMBED_DIM), dtype=np.float32)
    vectors = list(_engine(model_name).embed(items))
    return np.asarray(vectors, dtype=np.float32)


def embed_query(text: str, model_name: str = DEFAULT_MODEL) -> np.ndarray:
    """Return a (EMBED_DIM,) float32 vector for a single query."""
    if not text.strip():
        return np.zeros((EMBED_DIM,), dtype=np.float32)
    vectors = list(_engine(model_name).query_embed([text]))
    return np.asarray(vectors[0], dtype=np.float32)
