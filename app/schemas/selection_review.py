from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator


class SelectionReviewCreate(BaseModel):
    run_id: str = Field(min_length=1, max_length=40)
    reviewer_name: str = Field(default="业务审核员", min_length=1, max_length=120)


class SelectionReviewItemUpdate(BaseModel):
    action: Literal["include", "exclude", "restore", "set_lock", "resolve_risk"]
    locked: bool | None = None
    reason: str | None = Field(default=None, max_length=1000)
    risk_resolution: Literal["PENDING", "CLEARED", "REJECTED"] | None = None
    actor_name: str = Field(default="业务审核员", min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_action(self) -> Self:
        if self.action == "exclude" and not (self.reason and self.reason.strip()):
            raise ValueError("reason is required when excluding a creator")
        if self.action == "set_lock" and self.locked is None:
            raise ValueError("locked is required for set_lock")
        if self.action == "resolve_risk" and self.risk_resolution is None:
            raise ValueError("risk_resolution is required for resolve_risk")
        return self


class ReviewActionRequest(BaseModel):
    actor_name: str = Field(default="业务审核员", min_length=1, max_length=120)


class SelectionReviewItemRead(BaseModel):
    account_id: str
    handle: str
    platform: str
    final_rank: int
    fit_score: float
    risk_decision: Literal["PASS", "REVIEW"]
    disposition: Literal["INCLUDED", "AVAILABLE", "EXCLUDED"]
    source: Literal["SYSTEM", "OPTIMIZER", "HUMAN"]
    locked: bool
    reason: str | None
    risk_resolution: Literal["NOT_REQUIRED", "PENDING", "CLEARED", "REJECTED"]
    updated_at: datetime


class SelectionReviewRead(BaseModel):
    review_id: str
    run_id: str
    campaign_id: str
    status: Literal["DRAFT", "CONFIRMED"]
    reviewer_name: str
    version: int
    optimization_summary: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    items: list[SelectionReviewItemRead]
