from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    model_name: str
    dimension: int

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

