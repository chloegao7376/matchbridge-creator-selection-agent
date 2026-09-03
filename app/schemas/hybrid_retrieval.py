from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.retrieval import KeywordEvidence, MatchWarning, QueryWarning, RiskWarning


class HybridCandidate(BaseModel):
    account_id: str
    creator_id: str
    handle: str
    platform: str
    primary_category: str
    style_tags: list[str]
    topic_tags: list[str]
    keyword_rank: int | None = None
    vector_rank: int | None = None
    keyword_score: float | None = None
    vector_score: float | None = None
    rrf_score: float
    document_generated_at: date
    keyword_evidence: KeywordEvidence | None = None
    vector_snippet: str | None = None
    match_warnings: list[MatchWarning] = Field(default_factory=list)
    risk_warnings: list[RiskWarning] = Field(default_factory=list)


class HybridSearchResponse(BaseModel):
    query: str
    campaign_id: str
    recommendation_run_id: str
    evaluated_at: datetime
    embedding_model: str
    hard_filter_applied: bool = True
    eligible_pool_size: int
    keyword_matches: int
    vector_matches: int
    fusion_config: dict[str, float]
    warnings: list[QueryWarning] = Field(default_factory=list)
    candidates: list[HybridCandidate]
