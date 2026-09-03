from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.briefs import BriefRepository
from app.repositories.recommendation_runs import RecommendationRunRepository
from app.schemas.history_availability import (
    HistoricalAvailabilityCandidate,
    HistoricalAvailabilityRunResponse,
)
from app.schemas.recommendation_config import HistoricalAvailabilityRunRequest
from app.services.recommendation_pipeline import RecommendationPipeline

router = APIRouter(
    prefix="/api/historical-data-availability-checker",
    tags=["historical-data-availability-checker"],
)
DbSession = Annotated[Session, Depends(get_db)]
HistoryPayload = Annotated[
    HistoricalAvailabilityRunRequest,
    Body(
        openapi_examples={
            "default": {
                "summary": "对Hybrid候选池执行三档历史数据分层",
                "value": {
                    "campaign_id": "cmp_0001",
                    "query": "配料表",
                    "candidate_count": 20,
                    "retrieval_advanced": {
                        "keyword_weight": 0.5,
                        "vector_weight": 0.5,
                        "retrieval_depth": 100,
                        "rrf_k": 60,
                    },
                },
            }
        }
    ),
]


@router.post(
    "/check",
    response_model=HistoricalAvailabilityRunResponse,
    summary="historical-data-availability-checker",
    description=(
        "先生成Hybrid候选池，再按当前Campaign品类、内容形式、主KPI、归因窗口和18个月回看期，"
        "将达人划分为历史充分、历史有限或完全冷启动。该结果属于数据/匹配提示，不改变风险决策。"
    ),
)
def check_historical_data_availability(payload: HistoryPayload, db: DbSession):
    brief = BriefRepository(db).get(payload.campaign_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="campaign brief not found")

    retrieval = payload.retrieval_advanced
    run_repository = RecommendationRunRepository(db)
    run = run_repository.create(
        campaign_id=payload.campaign_id,
        run_type="history_availability_check",
        query_text=payload.query,
        retrieval_config={
            **retrieval.model_dump(),
            "candidate_count": payload.candidate_count,
        },
        fit_config={
            "module": "historical_data_availability",
            "tiers": ["HISTORY_SUFFICIENT", "HISTORY_LIMITED", "COLD_START"],
        },
    )
    try:
        pipeline_result = RecommendationPipeline(db).calculate_features(
            brief,
            payload.query,
            run_id=run.run_id,
            evaluated_at=run.evaluated_at,
            top_k=payload.candidate_count,
            retrieval_depth=retrieval.retrieval_depth,
            keyword_weight=retrieval.keyword_weight,
            vector_weight=retrieval.vector_weight,
            rrf_k=retrieval.rrf_k,
        )
        tier_counts = Counter(
            feature.historical_data_availability.tier
            for feature in pipeline_result.features
        )
        candidates = [
            HistoricalAvailabilityCandidate(
                account_id=feature.account_id,
                creator_id=feature.creator_id,
                handle=feature.handle,
                platform=feature.platform,
                retrieval_rank=feature.retrieval_rank,
                availability=feature.historical_data_availability,
                warnings=[
                    warning
                    for warning in feature.match_warnings
                    if warning.code
                    in {"LIMITED_CREATOR_HISTORY", "COLD_START_NO_ATTRIBUTED_HISTORY"}
                ],
            )
            for feature in pipeline_result.features
        ]
        response = HistoricalAvailabilityRunResponse(
            campaign_id=payload.campaign_id,
            query=payload.query,
            recommendation_run_id=run.run_id,
            evaluated_at=run.evaluated_at,
            tier_counts={
                "HISTORY_SUFFICIENT": tier_counts["HISTORY_SUFFICIENT"],
                "HISTORY_LIMITED": tier_counts["HISTORY_LIMITED"],
                "COLD_START": tier_counts["COLD_START"],
            },
            candidate_count=len(candidates),
            query_warnings=pipeline_result.warnings,
            candidates=candidates,
        )
    except Exception:
        run_repository.fail(run.run_id)
        raise
    run_repository.complete(run)
    return response
