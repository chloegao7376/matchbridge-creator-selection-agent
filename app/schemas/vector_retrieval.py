from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.retrieval import MatchWarning, QueryWarning, RiskWarning


class VectorCandidate(BaseModel):
    account_id: str
    creator_id: str
    handle: str
    platform: str
    primary_category: str
    style_tags: list[str]
    topic_tags: list[str]
    vector_score: float
    vector_distance: float
    embedding_model: str
    document_generated_at: date
    snippet: str
    match_warnings: list[MatchWarning] = Field(default_factory=list)
    risk_warnings: list[RiskWarning] = Field(default_factory=list)


class VectorSearchResponse(BaseModel):
    query: str
    vector_query_text: str
    campaign_id: str
    recommendation_run_id: str
    evaluated_at: datetime
    embedding_model: str
    hard_filter_applied: bool = True
    eligible_pool_size: int
    total_matches: int
    warnings: list[QueryWarning] = Field(default_factory=list)
    candidates: list[VectorCandidate]
