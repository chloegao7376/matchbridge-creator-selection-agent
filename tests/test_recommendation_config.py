import pytest
from pydantic import ValidationError

from app.main import app
from app.schemas.recommendation_config import FitRunRequest, RecommendationRunRequest
from app.services.fit_ranker import DIMENSION_WEIGHTS

CUSTOM_WEIGHTS = {
    "content_relevance": 0.40,
    "audience_fit": 0.20,
    "performance": 0.10,
    "cost_efficiency": 0.10,
    "traffic_quality": 0.05,
    "delivery_reliability": 0.10,
    "data_quality": 0.05,
}


def test_minimal_request_uses_default_retrieval_and_fit_settings():
    request = RecommendationRunRequest(
        campaign_id="cmp_0001",
        query="配料表",
        candidate_count=50,
    )

    assert request.retrieval_advanced.keyword_weight == 0.5
    assert request.retrieval_advanced.vector_weight == 0.5
    assert request.retrieval_advanced.retrieval_depth == 100
    assert request.retrieval_advanced.rrf_k == 60
    assert request.fit.mode == "default"
    assert request.fit.weights is None


def test_custom_mode_requires_complete_weights_that_sum_to_one():
    request = RecommendationRunRequest(
        campaign_id="cmp_0001",
        query="配料表",
        candidate_count=20,
        fit={"mode": "custom", "weights": CUSTOM_WEIGHTS},
    )

    assert request.fit.mode == "custom"
    assert request.fit.weights.model_dump() == CUSTOM_WEIGHTS


@pytest.mark.parametrize(
    "fit",
    [
        {"mode": "custom"},
        {"mode": "default", "weights": CUSTOM_WEIGHTS},
        {"mode": "custom", "weights": {**CUSTOM_WEIGHTS, "content_relevance": 0.30}},
    ],
)
def test_invalid_fit_mode_or_weight_configuration_is_rejected(fit):
    with pytest.raises(ValidationError):
        RecommendationRunRequest(
            campaign_id="cmp_0001",
            query="配料表",
            candidate_count=20,
            fit=fit,
        )


def test_per_channel_retrieval_limit_must_cover_candidate_count():
    with pytest.raises(ValidationError, match="retrieval_depth"):
        RecommendationRunRequest(
            campaign_id="cmp_0001",
            query="配料表",
            candidate_count=50,
            retrieval_advanced={"retrieval_depth": 20},
        )


def test_fit_request_contains_only_business_inputs_and_fit_settings():
    request = FitRunRequest(
        campaign_id="cmp_0001",
        query="配料表",
        candidate_count=20,
    )

    assert request.fit.mode == "default"
    assert request.fit.weights is None
    assert DIMENSION_WEIGHTS == {
        "content_relevance": 0.30,
        "audience_fit": 0.20,
        "performance": 0.15,
        "cost_efficiency": 0.10,
        "traffic_quality": 0.10,
        "delivery_reliability": 0.10,
        "data_quality": 0.05,
    }


def test_fit_request_rejects_retrieval_advanced_settings():
    with pytest.raises(ValidationError):
        FitRunRequest(
            campaign_id="cmp_0001",
            query="配料表",
            retrieval_advanced={"keyword_weight": 1.0},
        )


def test_openapi_separates_retrieval_fit_recommendations_and_legacy_audit():
    paths = app.openapi()["paths"]

    assert paths["/api/retrieval/hybrid"]["get"]["tags"] == ["retrieval"]
    fit_operation = paths["/api/fit/calculate"]["post"]
    assert fit_operation["tags"] == ["fit"]
    assert fit_operation["summary"] == "对Hybrid召回候选达人进行业务适配度计算"
    fit_examples = fit_operation["requestBody"]["content"]["application/json"]["examples"]
    assert set(fit_examples) == {"default", "custom"}
    assert fit_examples["default"]["value"]["fit"] == {"mode": "default"}
    assert fit_examples["custom"]["value"]["fit"]["weights"] == {
        "content_relevance": 0.30,
        "audience_fit": 0.20,
        "performance": 0.15,
        "cost_efficiency": 0.10,
        "traffic_quality": 0.10,
        "delivery_reliability": 0.10,
        "data_quality": 0.05,
    }
    recommendation_operation = paths["/api/recommendations/ranked"]["post"]
    assert recommendation_operation["tags"] == ["recommendations"]
    recommendation_examples = recommendation_operation["requestBody"]["content"]["application/json"][
        "examples"
    ]
    assert recommendation_examples["default"]["value"]["fit"] == {"mode": "default"}
    assert recommendation_examples["custom"]["value"]["fit"]["weights"] == {
        "content_relevance": 0.30,
        "audience_fit": 0.20,
        "performance": 0.15,
        "cost_efficiency": 0.10,
        "traffic_quality": 0.10,
        "delivery_reliability": 0.10,
        "data_quality": 0.05,
    }
    legacy = paths["/api/recommendations/features"]["get"]
    assert legacy["tags"] == ["internal-audit"]
    assert legacy["deprecated"] is True


def test_openapi_exposes_historical_data_availability_module():
    operation = app.openapi()["paths"]["/api/historical-data-availability-checker/check"]["post"]

    assert operation["summary"] == "historical-data-availability-checker"
    assert operation["tags"] == ["historical-data-availability-checker"]
