from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.briefs import BriefRepository
from app.repositories.recommendation_runs import RecommendationRunRepository
from app.schemas.features import FeatureCalculationResponse
from app.schemas.recommendation import (
    FinalRecommendationCandidate,
    FinalRecommendationResponse,
    FinalStageSummary,
    FitStageSummary,
    HistoricalDataAvailabilityStageSummary,
    RecommendationStages,
    RetrievalStageSummary,
)
from app.schemas.recommendation_config import RecommendationRunRequest
from app.services.budget_optimizer import BudgetOptimizer
from app.services.feature_calculator import FEATURE_VERSION, resolve_primary_kpi
from app.services.fit_ranker import (
    CONFIDENCE_POLICY,
    DIMENSION_WEIGHTS,
    HISTORY_WEIGHT_POLICY,
    MISSING_VALUE_POLICY,
    FitRanker,
    scoring_version_for,
)
from app.services.recommendation_explainer import (
    build_business_explanation,
    build_selection_explanations,
)
from app.services.recommendation_pipeline import RecommendationPipeline

router = APIRouter(prefix="/api/recommendations")
DbSession = Annotated[Session, Depends(get_db)]
RecommendationPayload = Annotated[
    RecommendationRunRequest,
    Body(
        openapi_examples={
            "default": {
                "summary": "default：使用系统默认召回与fit权重",
                "value": {
                    "campaign_id": "cmp_0001",
                    "query": "配料表",
                    "candidate_count": 50,
                    "retrieval_advanced": {
                        "keyword_weight": 0.5,
                        "vector_weight": 0.5,
                        "retrieval_depth": 100,
                        "rrf_k": 60,
                    },
                    "fit": {"mode": "default"},
                },
            },
            "custom": {
                "summary": "custom：自定义七维fit权重",
                "description": "七维权重必须全部提交且合计为1。",
                "value": {
                    "campaign_id": "cmp_0001",
                    "query": "配料表",
                    "candidate_count": 50,
                    "retrieval_advanced": {
                        "keyword_weight": 0.5,
                        "vector_weight": 0.5,
                        "retrieval_depth": 100,
                        "rrf_k": 60,
                    },
                    "fit": {
                        "mode": "custom",
                        "weights": {
                            "content_relevance": 0.30,
                            "audience_fit": 0.20,
                            "performance": 0.15,
                            "cost_efficiency": 0.10,
                            "traffic_quality": 0.10,
                            "delivery_reliability": 0.10,
                            "data_quality": 0.05,
                        },
                    },
                },
            },
        }
    ),
]


def execute_ranking(
    db: Session,
    *,
    campaign_id: str,
    query: str,
    candidate_count: int,
    retrieval_depth: int,
    keyword_weight: float,
    vector_weight: float,
    rrf_k: int,
    fit_mode: str,
    dimension_weights: dict[str, float],
) -> FinalRecommendationResponse:
    brief = BriefRepository(db).get(campaign_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="campaign brief not found")
    effective_scoring_version = scoring_version_for(fit_mode, dimension_weights)
    primary_kpi = resolve_primary_kpi(brief)
    retrieval_config = {
        "keyword_weight": keyword_weight,
        "vector_weight": vector_weight,
        "retrieval_depth": retrieval_depth,
        "rrf_k": rrf_k,
        "candidate_count": candidate_count,
    }
    fit_config = {
        "mode": fit_mode,
        "weights": dimension_weights,
        "scoring_version": effective_scoring_version,
        "confidence_policy": CONFIDENCE_POLICY,
        "missing_value_policy": MISSING_VALUE_POLICY,
        "risk_policy_editable": False,
    }
    run_repository = RecommendationRunRepository(db)
    run = run_repository.create(
        campaign_id=campaign_id,
        run_type="fit_ranking",
        query_text=query,
        keyword_weight_config={
            "keyword_weight": keyword_weight,
            "vector_weight": vector_weight,
            "rrf_k": float(rrf_k),
            "campaign_base": 0.4,
            "user_focus": 0.6,
        },
        retrieval_config=retrieval_config,
        fit_config=fit_config,
        budget_config={
            "method": "beam_search_quadratic_v3",
            "objective": "maximize_overlap_adjusted_expected_primary_kpi",
            "primary_kpi": primary_kpi,
            "total_budget_cny": brief.total_budget_cny,
            "target_creator_count": brief.creator_count,
            "risk_eligibility": "PASS_only",
        },
    )
    try:
        pipeline_result = RecommendationPipeline(db).calculate_features(
            brief,
            query,
            run_id=run.run_id,
            evaluated_at=run.evaluated_at,
            top_k=candidate_count,
            retrieval_depth=retrieval_depth,
            keyword_weight=keyword_weight,
            vector_weight=vector_weight,
            rrf_k=rrf_k,
        )
        ranked = FitRanker(db).rank(
            pipeline_result.features,
            run_id=run.run_id,
            campaign_id=campaign_id,
            evaluated_at=run.evaluated_at,
            dimension_weights=dimension_weights,
            scoring_version=effective_scoring_version,
        )
        budget_optimization = BudgetOptimizer().optimize(
            ranked,
            total_budget_cny=brief.total_budget_cny,
            target_creator_count=brief.creator_count,
            primary_kpi=primary_kpi,
        )
        run.budget_config = budget_optimization.model_dump(mode="json")
        selected_by_account = {
            candidate.account_id: candidate
            for candidate in budget_optimization.selected_candidates
        }
        final_candidates = []
        for candidate in ranked:
            reasons, notes = build_business_explanation(candidate)
            selected = selected_by_account.get(candidate.account_id)
            why_this_creator, why_in_final_combination = build_selection_explanations(
                candidate,
                selected,
                budget_optimization,
            )
            final_candidates.append(
                FinalRecommendationCandidate(
                    account_id=candidate.account_id,
                    creator_id=candidate.creator_id,
                    handle=candidate.handle,
                    platform=candidate.platform,
                    final_rank=candidate.recommendation_rank,
                    fit_score=candidate.fit_score,
                    risk_decision=candidate.risk_decision,
                    selected_in_budget_plan=selected is not None,
                    historical_data_availability=candidate.features.historical_data_availability,
                    why_this_creator=why_this_creator,
                    why_in_final_combination=why_in_final_combination,
                    recommendation_reasons=reasons,
                    business_notes=notes,
                )
            )
        response = FinalRecommendationResponse(
            campaign_id=campaign_id,
            query=query,
            recommendation_run_id=run.run_id,
            evaluated_at=run.evaluated_at,
            stages=RecommendationStages(
                retrieval=RetrievalStageSummary(
                    hard_filter_pool_size=pipeline_result.hard_filter_pool_size,
                    retrieved_candidate_count=pipeline_result.hybrid_retrieval_count,
                ),
                historical_data_availability=HistoricalDataAvailabilityStageSummary(),
                fit=FitStageSummary(
                    method=effective_scoring_version,
                    dimension_weights=dimension_weights,
                    confidence_policy=CONFIDENCE_POLICY,
                    missing_value_policy=MISSING_VALUE_POLICY,
                    history_weight_policy=HISTORY_WEIGHT_POLICY,
                ),
                final=FinalStageSummary(final_candidate_count=len(ranked)),
            ),
            budget_optimization=budget_optimization,
            warnings=pipeline_result.warnings,
            candidates=final_candidates,
        )
    except Exception:
        run_repository.fail(run.run_id)
        raise
    run_repository.complete(run)
    return response


@router.get(
    "/features",
    response_model=FeatureCalculationResponse,
    tags=["internal-audit"],
    summary="旧版特征明细调试接口",
    deprecated=True,
)
def calculate_candidate_features(
    db: DbSession,
    campaign_id: str,
    query: Annotated[str, Query(min_length=1, max_length=200)],
    top_k: Annotated[int, Query(ge=1, le=200)] = 50,
    retrieval_depth: Annotated[int, Query(ge=1, le=200)] = 100,
    keyword_weight: Annotated[float, Query(ge=0, le=1)] = 0.5,
    vector_weight: Annotated[float, Query(ge=0, le=1)] = 0.5,
    rrf_k: Annotated[int, Query(ge=1, le=200)] = 60,
):
    if keyword_weight + vector_weight <= 0:
        raise HTTPException(status_code=422, detail="keyword_weight and vector_weight cannot both be zero")
    if retrieval_depth < top_k:
        raise HTTPException(status_code=422, detail="retrieval_depth must be greater than or equal to top_k")
    brief = BriefRepository(db).get(campaign_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="campaign brief not found")
    run_repository = RecommendationRunRepository(db)
    run = run_repository.create(
        campaign_id=campaign_id,
        run_type="feature_calculation",
        query_text=query,
        keyword_weight_config={
            "keyword_weight": keyword_weight,
            "vector_weight": vector_weight,
            "rrf_k": float(rrf_k),
            "campaign_base": 0.4,
            "user_focus": 0.6,
        },
        retrieval_config={
            "keyword_weight": keyword_weight,
            "vector_weight": vector_weight,
            "retrieval_depth": retrieval_depth,
            "rrf_k": rrf_k,
            "candidate_count": top_k,
        },
        fit_config={
            "mode": "feature_calculation_only",
            "feature_version": FEATURE_VERSION,
        },
    )
    try:
        pipeline_result = RecommendationPipeline(db).calculate_features(
            brief,
            query,
            run_id=run.run_id,
            evaluated_at=run.evaluated_at,
            top_k=top_k,
            retrieval_depth=retrieval_depth,
            keyword_weight=keyword_weight,
            vector_weight=vector_weight,
            rrf_k=rrf_k,
        )
        response = FeatureCalculationResponse(
            campaign_id=campaign_id,
            query=query,
            recommendation_run_id=run.run_id,
            evaluated_at=run.evaluated_at,
            feature_version=FEATURE_VERSION,
            hard_filter_pool_size=pipeline_result.hard_filter_pool_size,
            hybrid_retrieval_count=pipeline_result.hybrid_retrieval_count,
            feature_count=len(pipeline_result.features),
            note=(
                "候选人仍按Hybrid召回顺序返回；本接口只计算分项特征，"
                "尚未计算最终适配度或重新排序。"
            ),
            warnings=pipeline_result.warnings,
            candidates=pipeline_result.features,
        )
    except Exception:
        run_repository.fail(run.run_id)
        raise
    run_repository.complete(run)
    return response


@router.get(
    "/ranked",
    response_model=FinalRecommendationResponse,
    tags=["recommendations"],
    summary="旧版查询参数方式运行最终推荐",
    deprecated=True,
)
def rank_candidates(
    db: DbSession,
    campaign_id: str,
    query: Annotated[str, Query(min_length=1, max_length=200)],
    top_k: Annotated[int, Query(ge=1, le=200)] = 50,
    retrieval_depth: Annotated[int, Query(ge=1, le=200)] = 100,
    keyword_weight: Annotated[float, Query(ge=0, le=1)] = 0.5,
    vector_weight: Annotated[float, Query(ge=0, le=1)] = 0.5,
    rrf_k: Annotated[int, Query(ge=1, le=200)] = 60,
):
    if keyword_weight + vector_weight <= 0:
        raise HTTPException(status_code=422, detail="keyword_weight and vector_weight cannot both be zero")
    if retrieval_depth < top_k:
        raise HTTPException(status_code=422, detail="retrieval_depth must be greater than or equal to top_k")
    return execute_ranking(
        db,
        campaign_id=campaign_id,
        query=query,
        candidate_count=top_k,
        retrieval_depth=retrieval_depth,
        keyword_weight=keyword_weight,
        vector_weight=vector_weight,
        rrf_k=rrf_k,
        fit_mode="default",
        dimension_weights=DIMENSION_WEIGHTS,
    )


@router.post(
    "/ranked",
    response_model=FinalRecommendationResponse,
    tags=["recommendations"],
    summary="综合Hybrid召回、fit适配度与风险决策生成最终推荐",
)
def rank_candidates_configured(payload: RecommendationPayload, db: DbSession):
    retrieval = payload.retrieval_advanced
    weights = (
        DIMENSION_WEIGHTS
        if payload.fit.mode == "default"
        else payload.fit.weights.model_dump()
    )
    return execute_ranking(
        db,
        campaign_id=payload.campaign_id,
        query=payload.query,
        candidate_count=payload.candidate_count,
        retrieval_depth=retrieval.retrieval_depth,
        keyword_weight=retrieval.keyword_weight,
        vector_weight=retrieval.vector_weight,
        rrf_k=retrieval.rrf_k,
        fit_mode=payload.fit.mode,
        dimension_weights=weights,
    )
