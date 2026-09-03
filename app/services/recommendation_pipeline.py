from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import CampaignBrief
from app.schemas.features import CandidateFeatureRead
from app.schemas.retrieval import QueryWarning
from app.services.candidate_warnings import attach_active_risk_warnings
from app.services.eligibility_filter import EligibilityFilter
from app.services.feature_calculator import FeatureCalculator
from app.services.hybrid_retriever import fuse_rrf
from app.services.keyword_retriever import KeywordRetriever
from app.services.query_consistency import check_query_campaign_consistency
from app.services.vector_retriever import VectorRetriever, build_vector_query_text


@dataclass
class FeaturePipelineResult:
    hard_filter_pool_size: int
    hybrid_retrieval_count: int
    features: list[CandidateFeatureRead]
    warnings: list[QueryWarning]


class RecommendationPipeline:
    def __init__(self, session: Session) -> None:
        self.session = session

    def calculate_features(
        self,
        brief: CampaignBrief,
        query: str,
        *,
        run_id: str,
        evaluated_at: datetime,
        top_k: int,
        retrieval_depth: int,
        keyword_weight: float,
        vector_weight: float,
        rrf_k: int,
    ) -> FeaturePipelineResult:
        retrieval_depth = max(retrieval_depth, top_k)
        eligibility = EligibilityFilter(self.session).evaluate(
            brief,
            include_excluded=False,
            limit=500,
            evaluated_at=evaluated_at,
            recommendation_run_id=run_id,
        )
        eligible_ids = [candidate.account_id for candidate in eligibility.candidates]
        keyword_result = KeywordRetriever(self.session).search(
            query,
            limit=retrieval_depth,
            campaign_id=brief.campaign_id,
            eligible_account_ids=eligible_ids,
            campaign_category=brief.product_category,
            campaign_base_terms=[brief.product_category, *brief.required_topics, *brief.tone_tags],
        )
        vector_candidates = VectorRetriever(self.session).search(
            build_vector_query_text(brief, query),
            eligible_account_ids=eligible_ids,
            query=query,
            campaign_category=brief.product_category,
            limit=retrieval_depth,
        )
        hybrid_candidates = fuse_rrf(
            keyword_result.candidates,
            vector_candidates,
            keyword_weight=keyword_weight,
            vector_weight=vector_weight,
            rrf_k=rrf_k,
            limit=top_k,
        )
        attach_active_risk_warnings(self.session, hybrid_candidates, evaluated_at=evaluated_at)
        features = FeatureCalculator(self.session).calculate(
            brief,
            hybrid_candidates,
            run_id=run_id,
            evaluated_at=evaluated_at,
        )
        warnings = check_query_campaign_consistency(
            keyword_result.parsed_terms,
            campaign_category=brief.product_category,
            required_topics=brief.required_topics,
            tone_tags=brief.tone_tags,
        )
        return FeaturePipelineResult(
            hard_filter_pool_size=len(eligible_ids),
            hybrid_retrieval_count=len(hybrid_candidates),
            features=features,
            warnings=warnings,
        )
