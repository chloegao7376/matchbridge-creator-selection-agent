from __future__ import annotations

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Platform = Literal["抖音", "小红书", "B站", "微博"]
ContentFormat = Literal["图文", "短视频", "中长视频", "动态", "直播"]
CampaignObjective = Literal["awareness", "engagement", "conversion"]
RiskTolerance = Literal["low", "medium", "high"]
CreatorTier = Literal["nano", "micro", "mid", "macro", "mega"]
GenderPreference = Literal["female", "male", "balanced"]
AgeBand = Literal["under_18", "18_24", "25_34", "35_44", "45_plus"]


PLATFORM_FORMATS: dict[str, set[str]] = {
    "抖音": {"短视频", "直播"},
    "小红书": {"图文", "短视频"},
    "B站": {"中长视频", "动态"},
    "微博": {"图文", "短视频"},
}


class TargetAudience(BaseModel):
    gender_preference: GenderPreference
    primary_age_band: AgeBand
    interest_tags: list[str] = Field(min_length=1, max_length=12)

    model_config = ConfigDict(extra="forbid")


class CampaignBriefPayload(BaseModel):
    brand_name: str = Field(min_length=1, max_length=120)
    product_name: str = Field(min_length=1, max_length=160)
    product_category: str = Field(min_length=1, max_length=64)
    campaign_objective: CampaignObjective
    primary_kpi: str = Field(min_length=1, max_length=64)
    target_platforms: list[Platform] = Field(min_length=1, max_length=4)
    target_regions: list[str] = Field(min_length=1, max_length=20)
    target_audience: TargetAudience
    tone_tags: list[str] = Field(min_length=1, max_length=8)
    required_topics: list[str] = Field(default_factory=list, max_length=12)
    forbidden_topics: list[str] = Field(default_factory=list, max_length=12)
    content_formats: list[ContentFormat] = Field(min_length=1, max_length=5)
    deliverables_per_creator: int = Field(ge=1, le=20)
    campaign_start_at: date
    campaign_end_at: date
    total_budget_cny: int = Field(gt=0, le=100_000_000)
    max_budget_per_creator_cny: int = Field(gt=0, le=50_000_000)
    creator_count: int = Field(ge=1, le=500)
    preferred_creator_tiers: list[CreatorTier] = Field(default_factory=list, max_length=5)
    competitor_brands: list[str] = Field(default_factory=list, max_length=50)
    competitor_exclusion_days: int = Field(ge=0, le=730)
    usage_rights_days: int = Field(ge=0, le=3650)
    exclusivity_required_days: int = Field(ge=0, le=730)
    risk_tolerance: RiskTolerance = "medium"
    brief_text: str = Field(min_length=1, max_length=10_000)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_business_constraints(self) -> Self:
        if self.campaign_end_at < self.campaign_start_at:
            raise ValueError("campaign_end_at must not be earlier than campaign_start_at")
        if self.max_budget_per_creator_cny > self.total_budget_cny:
            raise ValueError("max_budget_per_creator_cny must not exceed total_budget_cny")
        supported_formats = set().union(*(PLATFORM_FORMATS[platform] for platform in self.target_platforms))
        unsupported = set(self.content_formats) - supported_formats
        if unsupported:
            raise ValueError(f"content formats are not supported by selected platforms: {sorted(unsupported)}")
        return self


class CampaignBriefCreate(CampaignBriefPayload):
    pass


class CampaignBriefUpdate(BaseModel):
    brand_name: str | None = Field(default=None, min_length=1, max_length=120)
    product_name: str | None = Field(default=None, min_length=1, max_length=160)
    product_category: str | None = Field(default=None, min_length=1, max_length=64)
    campaign_objective: CampaignObjective | None = None
    primary_kpi: str | None = Field(default=None, min_length=1, max_length=64)
    target_platforms: list[Platform] | None = Field(default=None, min_length=1, max_length=4)
    target_regions: list[str] | None = Field(default=None, min_length=1, max_length=20)
    target_audience: TargetAudience | None = None
    tone_tags: list[str] | None = Field(default=None, min_length=1, max_length=8)
    required_topics: list[str] | None = Field(default=None, max_length=12)
    forbidden_topics: list[str] | None = Field(default=None, max_length=12)
    content_formats: list[ContentFormat] | None = Field(default=None, min_length=1, max_length=5)
    deliverables_per_creator: int | None = Field(default=None, ge=1, le=20)
    campaign_start_at: date | None = None
    campaign_end_at: date | None = None
    total_budget_cny: int | None = Field(default=None, gt=0, le=100_000_000)
    max_budget_per_creator_cny: int | None = Field(default=None, gt=0, le=50_000_000)
    creator_count: int | None = Field(default=None, ge=1, le=500)
    preferred_creator_tiers: list[CreatorTier] | None = Field(default=None, max_length=5)
    competitor_brands: list[str] | None = Field(default=None, max_length=50)
    competitor_exclusion_days: int | None = Field(default=None, ge=0, le=730)
    usage_rights_days: int | None = Field(default=None, ge=0, le=3650)
    exclusivity_required_days: int | None = Field(default=None, ge=0, le=730)
    risk_tolerance: RiskTolerance | None = None
    brief_text: str | None = Field(default=None, min_length=1, max_length=10_000)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CampaignBriefRead(CampaignBriefPayload):
    campaign_id: str
    created_at: date

    model_config = ConfigDict(from_attributes=True, extra="forbid")

