from datetime import date, datetime

from pydantic import BaseModel, Field


class KeywordEvidence(BaseModel):
    matched_terms: list[str] = Field(default_factory=list)
    matched_expanded_terms: list[str] = Field(default_factory=list)
    campaign_base_matched_terms: list[str] = Field(default_factory=list)
    matched_fields: dict[str, list[str]] = Field(default_factory=dict)
    snippet: str


class KeywordCandidate(BaseModel):
    account_id: str
    creator_id: str
    handle: str
    platform: str
    primary_category: str
    style_tags: list[str]
    topic_tags: list[str]
    campaign_base_score: float | None
    user_focus_score: float
    keyword_score: float
    document_generated_at: date
    evidence: KeywordEvidence
    match_warnings: list["MatchWarning"] = Field(default_factory=list)
    risk_warnings: list["RiskWarning"] = Field(default_factory=list)


class QueryWarning(BaseModel):
    code: str
    message: str
    campaign_category: str
    conflicting_terms: list[str]
    detected_categories: list[str]
    suggested_query: str


class MatchWarning(BaseModel):
    code: str
    message: str
    query_terms: list[str]


class RiskWarning(BaseModel):
    code: str
    message: str
    risk_event_id: str
    risk_type: str
    risk_subtype: str
    severity: str
    confidence: float
    decision: str
    review_status: str
    observed_at: date
    expires_at: date | None


class KeywordSearchResponse(BaseModel):
    query: str
    parsed_terms: list[str]
    query_expansions: dict[str, list[str]] = Field(default_factory=dict)
    campaign_base_terms: list[str] = Field(default_factory=list)
    score_weights: dict[str, float] = Field(default_factory=dict)
    campaign_id: str | None
    recommendation_run_id: str | None = None
    evaluated_at: datetime | None = None
    hard_filter_applied: bool
    eligible_pool_size: int | None
    total_matches: int
    warnings: list[QueryWarning] = Field(default_factory=list)
    candidates: list[KeywordCandidate]
