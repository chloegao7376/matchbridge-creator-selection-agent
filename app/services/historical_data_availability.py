from __future__ import annotations

from datetime import date, timedelta

from app.models import Collaboration
from app.schemas.features import HistoricalDataAvailability

HISTORY_LOOKBACK_DAYS = 548
SUFFICIENT_EFFECTIVE_HISTORY_N = 3.0
TIER_LABELS = {
    "HISTORY_SUFFICIENT": "历史充分",
    "HISTORY_LIMITED": "历史有限",
    "COLD_START": "完全冷启动",
}
WEIGHTING_POLICY = (
    "有效样本=已完成且归因窗口结束、18个月内、views>0且包含当前主KPI；"
    "同品类1.0/其他品类0.25 × 同形式1.0/兼容形式0.7 × "
    "近6个月1.0/6-12个月0.7/12-18个月0.4"
)


def _months_weight(ended_at: date, evaluated_at: date) -> float:
    age_days = (evaluated_at - ended_at).days
    if age_days <= 183:
        return 1.0
    if age_days <= 365:
        return 0.7
    return 0.4


def valid_history_sample(
    collaboration: Collaboration,
    *,
    primary_kpi: str,
    evaluated_at: date,
) -> bool:
    performance = collaboration.performance or {}
    attribution_closed = collaboration.ended_at + timedelta(
        days=collaboration.attribution_window_days
    )
    return (
        collaboration.status == "completed"
        and attribution_closed <= evaluated_at
        and collaboration.ended_at >= evaluated_at - timedelta(days=HISTORY_LOOKBACK_DAYS)
        and float(performance.get("views", 0) or 0) > 0
        and primary_kpi in performance
        and float(performance[primary_kpi]) >= 0
    )


class HistoricalDataAvailabilityChecker:
    """Classify creator history without introducing a fourth data-quality tier."""

    def evaluate(
        self,
        collaborations: list[Collaboration],
        *,
        campaign_category: str,
        compatible_formats: list[str],
        primary_kpi: str,
        evaluated_at: date,
    ) -> HistoricalDataAvailability:
        effective_n = 0.0
        valid_count = 0
        for collaboration in collaborations:
            if not valid_history_sample(
                collaboration,
                primary_kpi=primary_kpi,
                evaluated_at=evaluated_at,
            ):
                continue
            valid_count += 1
            category_weight = 1.0 if collaboration.brand_category == campaign_category else 0.25
            format_weight = 1.0 if collaboration.content_format in compatible_formats else 0.7
            effective_n += category_weight * format_weight * _months_weight(
                collaboration.ended_at, evaluated_at
            )

        effective_n = round(effective_n, 4)
        if effective_n >= SUFFICIENT_EFFECTIVE_HISTORY_N:
            tier = "HISTORY_SUFFICIENT"
        elif effective_n > 0:
            tier = "HISTORY_LIMITED"
        else:
            tier = "COLD_START"
        return HistoricalDataAvailability(
            tier=tier,
            tier_label=TIER_LABELS[tier],
            effective_history_n=effective_n,
            history_reliability=round(min(effective_n / SUFFICIENT_EFFECTIVE_HISTORY_N, 1.0), 6),
            valid_history_count=valid_count,
            primary_kpi=primary_kpi,
            weighting_policy=WEIGHTING_POLICY,
        )
