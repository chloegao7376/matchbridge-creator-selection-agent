from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.features import CandidateFeatureRead
from app.schemas.retrieval import QueryWarning


class DimensionContribution(BaseModel):
    weight: float
    raw_score: float | None
    confidence: float
    confidence_adjusted_score: float | None
    contribution_points: float
    missing: bool


class RankedCandidate(BaseModel):
    score_snapshot_id: str
    account_id: str
    creator_id: str
    handle: str
    platform: str
    retrieval_rank: int
    fit_rank: int
    recommendation_rank: int
    fit_score: float = Field(ge=0, le=100)
    feature_coverage: float = Field(ge=0, le=1)
    overall_confidence: float = Field(ge=0, le=1)
    missing_dimensions: list[str]
    risk_decision: Literal["PASS", "REVIEW"]
    dimension_contributions: dict[str, DimensionContribution]
    score_explanation: list[str]
    features: CandidateFeatureRead


class FitRankingResponse(BaseModel):
    campaign_id: str
    query: str
    recommendation_run_id: str
    evaluated_at: datetime
    scoring_version: str
    dimension_weights: dict[str, float]
    confidence_policy: str
    missing_value_policy: str
    hard_filter_pool_size: int
    ranked_candidate_count: int
    warnings: list[QueryWarning] = Field(default_factory=list)
    candidates: list[RankedCandidate]
