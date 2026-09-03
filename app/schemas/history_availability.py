from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.features import HistoricalDataAvailability
from app.schemas.retrieval import MatchWarning, QueryWarning


class HistoricalAvailabilityCandidate(BaseModel):
    account_id: str
    creator_id: str
    handle: str
    platform: str
    retrieval_rank: int
    availability: HistoricalDataAvailability
    warnings: list[MatchWarning] = Field(default_factory=list)


class HistoricalAvailabilityRunResponse(BaseModel):
    campaign_id: str
    query: str
    recommendation_run_id: str
    evaluated_at: datetime
    module_name: str = "historical-data-availability-checker"
    purpose: str = "在Fit前按当前Campaign与主KPI口径判断Hybrid召回候选达人的历史证据可用程度。"
    tier_counts: dict[str, int]
    candidate_count: int
    query_warnings: list[QueryWarning] = Field(default_factory=list)
    candidates: list[HistoricalAvailabilityCandidate]
