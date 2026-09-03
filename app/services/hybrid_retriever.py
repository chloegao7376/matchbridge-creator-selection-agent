from __future__ import annotations

from app.schemas.hybrid_retrieval import HybridCandidate
from app.schemas.retrieval import KeywordCandidate
from app.schemas.vector_retrieval import VectorCandidate


def fuse_rrf(
    keyword_candidates: list[KeywordCandidate],
    vector_candidates: list[VectorCandidate],
    *,
    keyword_weight: float = 0.5,
    vector_weight: float = 0.5,
    rrf_k: int = 60,
    limit: int = 20,
) -> list[HybridCandidate]:
    if keyword_weight < 0 or vector_weight < 0 or keyword_weight + vector_weight <= 0:
        raise ValueError("fusion weights must be non-negative and not both zero")
    if rrf_k < 1:
        raise ValueError("rrf_k must be positive")

    entries: dict[str, dict] = {}
    if keyword_weight > 0:
        for rank, candidate in enumerate(keyword_candidates, start=1):
            entries.setdefault(candidate.account_id, {})["keyword"] = (rank, candidate)
    if vector_weight > 0:
        for rank, candidate in enumerate(vector_candidates, start=1):
            entries.setdefault(candidate.account_id, {})["vector"] = (rank, candidate)

    max_score = (keyword_weight + vector_weight) / (rrf_k + 1)
    fused = []
    for account_id, sources in entries.items():
        keyword_entry = sources.get("keyword")
        vector_entry = sources.get("vector")
        reference = keyword_entry[1] if keyword_entry else vector_entry[1]
        raw_score = 0.0
        if keyword_entry:
            raw_score += keyword_weight / (rrf_k + keyword_entry[0])
        if vector_entry:
            raw_score += vector_weight / (rrf_k + vector_entry[0])
        fused.append(
            HybridCandidate(
                account_id=account_id,
                creator_id=reference.creator_id,
                handle=reference.handle,
                platform=reference.platform,
                primary_category=reference.primary_category,
                style_tags=reference.style_tags,
                topic_tags=reference.topic_tags,
                keyword_rank=keyword_entry[0] if keyword_entry else None,
                vector_rank=vector_entry[0] if vector_entry else None,
                keyword_score=keyword_entry[1].keyword_score if keyword_entry else None,
                vector_score=vector_entry[1].vector_score if vector_entry else None,
                rrf_score=round(raw_score / max_score, 6),
                document_generated_at=reference.document_generated_at,
                keyword_evidence=keyword_entry[1].evidence if keyword_entry else None,
                vector_snippet=vector_entry[1].snippet if vector_entry else None,
                match_warnings=(
                    keyword_entry[1].match_warnings if keyword_entry else vector_entry[1].match_warnings
                ),
            )
        )
    return sorted(fused, key=lambda item: (-item.rrf_score, item.account_id))[:limit]
