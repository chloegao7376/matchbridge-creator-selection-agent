from datetime import datetime

from pydantic import BaseModel, Field


class EligibilityCandidate(BaseModel):
    account_id: str
    creator_id: str
    handle: str
    platform: str
    creator_tier: str
    follower_count: int
    primary_category: str
    min_compatible_price_cny: int | None
    eligible: bool
    exclusion_reasons: list[str] = Field(default_factory=list)


class EligibilitySummary(BaseModel):
    evaluated_accounts: int
    eligible_accounts: int
    returned_candidates: int
    excluded_by_reason: dict[str, int]


class EligibilityResponse(BaseModel):
    campaign_id: str
    recommendation_run_id: str | None = None
    evaluated_at: datetime
    summary: EligibilitySummary
    candidates: list[EligibilityCandidate]
