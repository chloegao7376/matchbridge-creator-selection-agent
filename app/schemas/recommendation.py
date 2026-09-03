from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.budget import BudgetOptimizationSummary
from app.schemas.features import HistoricalDataAvailability
from app.schemas.retrieval import QueryWarning


class RetrievalStageSummary(BaseModel):
    method: Literal["keyword_vector_rrf"] = "keyword_vector_rrf"
    hard_filter_pool_size: int
    retrieved_candidate_count: int
    purpose: str = "根据Campaign上下文和query生成进入特征精算的候选池。"


class FitStageSummary(BaseModel):
    method: str
    includes_retrieval_signals: bool = True
    retrieval_signals: list[str] = Field(
        default_factory=lambda: ["keyword_relevance", "vector_similarity"]
    )
    business_dimensions: list[str] = Field(
        default_factory=lambda: [
            "audience_fit",
            "performance",
            "cost_efficiency",
            "traffic_quality",
            "delivery_reliability",
            "data_quality",
        ]
    )
    dimension_weights: dict[str, float]
    confidence_policy: str
    missing_value_policy: str
    history_weight_policy: str = "历史数据不足时由系统自动调整权重。"
    purpose: str = "对Hybrid召回候选达人进行业务适配度计算。"


class HistoricalDataAvailabilityStageSummary(BaseModel):
    name: str = "historical-data-availability-checker"
    tiers: list[str] = Field(default_factory=lambda: ["历史充分", "历史有限", "完全冷启动"])
    threshold: str = "effective_history_n >= 3为历史充分；0<n<3为历史有限；n=0为完全冷启动。"
    purpose: str = "在Fit前按当前Campaign与主KPI口径判断历史证据可用程度。"


class FinalStageSummary(BaseModel):
    ordering_policy: str = "PASS候选优先于REVIEW候选，同一风险层内按fit_score降序。"
    risk_is_part_of_fit_score: bool = False
    final_candidate_count: int
    purpose: str = "根据风险决策和fit_score产生最终选号优先级。"


class RecommendationStages(BaseModel):
    retrieval: RetrievalStageSummary
    historical_data_availability: HistoricalDataAvailabilityStageSummary = Field(
        default_factory=HistoricalDataAvailabilityStageSummary
    )
    fit: FitStageSummary
    final: FinalStageSummary


class RecommendationReason(BaseModel):
    dimension: str
    statement: str
    evidence_values: dict[str, Any] = Field(default_factory=dict)


class FinalRecommendationCandidate(BaseModel):
    account_id: str
    creator_id: str
    handle: str
    platform: str
    final_rank: int
    fit_score: float = Field(ge=0, le=100)
    risk_decision: Literal["PASS", "REVIEW"]
    selected_in_budget_plan: bool
    historical_data_availability: HistoricalDataAvailability = Field(
        default_factory=lambda: HistoricalDataAvailability(
            tier="HISTORY_SUFFICIENT",
            tier_label="历史充分",
            effective_history_n=3.0,
            history_reliability=1.0,
            valid_history_count=3,
            primary_kpi="unknown",
            weighting_policy="legacy/default",
        )
    )
    why_this_creator: RecommendationReason
    why_in_final_combination: RecommendationReason | None = None
    recommendation_reasons: list[RecommendationReason] = Field(default_factory=list)
    business_notes: list[str] = Field(default_factory=list)


class FinalRecommendationResponse(BaseModel):
    campaign_id: str
    query: str
    recommendation_run_id: str
    evaluated_at: datetime
    stages: RecommendationStages
    budget_optimization: BudgetOptimizationSummary
    warnings: list[QueryWarning] = Field(default_factory=list)
    candidates: list[FinalRecommendationCandidate]
