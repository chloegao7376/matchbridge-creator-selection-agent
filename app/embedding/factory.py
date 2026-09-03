from functools import lru_cache

from app.core.config import get_settings
from app.embedding.base import EmbeddingProvider
from app.embedding.hashing import HashingEmbeddingProvider


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "hashing":
        return HashingEmbeddingProvider(
            dimension=settings.embedding_dimension,
            model_name=settings.embedding_model,
        )
    raise ValueError(f"unsupported embedding provider: {settings.embedding_provider}")

