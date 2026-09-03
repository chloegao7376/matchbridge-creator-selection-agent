import math

from app.embedding.hashing import HashingEmbeddingProvider


def test_hashing_embedding_is_deterministic_normalized_and_versioned():
    provider = HashingEmbeddingProvider(dimension=64, model_name="test_hashing_v1")

    first = provider.embed_query("食品 配料表 成分")
    second = provider.embed_query("食品 配料表 成分")

    assert first == second
    assert len(first) == 64
    assert provider.model_name == "test_hashing_v1"
    assert math.isclose(math.sqrt(sum(value * value for value in first)), 1.0)
    assert first != provider.embed_query("数码 续航 电池")
