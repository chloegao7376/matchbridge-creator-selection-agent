from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

json_list_default = list
json_dict_default = dict


class Creator(Base):
    __tablename__ = "creators"

    creator_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_fictional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    home_region: Mapped[str] = mapped_column(String(64), nullable=False)
    languages: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=json_list_default)
    category_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=json_list_default)
    style_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=json_list_default)
    public_persona_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[date] = mapped_column(Date, nullable=False)


class CreatorAccount(Base):
    __tablename__ = "creator_accounts"
    __table_args__ = (
        Index("ix_creator_accounts_platform_category", "platform", "primary_category"),
        Index("ix_creator_accounts_followers", "follower_count_current"),
    )

    account_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    creator_id: Mapped[str] = mapped_column(ForeignKey("creators.creator_id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    handle: Mapped[str] = mapped_column(String(160), nullable=False)
    profile_url: Mapped[str] = mapped_column(Text, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    creator_tier: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    follower_count_current: Mapped[int] = mapped_column(BigInteger, nullable=False)
    primary_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=json_list_default)
    style_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=json_list_default)
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    account_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    data_source: Mapped[str] = mapped_column(String(64), nullable=False)
    collected_at: Mapped[date] = mapped_column(Date, nullable=False)
    data_confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    profile_embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedding_document_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CreatorSearchDocument(Base):
    __tablename__ = "creator_search_documents"
    __table_args__ = (
        Index(
            "ix_creator_search_documents_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )

    account_id: Mapped[str] = mapped_column(
        ForeignKey("creator_accounts.account_id", ondelete="CASCADE"), primary_key=True
    )
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    category_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    style_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    topic_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    audience_interest_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    representative_content_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    content_count: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[date] = mapped_column(Date, nullable=False)


class AudienceSnapshot(Base):
    __tablename__ = "audience_snapshots"

    account_id: Mapped[str] = mapped_column(ForeignKey("creator_accounts.account_id", ondelete="CASCADE"), primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    audience_gender_distribution: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    audience_age_distribution: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    top_regions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    audience_interest_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    active_follower_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    suspicious_account_ratio_observed: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    measurement_method: Mapped[str] = mapped_column(String(120), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)


class AccountMetricSnapshot(Base):
    __tablename__ = "account_metric_snapshots"

    account_id: Mapped[str] = mapped_column(ForeignKey("creator_accounts.account_id", ondelete="CASCADE"), primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    follower_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    posts_last_7d: Mapped[int] = mapped_column(Integer, nullable=False)
    median_views_last_30d: Mapped[int] = mapped_column(BigInteger, nullable=False)
    engagement_rate_by_followers_30d: Mapped[Decimal] = mapped_column(Numeric(10, 8), nullable=False)
    view_cv_30d: Mapped[Decimal] = mapped_column(Numeric(10, 8), nullable=False)
    repetitive_comment_ratio_observed: Mapped[Decimal] = mapped_column(Numeric(10, 8), nullable=False)
    data_source: Mapped[str] = mapped_column(String(64), nullable=False)


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        Index("ix_content_items_account_published", "account_id", "published_at"),
        Index("ix_content_items_sponsored", "is_sponsored", "ad_disclosure_present"),
    )

    content_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("creator_accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    published_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    content_format: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    style_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    mentioned_brands: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    is_sponsored: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ad_disclosure_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    comment_sample: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    comment_sentiment: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    metric_collected_at: Mapped[date] = mapped_column(Date, nullable=False)


class RateCard(Base):
    __tablename__ = "rate_cards"
    __table_args__ = (Index("ix_rate_cards_account_format", "account_id", "content_format"),)

    rate_card_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("creator_accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    content_format: Mapped[str] = mapped_column(String(32), nullable=False)
    base_price_cny: Mapped[int] = mapped_column(Integer, nullable=False)
    package_price_cny: Mapped[int] = mapped_column(Integer, nullable=False)
    package_description: Mapped[str] = mapped_column(Text, nullable=False)
    agency_fee_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    negotiable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    usage_rights_days_included: Mapped[int] = mapped_column(Integer, nullable=False)
    exclusivity_days_included: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)


class Collaboration(Base):
    __tablename__ = "collaborations"
    __table_args__ = (Index("ix_collaborations_account_ended", "account_id", "ended_at"),)

    collaboration_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("creator_accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    brand_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    brand_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    started_at: Mapped[date] = mapped_column(Date, nullable=False)
    ended_at: Mapped[date] = mapped_column(Date, nullable=False)
    content_format: Mapped[str] = mapped_column(String(32), nullable=False)
    contract_amount_cny: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    delivered_on_time: Mapped[bool] = mapped_column(Boolean, nullable=False)
    revision_count: Mapped[int] = mapped_column(Integer, nullable=False)
    performance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    attribution_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    roi: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    exclusive_until: Mapped[date] = mapped_column(Date, nullable=False)


class PolicyRule(Base):
    __tablename__ = "policy_rules"

    rule_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    version: Mapped[str] = mapped_column(String(24), primary_key=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    default_action: Mapped[str] = mapped_column(String(24), nullable=False)
    is_legal_determination: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RiskEvent(Base):
    __tablename__ = "risk_events"
    __table_args__ = (
        Index("ix_risk_events_account_observed", "account_id", "observed_at"),
        Index("ix_risk_events_decision_severity", "decision", "severity"),
    )

    risk_event_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("creator_accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    content_id: Mapped[str | None] = mapped_column(ForeignKey("content_items.content_id", ondelete="SET NULL"), nullable=True)
    risk_type: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_subtype: Mapped[str] = mapped_column(String(80), nullable=False)
    observed_at: Mapped[date] = mapped_column(Date, nullable=False)
    severity: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_metric: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_id: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(24), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_false_positive: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class CampaignBrief(Base):
    __tablename__ = "campaign_briefs"

    campaign_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    brand_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(160), nullable=False)
    product_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    campaign_objective: Mapped[str] = mapped_column(String(32), nullable=False)
    primary_kpi: Mapped[str] = mapped_column(String(64), nullable=False)
    target_platforms: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    target_regions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    target_audience: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    tone_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    required_topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    forbidden_topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    content_formats: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    deliverables_per_creator: Mapped[int] = mapped_column(Integer, nullable=False)
    campaign_start_at: Mapped[date] = mapped_column(Date, nullable=False)
    campaign_end_at: Mapped[date] = mapped_column(Date, nullable=False)
    total_budget_cny: Mapped[int] = mapped_column(Integer, nullable=False)
    max_budget_per_creator_cny: Mapped[int] = mapped_column(Integer, nullable=False)
    creator_count: Mapped[int] = mapped_column(Integer, nullable=False)
    preferred_creator_tiers: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    competitor_brands: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    competitor_exclusion_days: Mapped[int] = mapped_column(Integer, nullable=False)
    usage_rights_days: Mapped[int] = mapped_column(Integer, nullable=False)
    exclusivity_required_days: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_tolerance: Mapped[str] = mapped_column(String(24), nullable=False)
    brief_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[date] = mapped_column(Date, nullable=False)


class RecommendationRun(Base):
    __tablename__ = "recommendation_runs"
    __table_args__ = (
        Index("ix_recommendation_runs_campaign_started", "campaign_id", "started_at"),
        Index("ix_recommendation_runs_status", "status"),
    )

    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_briefs.campaign_id", ondelete="CASCADE"), nullable=False
    )
    run_type: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    filter_policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    keyword_weight_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=json_dict_default)
    retrieval_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=json_dict_default)
    fit_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=json_dict_default)
    budget_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=json_dict_default)
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class CandidateFeatureSnapshot(Base):
    __tablename__ = "candidate_feature_snapshots"
    __table_args__ = (
        Index("ix_candidate_feature_snapshots_run", "run_id"),
        Index("ix_candidate_feature_snapshots_campaign_account", "campaign_id", "account_id"),
    )

    feature_snapshot_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("recommendation_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_briefs.campaign_id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        ForeignKey("creator_accounts.account_id", ondelete="CASCADE"), nullable=False
    )
    feature_version: Mapped[str] = mapped_column(String(40), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retrieval_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class CandidateScoreSnapshot(Base):
    __tablename__ = "candidate_score_snapshots"
    __table_args__ = (
        Index("ix_candidate_score_snapshots_run", "run_id"),
        Index("ix_candidate_score_snapshots_campaign_account", "campaign_id", "account_id"),
    )

    score_snapshot_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    feature_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_feature_snapshots.feature_snapshot_id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("recommendation_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_briefs.campaign_id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        ForeignKey("creator_accounts.account_id", ondelete="CASCADE"), nullable=False
    )
    scoring_version: Mapped[str] = mapped_column(String(40), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fit_score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    fit_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_decision: Mapped[str] = mapped_column(String(24), nullable=False)
    scoring_detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class SelectionReview(Base):
    __tablename__ = "selection_reviews"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_selection_reviews_run_id"),
        Index("ix_selection_reviews_campaign_updated", "campaign_id", "updated_at"),
    )

    review_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("recommendation_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_briefs.campaign_id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    reviewer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    optimization_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=json_dict_default
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SelectionReviewItem(Base):
    __tablename__ = "selection_review_items"
    __table_args__ = (
        UniqueConstraint("review_id", "account_id", name="uq_selection_review_items_review_account"),
        Index("ix_selection_review_items_review_disposition", "review_id", "disposition"),
    )

    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    review_id: Mapped[str] = mapped_column(
        ForeignKey("selection_reviews.review_id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        ForeignKey("creator_accounts.account_id", ondelete="CASCADE"), nullable=False
    )
    disposition: Mapped[str] = mapped_column(String(24), nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_resolution: Mapped[str] = mapped_column(String(24), nullable=False, default="NOT_REQUIRED")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SelectionReviewEvent(Base):
    __tablename__ = "selection_review_events"
    __table_args__ = (Index("ix_selection_review_events_review_created", "review_id", "created_at"),)

    event_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    review_id: Mapped[str] = mapped_column(
        ForeignKey("selection_reviews.review_id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=json_dict_default)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
