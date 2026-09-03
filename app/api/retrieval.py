from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.briefs import BriefRepository
from app.repositories.recommendation_runs import RecommendationRunRepository
from app.schemas.hybrid_retrieval import HybridSearchResponse
from app.schemas.retrieval import KeywordSearchResponse
from app.schemas.vector_retrieval import VectorSearchResponse
from app.services.candidate_warnings import attach_active_risk_warnings
from app.services.eligibility_filter import EligibilityFilter
from app.services.hybrid_retriever import fuse_rrf
from app.services.keyword_retriever import KeywordRetriever, parse_terms
from app.services.query_consistency import check_query_campaign_consistency
from app.services.vector_retriever import VectorRetriever, build_vector_query_text

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/keyword", response_model=KeywordSearchResponse)
def keyword_search(
    db: DbSession,
    query: Annotated[str, Query(min_length=1, max_length=200)],
    campaign_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    eligible_ids: list[str] | None = None
    brief = None
    run = None
    run_repository = RecommendationRunRepository(db)
    if campaign_id:
        brief = BriefRepository(db).get(campaign_id)
        if brief is None:
            raise HTTPException(status_code=404, detail="campaign brief not found")
        run = run_repository.create(
            campaign_id=campaign_id,
            run_type="keyword_retrieval",
            query_text=query,
            keyword_weight_config={"campaign_base": 0.4, "user_focus": 0.6},
        )
    try:
        if brief is not None and run is not None:
            eligibility = EligibilityFilter(db).evaluate(
                brief,
                include_excluded=False,
                limit=500,
                evaluated_at=run.evaluated_at,
                recommendation_run_id=run.run_id,
            )
            eligible_ids = [candidate.account_id for candidate in eligibility.candidates]
        result = KeywordRetriever(db).search(
            query,
            limit=limit,
            campaign_id=campaign_id,
            eligible_account_ids=eligible_ids,
            campaign_category=brief.product_category if brief is not None else None,
            campaign_base_terms=(
                [brief.product_category, *brief.required_topics, *brief.tone_tags]
                if brief is not None
                else None
            ),
        )
        if brief is not None:
            result.warnings = check_query_campaign_consistency(
                result.parsed_terms,
                campaign_category=brief.product_category,
                required_topics=brief.required_topics,
                tone_tags=brief.tone_tags,
            )
        if run is not None:
            attach_active_risk_warnings(db, result.candidates, evaluated_at=run.evaluated_at)
            result.recommendation_run_id = run.run_id
            result.evaluated_at = run.evaluated_at
    except Exception:
        if run is not None:
            run_repository.fail(run.run_id)
        raise
    if run is not None:
        run_repository.complete(run)
    return result


@router.get("/vector", response_model=VectorSearchResponse)
def vector_search(
    db: DbSession,
    campaign_id: str,
    query: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    brief = BriefRepository(db).get(campaign_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="campaign brief not found")
    run_repository = RecommendationRunRepository(db)
    run = run_repository.create(
        campaign_id=campaign_id,
        run_type="vector_retrieval",
        query_text=query,
    )
    try:
        eligibility = EligibilityFilter(db).evaluate(
            brief,
            include_excluded=False,
            limit=500,
            evaluated_at=run.evaluated_at,
            recommendation_run_id=run.run_id,
        )
        eligible_ids = [candidate.account_id for candidate in eligibility.candidates]
        vector_retriever = VectorRetriever(db)
        vector_query_text = build_vector_query_text(brief, query)
        candidates = vector_retriever.search(
            vector_query_text,
            eligible_account_ids=eligible_ids,
            query=query,
            campaign_category=brief.product_category,
            limit=limit,
        )
        attach_active_risk_warnings(db, candidates, evaluated_at=run.evaluated_at)
        warnings = check_query_campaign_consistency(
            parse_terms(query),
            campaign_category=brief.product_category,
            required_topics=brief.required_topics,
            tone_tags=brief.tone_tags,
        )
        response = VectorSearchResponse(
            query=query,
            vector_query_text=vector_query_text,
            campaign_id=campaign_id,
            recommendation_run_id=run.run_id,
            evaluated_at=run.evaluated_at,
            embedding_model=vector_retriever.provider.model_name,
            eligible_pool_size=len(eligible_ids),
            total_matches=len(candidates),
            candidates=candidates,
            warnings=warnings,
        )
    except Exception:
        run_repository.fail(run.run_id)
        raise
    run_repository.complete(run)
    return response


@router.get("/hybrid", response_model=HybridSearchResponse)
def hybrid_search(
    db: DbSession,
    campaign_id: str,
    query: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    retrieval_depth: Annotated[int, Query(ge=1, le=200)] = 100,
    keyword_weight: Annotated[float, Query(ge=0, le=1)] = 0.5,
    vector_weight: Annotated[float, Query(ge=0, le=1)] = 0.5,
    rrf_k: Annotated[int, Query(ge=1, le=200)] = 60,
):
    if keyword_weight + vector_weight <= 0:
        raise HTTPException(status_code=422, detail="keyword_weight and vector_weight cannot both be zero")
    brief = BriefRepository(db).get(campaign_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="campaign brief not found")
    fusion_config = {
        "keyword_weight": keyword_weight,
        "vector_weight": vector_weight,
        "rrf_k": float(rrf_k),
        "campaign_base_weight": 0.4,
        "user_focus_weight": 0.6,
    }
    run_repository = RecommendationRunRepository(db)
    run = run_repository.create(
        campaign_id=campaign_id,
        run_type="hybrid_retrieval",
        query_text=query,
        keyword_weight_config=fusion_config,
    )
    try:
        eligibility = EligibilityFilter(db).evaluate(
            brief,
            include_excluded=False,
            limit=500,
            evaluated_at=run.evaluated_at,
            recommendation_run_id=run.run_id,
        )
        eligible_ids = [candidate.account_id for candidate in eligibility.candidates]
        campaign_base_terms = [brief.product_category, *brief.required_topics, *brief.tone_tags]
        keyword_result = KeywordRetriever(db).search(
            query,
            limit=retrieval_depth,
            campaign_id=campaign_id,
            eligible_account_ids=eligible_ids,
            campaign_category=brief.product_category,
            campaign_base_terms=campaign_base_terms,
        )
        vector_retriever = VectorRetriever(db)
        vector_candidates = vector_retriever.search(
            build_vector_query_text(brief, query),
            eligible_account_ids=eligible_ids,
            query=query,
            campaign_category=brief.product_category,
            limit=retrieval_depth,
        )
        candidates = fuse_rrf(
            keyword_result.candidates,
            vector_candidates,
            keyword_weight=keyword_weight,
            vector_weight=vector_weight,
            rrf_k=rrf_k,
            limit=limit,
        )
        attach_active_risk_warnings(db, candidates, evaluated_at=run.evaluated_at)
        warnings = check_query_campaign_consistency(
            keyword_result.parsed_terms,
            campaign_category=brief.product_category,
            required_topics=brief.required_topics,
            tone_tags=brief.tone_tags,
        )
        response = HybridSearchResponse(
            query=query,
            campaign_id=campaign_id,
            recommendation_run_id=run.run_id,
            evaluated_at=run.evaluated_at,
            embedding_model=vector_retriever.provider.model_name,
            eligible_pool_size=len(eligible_ids),
            keyword_matches=keyword_result.total_matches,
            vector_matches=len(vector_candidates),
            fusion_config=fusion_config,
            candidates=candidates,
            warnings=warnings,
        )
    except Exception:
        run_repository.fail(run.run_id)
        raise
    run_repository.complete(run)
    return response
