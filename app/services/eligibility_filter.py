from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, func, literal, or_, select
from sqlalchemy.orm import Session

from app.models import CampaignBrief, Collaboration, CreatorAccount, RateCard, RiskEvent
from app.schemas.eligibility import EligibilityCandidate, EligibilityResponse, EligibilitySummary


class EligibilityFilter:
    """Evaluate deterministic campaign gates in SQL and return reasons."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def evaluate(
        self,
        brief: CampaignBrief,
        *,
        include_excluded: bool = False,
        limit: int = 100,
        evaluated_at: datetime | None = None,
        recommendation_run_id: str | None = None,
    ) -> EligibilityResponse:
        evaluated_at = evaluated_at or datetime.now(UTC)
        evaluation_date = evaluated_at.date()
        competitor_cutoff = brief.campaign_start_at - timedelta(days=brief.competitor_exclusion_days)

        compatible_price = (
            select(func.min(RateCard.base_price_cny))
            .where(
                RateCard.account_id == CreatorAccount.account_id,
                RateCard.content_format.in_(brief.content_formats),
                RateCard.valid_from <= evaluation_date,
                RateCard.valid_to >= evaluation_date,
            )
            .correlate(CreatorAccount)
            .scalar_subquery()
        )
        affordable_price = (
            select(func.min(RateCard.base_price_cny))
            .where(
                RateCard.account_id == CreatorAccount.account_id,
                RateCard.content_format.in_(brief.content_formats),
                RateCard.base_price_cny <= brief.max_budget_per_creator_cny,
                RateCard.valid_from <= evaluation_date,
                RateCard.valid_to >= evaluation_date,
            )
            .correlate(CreatorAccount)
            .scalar_subquery()
        )
        active_block = exists(
            select(literal(1)).where(
                RiskEvent.account_id == CreatorAccount.account_id,
                RiskEvent.decision == "BLOCK",
                RiskEvent.observed_at <= evaluation_date,
                or_(RiskEvent.expires_at.is_(None), RiskEvent.expires_at >= evaluation_date),
            )
        )
        if brief.competitor_brands:
            competitor_conflict = exists(
                select(literal(1)).where(
                    Collaboration.account_id == CreatorAccount.account_id,
                    Collaboration.brand_name.in_(brief.competitor_brands),
                    or_(
                        Collaboration.ended_at >= competitor_cutoff,
                        Collaboration.exclusive_until >= brief.campaign_start_at,
                    ),
                )
            )
        else:
            competitor_conflict = literal(False)

        platform_match = CreatorAccount.platform.in_(brief.target_platforms)
        category_match = or_(
            CreatorAccount.primary_category == brief.product_category,
            CreatorAccount.category_tags.contains([brief.product_category]),
        )
        statement = select(
            CreatorAccount.account_id,
            CreatorAccount.creator_id,
            CreatorAccount.handle,
            CreatorAccount.platform,
            CreatorAccount.creator_tier,
            CreatorAccount.follower_count_current,
            CreatorAccount.primary_category,
            (CreatorAccount.account_status == "active").label("account_active"),
            platform_match.label("platform_match"),
            category_match.label("category_match"),
            compatible_price.label("compatible_price"),
            affordable_price.label("affordable_price"),
            active_block.label("active_block"),
            competitor_conflict.label("competitor_conflict"),
        ).order_by(CreatorAccount.follower_count_current.desc())

        reason_counts: Counter[str] = Counter()
        candidates: list[EligibilityCandidate] = []
        eligible_count = 0
        rows = self.session.execute(statement).all()
        for row in rows:
            reasons: list[str] = []
            if not row.account_active:
                reasons.append("account_inactive")
            if not row.platform_match:
                reasons.append("platform_mismatch")
            if not row.category_match:
                reasons.append("category_mismatch")
            if row.compatible_price is None:
                reasons.append("no_compatible_rate_card")
            elif row.affordable_price is None:
                reasons.append("over_per_creator_budget")
            if row.active_block:
                reasons.append("active_block_risk")
            if row.competitor_conflict:
                reasons.append("competitor_exclusion_conflict")

            eligible = not reasons
            if eligible:
                eligible_count += 1
            else:
                reason_counts.update(reasons)
            if (include_excluded or eligible) and len(candidates) < limit:
                candidates.append(
                    EligibilityCandidate(
                        account_id=row.account_id,
                        creator_id=row.creator_id,
                        handle=row.handle,
                        platform=row.platform,
                        creator_tier=row.creator_tier,
                        follower_count=row.follower_count_current,
                        primary_category=row.primary_category,
                        min_compatible_price_cny=row.compatible_price,
                        eligible=eligible,
                        exclusion_reasons=reasons,
                    )
                )

        return EligibilityResponse(
            campaign_id=brief.campaign_id,
            recommendation_run_id=recommendation_run_id,
            evaluated_at=evaluated_at,
            summary=EligibilitySummary(
                evaluated_accounts=len(rows),
                eligible_accounts=eligible_count,
                returned_candidates=len(candidates),
                excluded_by_reason=dict(sorted(reason_counts.items())),
            ),
            candidates=candidates,
        )
