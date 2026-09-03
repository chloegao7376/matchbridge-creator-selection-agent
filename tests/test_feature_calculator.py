from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.services.feature_calculator import FeatureCalculator, weighted_score


def test_weighted_score_renormalizes_available_features():
    assert weighted_score([(0.8, 0.5), (None, 0.3), (0.4, 0.2)]) == 0.685714


def test_creator_location_is_recorded_but_not_used_in_audience_score():
    calculator = FeatureCalculator(None)
    brief = SimpleNamespace(
        target_audience={
            "gender_preference": "balanced",
            "primary_age_band": "35_44",
            "interest_tags": ["品质生活", "户外运动"],
        },
        target_regions=["成都"],
    )
    snapshot = SimpleNamespace(
        audience_gender_distribution={"female": 0.45, "male": 0.45, "unknown": 0.10},
        audience_age_distribution={"35_44": 0.30},
        audience_interest_tags=["品质生活"],
        top_regions={"成都": 0.20},
        snapshot_date=date(2026, 8, 31),
        confidence=Decimal("0.90"),
    )
    matching_account = SimpleNamespace(
        region="成都", collected_at=date(2026, 8, 31), data_confidence=Decimal("0.9")
    )
    other_account = SimpleNamespace(
        region="北京", collected_at=date(2026, 8, 31), data_confidence=Decimal("0.9")
    )

    matching = calculator._audience(brief, matching_account, snapshot)
    other = calculator._audience(brief, other_account, snapshot)

    assert matching.score == other.score
    assert matching.components["creator_location_match"].score == 1.0
    assert other.components["creator_location_match"].score == 0.0


def test_cost_uses_deliverables_and_agency_fee():
    calculator = FeatureCalculator(None)
    brief = SimpleNamespace(deliverables_per_creator=2, max_budget_per_creator_cny=10_000)
    rate = SimpleNamespace(
        base_price_cny=2_000,
        agency_fee_rate=Decimal("0.10"),
        content_format="图文",
        valid_from=date(2026, 8, 1),
    )

    result = calculator._cost(brief, None, [rate])

    assert result.components["estimated_cost_cny"].raw_value == 4_400
    assert result.components["budget_headroom"].raw_value == 0.44
    assert result.score == 0.56


def test_primary_kpi_projection_uses_same_category_cohort_prior():
    calculator = FeatureCalculator(None)
    brief = SimpleNamespace(
        primary_kpi="conversions",
        campaign_objective="conversion",
        product_category="食品饮料",
        deliverables_per_creator=2,
    )
    metric = SimpleNamespace(
        engagement_rate_by_followers_30d=Decimal("0.03"),
        median_views_last_30d=100,
        follower_count=1_000,
        snapshot_date=date(2026, 8, 31),
    )
    cohort = [
        SimpleNamespace(
            performance={"views": 1_000, "conversions": 10},
        )
    ]

    result = calculator._performance(brief, metric, [], cohort)
    projection = result.components["expected_primary_kpi_baseline"]

    assert projection.unit == "conversions"
    assert projection.raw_value == 2.0
    assert projection.confidence == 0.6
