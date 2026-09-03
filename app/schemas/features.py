from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.retrieval import MatchWarning, QueryWarning, RiskWarning


class FeatureValue(BaseModel):
    score: float | None = Field(default=None, ge=0, le=1)
    raw_value: Any = None
    unit: str | None = None
    data_source: str
    as_of: date | None = None
    confidence: float = Field(ge=0, le=1)
    missing: bool = False
    evidence: str


class FeatureDimension(BaseModel):
    score: float | None = Field(default=None, ge=0, le=1)
    components: dict[str, FeatureValue]
    evidence: str


class HistoricalDataAvailability(BaseModel):
    """Business-facing history tier calculated for the current Campaign run."""

    tier: Literal["HISTORY_SUFFICIENT", "HISTORY_LIMITED", "COLD_START"]
    tier_label: str
    effective_history_n: float = Field(ge=0)
    history_reliability: float = Field(ge=0, le=1)
    valid_history_count: int = Field(ge=0)
    primary_kpi: str
    lookback_months: int = 18
    weighting_policy: str


class CandidateFeatureRead(BaseModel):
    feature_snapshot_id: str
    account_id: str
    creator_id: str
    handle: str
    platform: str
    retrieval_rank: int
    keyword_rank: int | None
    vector_rank: int | None
    rrf_score: float
    feature_version: str
    matched_focus_terms: list[str] = Field(default_factory=list)
    matched_campaign_terms: list[str] = Field(default_factory=list)
    historical_data_availability: HistoricalDataAvailability = Field(
        default_factory=lambda: HistoricalDataAvailability(
            tier="HISTORY_SUFFICIENT",
            tier_label="历史充分",
            effective_history_n=3.0,
            history_reliability=1.0,
            valid_history_count=3,
            primary_kpi="unknown",
            weighting_policy="legacy/default",
        )
    )
    content_relevance: FeatureDimension
    audience_fit: FeatureDimension
    performance: FeatureDimension
    cost_efficiency: FeatureDimension
    traffic_quality: FeatureDimension
    delivery_reliability: FeatureDimension
    data_quality: FeatureDimension
    match_warnings: list[MatchWarning] = Field(default_factory=list)
    risk_warnings: list[RiskWarning] = Field(default_factory=list)


class FeatureCalculationResponse(BaseModel):
    campaign_id: str
    query: str
    recommendation_run_id: str
    evaluated_at: datetime
    feature_version: str
    hard_filter_pool_size: int
    hybrid_retrieval_count: int
    feature_count: int
    note: str
    warnings: list[QueryWarning] = Field(default_factory=list)
    candidates: list[CandidateFeatureRead]
