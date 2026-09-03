from datetime import UTC, datetime

from app.schemas.budget import BudgetOptimizationSummary
from app.schemas.recommendation import (
    FinalRecommendationCandidate,
    FinalRecommendationResponse,
    FinalStageSummary,
    FitStageSummary,
    RecommendationReason,
    RecommendationStages,
    RetrievalStageSummary,
)


def test_business_response_has_history_stage_and_final_metrics_plus_explanation():
    response = FinalRecommendationResponse(
        campaign_id="cmp_test",
        query="成分",
        recommendation_run_id="run_test",
        evaluated_at=datetime(2026, 9, 2, tzinfo=UTC),
        stages=RecommendationStages(
            retrieval=RetrievalStageSummary(hard_filter_pool_size=20, retrieved_candidate_count=20),
            fit=FitStageSummary(
                method="fit_scoring_v1",
                dimension_weights={"content_relevance": 0.3, "audience_fit": 0.2},
                confidence_policy="test",
                missing_value_policy="test",
            ),
            final=FinalStageSummary(final_candidate_count=20),
        ),
        budget_optimization=BudgetOptimizationSummary(
            staffing_status="FULL",
            primary_kpi="conversions",
            total_budget_cny=100_000,
            target_creator_count=1,
            eligible_candidate_count=1,
            selected_creator_count=1,
            selected_total_cost_cny=10_000,
            remaining_budget_cny=90_000,
            budget_utilization=0.1,
            selected_total_expected_primary_kpi=100,
            selected_average_expected_primary_kpi=100,
            audience_overlap_penalty=10,
            overlap_adjusted_expected_primary_kpi=90,
            selected_total_fit_score=82.5,
            selected_average_fit_score=82.5,
            selected_candidates=[],
        ),
        candidates=[
            FinalRecommendationCandidate(
                account_id="acc_1",
                creator_id="cr_1",
                handle="测试达人",
                platform="微博",
                final_rank=1,
                fit_score=82.5,
                risk_decision="PASS",
                selected_in_budget_plan=True,
                why_this_creator=RecommendationReason(
                    dimension="candidate_selection",
                    statement="业务适配度较高。",
                ),
                why_in_final_combination=RecommendationReason(
                    dimension="portfolio_selection",
                    statement="有助于提升组合目标。",
                ),
            )
        ],
    )
    payload = response.model_dump(mode="json")

    assert list(payload["stages"]) == [
        "retrieval",
        "historical_data_availability",
        "fit",
        "final",
    ]
    assert (
        payload["stages"]["historical_data_availability"]["name"]
        == "historical-data-availability-checker"
    )
    assert (
        payload["budget_optimization"]["objective"]
        == "maximize_overlap_adjusted_expected_primary_kpi"
    )
    assert payload["stages"]["fit"]["includes_retrieval_signals"] is True
    assert payload["stages"]["fit"]["retrieval_signals"] == [
        "keyword_relevance",
        "vector_similarity",
    ]
    assert set(payload["candidates"][0]) == {
        "account_id",
        "creator_id",
        "handle",
        "platform",
        "final_rank",
        "fit_score",
        "risk_decision",
            "selected_in_budget_plan",
            "historical_data_availability",
        "why_this_creator",
        "why_in_final_combination",
        "recommendation_reasons",
        "business_notes",
    }
