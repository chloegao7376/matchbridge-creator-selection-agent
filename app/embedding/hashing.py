from __future__ import annotations

import hashlib
import math
import re

from app.embedding.base import EmbeddingProvider

WHITESPACE = re.compile(r"\s+")


class HashingEmbeddingProvider(EmbeddingProvider):
    """Dependency-free deterministic baseline, not a learned semantic model."""

    def __init__(self, *, dimension: int, model_name: str) -> None:
        if dimension <= 0:
            raise ValueError("embedding dimension must be positive")
        self.dimension = dimension
        self.model_name = model_name

    def _embed(self, text: str) -> list[float]:
        normalized = WHITESPACE.sub(" ", text.strip().lower())
        vector = [0.0] * self.dimension
        for ngram_size, weight in ((1, 0.55), (2, 1.0), (3, 1.2)):
            if len(normalized) < ngram_size:
                continue
            for index in range(len(normalized) - ngram_size + 1):
                ngram = normalized[index : index + ngram_size]
                if ngram.isspace():
                    continue
                digest = hashlib.blake2b(ngram.encode("utf-8"), digest_size=8).digest()
                bucket = int.from_bytes(digest[:4], "big") % self.dimension
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[bucket] += sign * weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]
