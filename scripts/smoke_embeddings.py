"""Manual smoke test for Dispatch's local sentence embedding provider."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.embeddings import LocalSentenceEmbeddingProvider


if __name__ == "__main__":
    texts = [
        "Python 3.14 is released",
        "A new version of Python has shipped",
        "Spacecraft reaches Mars",
    ]
    embeddings = LocalSentenceEmbeddingProvider().embed(texts)
    print(f"Generated {len(embeddings)} embeddings with {len(embeddings[0])} dimensions.")
