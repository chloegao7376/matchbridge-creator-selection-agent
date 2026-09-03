from typing import Literal

from pydantic import BaseModel, Field


class BudgetSelectedCandidate(BaseModel):
    account_id: str
    creator_id: str
    handle: str
    platform: str
    final_rank: int
    fit_score: float = Field(ge=0, le=100)
    estimated_cost_cny: float = Field(gt=0)
    primary_kpi: str
    baseline_expected_primary_kpi: float = Field(ge=0)
    campaign_transfer_factor: float = Field(ge=0, le=1)
    confidence_factor: float = Field(ge=0, le=1)
    expected_primary_kpi: float = Field(ge=0)
    average_audience_similarity_to_selected: float = Field(ge=0, le=1)
    overlap_penalty_contribution: float = Field(ge=0)


class BudgetOptimizationSummary(BaseModel):
    method: Literal["beam_search_quadratic_v3"] = "beam_search_quadratic_v3"
    objective: Literal["maximize_overlap_adjusted_expected_primary_kpi"] = (
        "maximize_overlap_adjusted_expected_primary_kpi"
    )
    objective_review: str = (
        "v3在总预算和人数上限内最大化适配、置信及受众重叠代理修正后的预期主KPI；"
        "audience_overlap基于受众分布代理估计，不是真实粉丝去重结果。"
    )
    candidate_scope: Literal["retrieved_pass_candidates_with_valid_cost_and_kpi"] = (
        "retrieved_pass_candidates_with_valid_cost_and_kpi"
    )
    solution_status: Literal["HEURISTIC"] = "HEURISTIC"
    staffing_status: Literal["FULL", "PARTIAL", "EMPTY"]
    primary_kpi: str
    suitability_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "content_relevance": 0.50,
            "audience_fit": 0.35,
            "traffic_quality": 0.10,
            "delivery_reliability": 0.05,
        }
    )
    audience_similarity_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "age_distribution_overlap": 0.35,
            "region_distribution_overlap": 0.30,
            "interest_tag_similarity": 0.20,
            "gender_distribution_overlap": 0.15,
        }
    )
    audience_overlap_is_proxy: Literal[True] = True
    audience_overlap_disclaimer: str = (
        "audience_overlap是基于受众分布的代理估计，不是真实粉丝去重结果；"
        "获得平台侧去重触达数据后应替换为真正的边际KPI模型。"
    )
    overlap_penalty_formula: str = (
        "sum(similarity_ij * min(expected_kpi_i, expected_kpi_j)) / max(target_creator_count - 1, 1)"
    )
    total_budget_cny: float = Field(gt=0)
    target_creator_count: int = Field(ge=1)
    eligible_candidate_count: int = Field(ge=0)
    selected_creator_count: int = Field(ge=0)
    selected_total_cost_cny: float = Field(ge=0)
    remaining_budget_cny: float = Field(ge=0)
    budget_utilization: float = Field(ge=0, le=1)
    selected_total_expected_primary_kpi: float = Field(ge=0)
    selected_average_expected_primary_kpi: float = Field(ge=0)
    audience_overlap_penalty: float = Field(ge=0)
    overlap_adjusted_expected_primary_kpi: float = Field(ge=0)
    selected_total_fit_score: float = Field(ge=0)
    selected_average_fit_score: float = Field(ge=0, le=100)
    selected_candidates: list[BudgetSelectedCandidate]
    warnings: list[str] = Field(default_factory=list)
