from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.brief import CampaignBriefCreate


def valid_payload() -> dict:
    return {
        "brand_name": "澄光护肤",
        "product_name": "澄光护肤新品",
        "product_category": "美妆个护",
        "campaign_objective": "engagement",
        "primary_kpi": "engagements",
        "target_platforms": ["小红书"],
        "target_regions": ["上海", "杭州"],
        "target_audience": {
            "gender_preference": "female",
            "primary_age_band": "25_34",
            "interest_tags": ["品质生活", "健康"],
        },
        "tone_tags": ["知性温柔"],
        "required_topics": ["成分"],
        "forbidden_topics": ["夸大承诺"],
        "content_formats": ["图文"],
        "deliverables_per_creator": 1,
        "campaign_start_at": date(2026, 10, 1),
        "campaign_end_at": date(2026, 10, 31),
        "total_budget_cny": 150_000,
        "max_budget_per_creator_cny": 30_000,
        "creator_count": 5,
        "preferred_creator_tiers": ["micro", "mid"],
        "competitor_brands": ["微澜美研"],
        "competitor_exclusion_days": 60,
        "usage_rights_days": 30,
        "exclusivity_required_days": 14,
        "risk_tolerance": "low",
        "brief_text": "为国货美妆新品选择小红书达人。",
    }


def test_valid_campaign_brief() -> None:
    brief = CampaignBriefCreate.model_validate(valid_payload())
    assert brief.total_budget_cny == 150_000


def test_rejects_invalid_date_range() -> None:
    payload = valid_payload()
    payload["campaign_end_at"] = date(2026, 9, 30)
    with pytest.raises(ValidationError, match="campaign_end_at"):
        CampaignBriefCreate.model_validate(payload)


def test_rejects_platform_format_mismatch() -> None:
    payload = valid_payload()
    payload["content_formats"] = ["直播"]
    with pytest.raises(ValidationError, match="not supported"):
        CampaignBriefCreate.model_validate(payload)


def test_rejects_per_creator_budget_above_total() -> None:
    payload = valid_payload()
    payload["max_budget_per_creator_cny"] = 200_000
    with pytest.raises(ValidationError, match="must not exceed"):
        CampaignBriefCreate.model_validate(payload)
