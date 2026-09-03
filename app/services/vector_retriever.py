from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embedding import get_embedding_provider
from app.models import CampaignBrief, CreatorAccount, CreatorSearchDocument
from app.schemas.retrieval import MatchWarning
from app.schemas.vector_retrieval import VectorCandidate
from app.services.keyword_retriever import matched_variants, parse_terms
from app.services.query_expansion import expand_terms


def build_vector_query_text(brief: CampaignBrief, query: str) -> str:
    expansions = expand_terms(parse_terms(query), brief.product_category)
    expanded_terms = list(dict.fromkeys(term for terms in expansions.values() for term in terms))
    parts = [
        f"Campaign品类：{brief.product_category}",
        f"用户焦点：{query}",
        f"焦点扩展：{' '.join(expanded_terms)}",
    ]
    if brief.required_topics:
        parts.append(f"必选主题：{' '.join(brief.required_topics)}")
    if brief.tone_tags:
        parts.append(f"内容调性：{' '.join(brief.tone_tags)}")
    return "\n".join(parts)


class VectorRetriever:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.provider = get_embedding_provider()

    def search(
        self,
        vector_query_text: str,
        *,
        eligible_account_ids: list[str],
        query: str,
        campaign_category: str,
        limit: int = 20,
    ) -> list[VectorCandidate]:
        if not eligible_account_ids:
            return []

        query_vector = self.provider.embed_query(vector_query_text)
        distance = CreatorAccount.profile_embedding.cosine_distance(query_vector).label("vector_distance")
        statement = (
            select(CreatorAccount, CreatorSearchDocument, distance)
            .join(CreatorSearchDocument, CreatorSearchDocument.account_id == CreatorAccount.account_id)
            .where(
                CreatorAccount.account_id.in_(eligible_account_ids),
                CreatorAccount.profile_embedding.is_not(None),
                CreatorAccount.embedding_model == self.provider.model_name,
            )
            .order_by(distance, CreatorAccount.account_id)
            .limit(limit)
        )
        rows = self.session.execute(statement).all()
        candidates = []
        terms = parse_terms(query)
        expansions = expand_terms(terms, campaign_category)
        for row in rows:
            account = row.CreatorAccount
            document = row.CreatorSearchDocument
            vector_distance = float(row.vector_distance)
            matched_terms, _ = matched_variants(document.search_text, expansions)
            candidates.append(
                VectorCandidate(
                    account_id=account.account_id,
                    creator_id=account.creator_id,
                    handle=account.handle,
                    platform=account.platform,
                    primary_category=account.primary_category,
                    style_tags=account.style_tags,
                    topic_tags=document.topic_tags,
                    vector_score=round(max(-1.0, min(1.0, 1.0 - vector_distance)), 6),
                    vector_distance=round(vector_distance, 6),
                    embedding_model=account.embedding_model,
                    document_generated_at=document.generated_at,
                    snippet=document.search_text[:200].replace("\n", " "),
                    match_warnings=(
                        []
                        if matched_terms
                        else [
                            MatchWarning(
                                code="no_lexical_focus_match",
                                message=(
                                    f"该达人未发现用户焦点词“{' '.join(terms)}”"
                                    "或其品类内同义词的直接文本证据；"
                                    "当前排名来自向量相似度。"
                                ),
                                query_terms=terms,
                            )
                        ]
                    ),
                )
            )
        return candidates
