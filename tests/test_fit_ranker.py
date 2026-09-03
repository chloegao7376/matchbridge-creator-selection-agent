from datetime import UTC, date, datetime

from app.schemas.features import (
    CandidateFeatureRead,
    FeatureDimension,
    FeatureValue,
    HistoricalDataAvailability,
)
from app.schemas.retrieval import RiskWarning
from app.services.fit_ranker import FitRanker, effective_dimension_weights

DIMENSIONS = (
    "content_relevance",
    "audience_fit",
    "performance",
    "cost_efficiency",
    "traffic_quality",
    "delivery_reliability",
    "data_quality",
)


def feature_dimension(score: float | None, confidence: float = 1.0) -> FeatureDimension:
    return FeatureDimension(
        score=score,
        components={
            "test": FeatureValue(
                score=score,
                raw_value=score,
                data_source="test",
                confidence=confidence,
                missing=score is None,
                evidence="test",
            )
        },
        evidence="test",
    )


def feature_candidate(
    account_id: str,
    *,
    score: float,
    confidence: float = 1.0,
    missing: set[str] | None = None,
    review: bool = False,
    retrieval_rank: int = 1,
    history_tier: str = "HISTORY_SUFFICIENT",
    history_reliability: float = 1.0,
) -> CandidateFeatureRead:
    missing = missing or set()
    dimensions = {
        name: feature_dimension(None if name in missing else score, confidence) for name in DIMENSIONS
    }
    risk_warnings = []
    if review:
        risk_warnings.append(
            RiskWarning(
                code="active_review_risk",
                message="test",
                risk_event_id="risk_test",
                risk_type="content_compliance",
                risk_subtype="test",
                severity="medium",
                confidence=0.9,
                decision="REVIEW",
                review_status="pending",
                observed_at=date(2026, 9, 1),
                expires_at=date(2026, 9, 30),
            )
        )
    return CandidateFeatureRead(
        feature_snapshot_id=f"feature_{account_id}",
        account_id=account_id,
        creator_id=f"creator_{account_id}",
        handle=account_id,
        platform="微博",
        retrieval_rank=retrieval_rank,
        keyword_rank=retrieval_rank,
        vector_rank=retrieval_rank,
        rrf_score=1.0,
        feature_version="test",
        historical_data_availability=HistoricalDataAvailability(
            tier=history_tier,
            tier_label={
                "HISTORY_SUFFICIENT": "历史充分",
                "HISTORY_LIMITED": "历史有限",
                "COLD_START": "完全冷启动",
            }[history_tier],
            effective_history_n=history_reliability * 3,
            history_reliability=history_reliability,
            valid_history_count=0,
            primary_kpi="conversions",
            weighting_policy="test",
        ),
        risk_warnings=risk_warnings,
        **dimensions,
    )


def rank(features):
    return FitRanker(None).rank(
        features,
        run_id="run_test",
        campaign_id="cmp_test",
        evaluated_at=datetime(2026, 9, 1, tzinfo=UTC),
        persist=False,
    )


def test_low_confidence_shrinks_score_toward_neutral_prior():
    high_confidence, low_confidence = rank(
        [
            feature_candidate("high", score=0.9, confidence=1.0),
            feature_candidate("low", score=0.9, confidence=0.2, retrieval_rank=2),
        ]
    )

    assert high_confidence.fit_score == 90.0
    assert low_confidence.fit_score == 58.0


def test_missing_dimension_is_renormalized_and_coverage_penalized():
    complete, incomplete = rank(
        [
            feature_candidate("complete", score=0.8),
            feature_candidate("incomplete", score=0.8, missing={"delivery_reliability"}, retrieval_rank=2),
        ]
    )

    assert complete.fit_score == 80.0
    assert incomplete.fit_score == 77.6
    assert incomplete.feature_coverage == 0.9
    assert incomplete.missing_dimensions == ["delivery_reliability"]


def test_recommendation_rank_puts_pass_before_review_without_changing_fit_rank():
    ranked = rank(
        [
            feature_candidate("review", score=0.9, review=True),
            feature_candidate("pass", score=0.6, retrieval_rank=2),
        ]
    )
    by_account = {candidate.account_id: candidate for candidate in ranked}

    assert by_account["review"].fit_rank == 1
    assert by_account["review"].recommendation_rank == 2
    assert by_account["pass"].fit_rank == 2
    assert by_account["pass"].recommendation_rank == 1


def test_limited_history_releases_performance_weight_by_reliability():
    candidate = feature_candidate(
        "limited",
        score=0.8,
        history_tier="HISTORY_LIMITED",
        history_reliability=0.5,
    )
    weights = effective_dimension_weights(
        candidate,
        {
            "content_relevance": 0.30,
            "audience_fit": 0.20,
            "performance": 0.15,
            "cost_efficiency": 0.10,
            "traffic_quality": 0.10,
            "delivery_reliability": 0.10,
            "data_quality": 0.05,
        },
    )

    assert weights == {
        "content_relevance": 0.33,
        "audience_fit": 0.2225,
        "performance": 0.075,
        "cost_efficiency": 0.10,
        "traffic_quality": 0.115,
        "delivery_reliability": 0.10,
        "data_quality": 0.0575,
    }


def test_cold_start_uses_fixed_weights_and_zero_historical_performance():
    candidate = feature_candidate(
        "cold", score=0.8, history_tier="COLD_START", history_reliability=0.0
    )
    weights = effective_dimension_weights(candidate, {name: 1 / 7 for name in DIMENSIONS})

    assert weights["performance"] == 0.0
    assert weights["content_relevance"] == 0.36
    assert sum(weights.values()) == 1.0
