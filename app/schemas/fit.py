from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.retrieval import QueryWarning


class FitDimensionResult(BaseModel):
    score: float | None
    weight: float
    contribution_points: float
    missing: bool


class FitCandidateResult(BaseModel):
    account_id: str
    creator_id: str
    handle: str
    platform: str
    retrieval_rank: int
    fit_rank: int
    fit_score: float = Field(ge=0, le=100)
    feature_coverage: float = Field(ge=0, le=1)
    overall_confidence: float = Field(ge=0, le=1)
    dimensions: dict[str, FitDimensionResult]


class FitRunResponse(BaseModel):
    campaign_id: str
    query: str
    recommendation_run_id: str
    evaluated_at: datetime
    mode: str
    scoring_version: str
    effective_weights: dict[str, float]
    confidence_policy: str
    missing_value_policy: str
    candidate_count: int
    warnings: list[QueryWarning] = Field(default_factory=list)
    candidates: list[FitCandidateResult]
