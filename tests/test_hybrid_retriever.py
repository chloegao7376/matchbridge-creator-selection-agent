from datetime import date

from app.schemas.retrieval import KeywordCandidate, KeywordEvidence
from app.schemas.vector_retrieval import VectorCandidate
from app.services.hybrid_retriever import fuse_rrf


def keyword_candidate(account_id: str, score: float) -> KeywordCandidate:
    return KeywordCandidate(
        account_id=account_id,
        creator_id=f"creator_{account_id}",
        handle=account_id,
        platform="微博",
        primary_category="食品饮料",
        style_tags=["测评"],
        topic_tags=["配料表"],
        campaign_base_score=0.8,
        user_focus_score=score,
        keyword_score=score,
        document_generated_at=date(2026, 8, 31),
        evidence=KeywordEvidence(snippet="evidence"),
    )


def vector_candidate(account_id: str, score: float) -> VectorCandidate:
    return VectorCandidate(
        account_id=account_id,
        creator_id=f"creator_{account_id}",
        handle=account_id,
        platform="微博",
        primary_category="食品饮料",
        style_tags=["测评"],
        topic_tags=["配料表"],
        vector_score=score,
        vector_distance=1 - score,
        embedding_model="test",
        document_generated_at=date(2026, 8, 31),
        snippet="vector evidence",
    )


def test_rrf_rewards_candidates_recalled_by_both_channels():
    fused = fuse_rrf(
        [keyword_candidate("both", 0.9), keyword_candidate("keyword_only", 0.8)],
        [vector_candidate("both", 0.7), vector_candidate("vector_only", 0.6)],
    )

    assert [candidate.account_id for candidate in fused] == ["both", "keyword_only", "vector_only"]
    assert fused[0].keyword_rank == 1
    assert fused[0].vector_rank == 1
    assert fused[0].rrf_score == 1.0


def test_zero_weight_removes_that_retrieval_channel():
    fused = fuse_rrf(
        [keyword_candidate("keyword_only", 0.9)],
        [vector_candidate("vector_only", 0.9)],
        keyword_weight=0,
        vector_weight=1,
    )

    assert [candidate.account_id for candidate in fused] == ["vector_only"]
