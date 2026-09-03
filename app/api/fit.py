from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.briefs import BriefRepository
from app.repositories.recommendation_runs import RecommendationRunRepository
from app.schemas.fit import FitCandidateResult, FitDimensionResult, FitRunResponse
from app.schemas.recommendation_config import FitRunRequest
from app.services.fit_ranker import (
    CONFIDENCE_POLICY,
    DIMENSION_WEIGHTS,
    MISSING_VALUE_POLICY,
    FitRanker,
    scoring_version_for,
)
from app.services.recommendation_pipeline import RecommendationPipeline

router = APIRouter(prefix="/api/fit", tags=["fit"])
DbSession = Annotated[Session, Depends(get_db)]
FitPayload = Annotated[
    FitRunRequest,
    Body(
        openapi_examples={
            "default": {
                "summary": "default：使用系统默认权重",
                "description": "内容30%、受众20%、历史效果15%、成本10%、流量10%、履约10%、数据5%。",
                "value": {
                    "campaign_id": "cmp_0001",
                    "query": "配料表",
                    "candidate_count": 50,
                    "fit": {"mode": "default"},
                },
            },
            "custom": {
                "summary": "custom：自定义七维权重",
                "description": "必须提交全部七个维度，权重合计必须为1。",
                "value": {
                    "campaign_id": "cmp_0001",
                    "query": "配料表",
                    "candidate_count": 50,
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


@router.post(
    "/calculate",
    response_model=FitRunResponse,
    summary="对Hybrid召回候选达人进行业务适配度计算",
    description=(
        "default模式使用系统预设的七维权重；"
        "需要调节权重时，切换为custom模式并提交合计为1的完整七维权重。"
    ),
)
def calculate_fit(payload: FitPayload, db: DbSession):
    brief = BriefRepository(db).get(payload.campaign_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="campaign brief not found")
    weights = (
        DIMENSION_WEIGHTS
        if payload.fit.mode == "default"
        else payload.fit.weights.model_dump()
    )
    scoring_version = scoring_version_for(payload.fit.mode, weights)
    retrieval_depth = max(100, payload.candidate_count)
    run_repository = RecommendationRunRepository(db)
    run = run_repository.create(
        campaign_id=payload.campaign_id,
        run_type="fit_calculation",
        query_text=payload.query,
        retrieval_config={
            "source": "hybrid_system_default",
            "keyword_weight": 0.5,
            "vector_weight": 0.5,
            "retrieval_depth": retrieval_depth,
            "rrf_k": 60,
            "candidate_count": payload.candidate_count,
        },
        fit_config={
            "mode": payload.fit.mode,
            "weights": weights,
            "scoring_version": scoring_version,
            "confidence_policy": CONFIDENCE_POLICY,
            "missing_value_policy": MISSING_VALUE_POLICY,
            "risk_policy_editable": False,
        },
    )
    try:
        pipeline_result = RecommendationPipeline(db).calculate_features(
            brief,
            payload.query,
            run_id=run.run_id,
            evaluated_at=run.evaluated_at,
            top_k=payload.candidate_count,
            retrieval_depth=retrieval_depth,
            keyword_weight=0.5,
            vector_weight=0.5,
            rrf_k=60,
        )
        ranked = FitRanker(db).rank(
            pipeline_result.features,
            run_id=run.run_id,
            campaign_id=payload.campaign_id,
            evaluated_at=run.evaluated_at,
            dimension_weights=weights,
            scoring_version=scoring_version,
        )
        candidates = []
        for candidate in sorted(ranked, key=lambda item: item.fit_rank):
            candidates.append(
                FitCandidateResult(
                    account_id=candidate.account_id,
                    creator_id=candidate.creator_id,
                    handle=candidate.handle,
                    platform=candidate.platform,
                    retrieval_rank=candidate.retrieval_rank,
                    fit_rank=candidate.fit_rank,
                    fit_score=candidate.fit_score,
                    feature_coverage=candidate.feature_coverage,
                    overall_confidence=candidate.overall_confidence,
                    dimensions={
                        name: FitDimensionResult(
                            score=contribution.raw_score,
                            weight=contribution.weight,
                            contribution_points=contribution.contribution_points,
                            missing=contribution.missing,
                        )
                        for name, contribution in candidate.dimension_contributions.items()
                    },
                )
            )
        response = FitRunResponse(
            campaign_id=payload.campaign_id,
            query=payload.query,
            recommendation_run_id=run.run_id,
            evaluated_at=run.evaluated_at,
            mode=payload.fit.mode,
            scoring_version=scoring_version,
            effective_weights=weights,
            confidence_policy=CONFIDENCE_POLICY,
            missing_value_policy=MISSING_VALUE_POLICY,
            candidate_count=len(candidates),
            warnings=pipeline_result.warnings,
            candidates=candidates,
        )
    except Exception:
        run_repository.fail(run.run_id)
        raise
    run_repository.complete(run)
    return response
