from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models import CreatorAccount, CreatorSearchDocument
from app.schemas.retrieval import KeywordCandidate, KeywordEvidence, KeywordSearchResponse, MatchWarning
from app.services.query_expansion import expand_terms

TERM_SPLIT = re.compile(r"[\s,，。；;、|/]+")


def parse_terms(query: str) -> list[str]:
    terms = [term.strip().lower() for term in TERM_SPLIT.split(query) if term.strip()]
    return list(dict.fromkeys(terms))[:12]


def build_snippet(text: str, terms: list[str], radius: int = 70) -> str:
    lower = text.lower()
    positions = [lower.find(term) for term in terms if lower.find(term) >= 0]
    if not positions:
        return text[: radius * 2].replace("\n", " ")
    position = min(positions)
    start = max(0, position - radius)
    end = min(len(text), position + radius)
    prefix = "…" if start else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end].replace(chr(10), ' ')}{suffix}"


@dataclass
class ScoreGroup:
    score: Any
    match_condition: Any


def build_score_group(expansions: dict[str, list[str]]) -> ScoreGroup:
    concept_scores = []
    group_conditions = []
    for original_term, variants in expansions.items():
        original_match = CreatorSearchDocument.search_text.contains(original_term, autoescape=True)
        synonym_matches = [
            CreatorSearchDocument.search_text.contains(variant, autoescape=True) for variant in variants[1:]
        ]
        synonym_match = or_(*synonym_matches) if synonym_matches else original_match
        any_exact_match = or_(original_match, synonym_match)
        exact_score = case(
            (original_match, 1.0),
            (synonym_match, 0.90),
            else_=0.0,
        )
        similarities = [func.word_similarity(variant, CreatorSearchDocument.search_text) for variant in variants]
        best_similarity = func.greatest(*similarities) if len(similarities) > 1 else similarities[0]
        concept_scores.append(0.85 * exact_score + 0.15 * best_similarity)
        group_conditions.append(or_(any_exact_match, best_similarity >= 0.08))

    if not concept_scores:
        return ScoreGroup(score=0.0, match_condition=False)
    score = sum(concept_scores, start=0) / len(concept_scores)
    return ScoreGroup(score=score, match_condition=or_(*group_conditions))


def matched_variants(text: str, expansions: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    text_lower = text.lower()
    matched_concepts = []
    matched_expanded = []
    for concept, variants in expansions.items():
        hits = [variant for variant in variants if variant in text_lower]
        if hits:
            matched_concepts.append(concept)
            matched_expanded.extend(hits)
    return matched_concepts, list(dict.fromkeys(matched_expanded))


class KeywordRetriever:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        campaign_id: str | None = None,
        eligible_account_ids: list[str] | None = None,
        campaign_category: str | None = None,
        campaign_base_terms: list[str] | None = None,
    ) -> KeywordSearchResponse:
        terms = parse_terms(query)
        focus_expansions = expand_terms(terms, campaign_category)
        base_terms = list(dict.fromkeys(term.lower() for term in (campaign_base_terms or []) if term.strip()))
        base_expansions = expand_terms(base_terms, campaign_category)
        has_campaign_context = bool(campaign_id and base_expansions)
        score_weights = (
            {"campaign_base": 0.4, "user_focus": 0.6}
            if has_campaign_context
            else {"user_focus": 1.0}
        )

        if not terms:
            return KeywordSearchResponse(
                query=query,
                parsed_terms=[],
                query_expansions={},
                campaign_base_terms=base_terms,
                score_weights=score_weights,
                campaign_id=campaign_id,
                hard_filter_applied=eligible_account_ids is not None,
                eligible_pool_size=len(eligible_account_ids) if eligible_account_ids is not None else None,
                total_matches=0,
                candidates=[],
            )

        focus_group = build_score_group(focus_expansions)
        base_group = build_score_group(base_expansions)
        if has_campaign_context:
            final_score = (0.4 * base_group.score + 0.6 * focus_group.score).label("keyword_score")
            campaign_base_score = base_group.score.label("campaign_base_score")
            match_condition = or_(base_group.match_condition, focus_group.match_condition)
        else:
            final_score = focus_group.score.label("keyword_score")
            campaign_base_score = None
            match_condition = focus_group.match_condition

        columns = [
            CreatorSearchDocument,
            CreatorAccount.creator_id,
            CreatorAccount.handle,
            CreatorAccount.platform,
            CreatorAccount.primary_category,
            CreatorAccount.style_tags,
            focus_group.score.label("user_focus_score"),
            final_score,
        ]
        if campaign_base_score is not None:
            columns.append(campaign_base_score)
        statement = (
            select(*columns)
            .join(CreatorAccount, CreatorAccount.account_id == CreatorSearchDocument.account_id)
            .where(match_condition)
            .order_by(final_score.desc(), CreatorSearchDocument.account_id)
        )
        if eligible_account_ids is not None:
            if not eligible_account_ids:
                rows = []
            else:
                rows = self.session.execute(
                    statement.where(CreatorSearchDocument.account_id.in_(eligible_account_ids))
                ).all()
        else:
            rows = self.session.execute(statement).all()

        candidates = []
        all_focus_variants = list(
            dict.fromkeys(variant for values in focus_expansions.values() for variant in values)
        )
        for row in rows[:limit]:
            document = row.CreatorSearchDocument
            matched_terms, matched_expanded_terms = matched_variants(document.search_text, focus_expansions)
            base_matched_terms, _ = matched_variants(document.search_text, base_expansions)
            matched_fields: dict[str, list[str]] = {}
            searchable_fields = {
                "category_tags": document.category_tags,
                "style_tags": document.style_tags,
                "topic_tags": document.topic_tags,
                "audience_interest_tags": document.audience_interest_tags,
            }
            for field_name, values in searchable_fields.items():
                field_hits = [
                    variant for variant in all_focus_variants if any(variant in value.lower() for value in values)
                ]
                if field_hits:
                    matched_fields[field_name] = list(dict.fromkeys(field_hits))
            candidates.append(
                KeywordCandidate(
                    account_id=document.account_id,
                    creator_id=row.creator_id,
                    handle=row.handle,
                    platform=row.platform,
                    primary_category=row.primary_category,
                    style_tags=row.style_tags,
                    topic_tags=document.topic_tags,
                    campaign_base_score=(
                        round(float(row.campaign_base_score), 6) if has_campaign_context else None
                    ),
                    user_focus_score=round(float(row.user_focus_score), 6),
                    keyword_score=round(float(row.keyword_score), 6),
                    document_generated_at=document.generated_at,
                    evidence=KeywordEvidence(
                        matched_terms=matched_terms,
                        matched_expanded_terms=matched_expanded_terms,
                        campaign_base_matched_terms=base_matched_terms,
                        matched_fields=matched_fields,
                        snippet=build_snippet(document.search_text, [*all_focus_variants, *base_terms]),
                    ),
                    match_warnings=(
                        []
                        if matched_terms
                        else [
                            MatchWarning(
                                code="no_lexical_focus_match",
                                message=(
                                    f"该达人未发现用户焦点词“{' '.join(terms)}”"
                                    "或其品类内同义词的直接文本证据。"
                                ),
                                query_terms=terms,
                            )
                        ]
                    ),
                )
            )

        return KeywordSearchResponse(
            query=query,
            parsed_terms=terms,
            query_expansions=focus_expansions,
            campaign_base_terms=base_terms,
            score_weights=score_weights,
            campaign_id=campaign_id,
            hard_filter_applied=eligible_account_ids is not None,
            eligible_pool_size=len(eligible_account_ids) if eligible_account_ids is not None else None,
            total_matches=len(rows),
            candidates=candidates,
        )
