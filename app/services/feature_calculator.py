from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import fmean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AccountMetricSnapshot,
    AudienceSnapshot,
    CampaignBrief,
    CandidateFeatureSnapshot,
    Collaboration,
    CreatorAccount,
    RateCard,
)
from app.schemas.features import (
    CandidateFeatureRead,
    FeatureDimension,
    FeatureValue,
    HistoricalDataAvailability,
)
from app.schemas.hybrid_retrieval import HybridCandidate
from app.schemas.retrieval import MatchWarning
from app.services.historical_data_availability import (
    HistoricalDataAvailabilityChecker,
    valid_history_sample,
)

FEATURE_VERSION = "candidate_features_v4_history_tiering"
KPI_BY_OBJECTIVE = {
    "awareness": "impressions",
    "engagement": "engagements",
    "conversion": "conversions",
}
KPI_RATE_FALLBACKS = {
    "impressions": 1.0,
    "engagements": 0.03,
    "conversions": 0.001,
}
KPI_PRIOR_VIEWS = 50_000


def resolve_primary_kpi(brief: CampaignBrief) -> str:
    if brief.primary_kpi in KPI_RATE_FALLBACKS:
        return brief.primary_kpi
    return KPI_BY_OBJECTIVE[brief.campaign_objective]


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def weighted_score(items: list[tuple[float | None, float]]) -> float | None:
    available = [(score, weight) for score, weight in items if score is not None and weight > 0]
    if not available:
        return None
    return round(sum(score * weight for score, weight in available) / sum(weight for _, weight in available), 6)


def value(
    *,
    score: float | None,
    raw_value,
    data_source: str,
    confidence: float,
    evidence: str,
    as_of=None,
    unit: str | None = None,
    missing: bool = False,
) -> FeatureValue:
    return FeatureValue(
        score=round(score, 6) if score is not None else None,
        raw_value=raw_value,
        unit=unit,
        data_source=data_source,
        as_of=as_of,
        confidence=round(clamp(confidence), 6),
        missing=missing,
        evidence=evidence,
    )


def dimension(components: dict[str, FeatureValue], weights: dict[str, float], evidence: str) -> FeatureDimension:
    score = weighted_score(
        [(component.score if not component.missing else None, weights.get(name, 0.0)) for name, component in components.items()]
    )
    return FeatureDimension(score=score, components=components, evidence=evidence)


class FeatureCalculator:
    def __init__(self, session: Session) -> None:
        self.session = session

    def calculate(
        self,
        brief: CampaignBrief,
        candidates: list[HybridCandidate],
        *,
        run_id: str,
        evaluated_at: datetime,
    ) -> list[CandidateFeatureRead]:
        account_ids = [candidate.account_id for candidate in candidates]
        if not account_ids:
            return []
        cutoff = evaluated_at.date()

        accounts = {
            account.account_id: account
            for account in self.session.scalars(
                select(CreatorAccount).where(CreatorAccount.account_id.in_(account_ids))
            )
        }
        audiences = {
            snapshot.account_id: snapshot
            for snapshot in self.session.scalars(
                select(AudienceSnapshot)
                .where(AudienceSnapshot.account_id.in_(account_ids), AudienceSnapshot.snapshot_date <= cutoff)
                .distinct(AudienceSnapshot.account_id)
                .order_by(AudienceSnapshot.account_id, AudienceSnapshot.snapshot_date.desc())
            )
        }
        metrics = {
            snapshot.account_id: snapshot
            for snapshot in self.session.scalars(
                select(AccountMetricSnapshot)
                .where(
                    AccountMetricSnapshot.account_id.in_(account_ids),
                    AccountMetricSnapshot.snapshot_date <= cutoff,
                )
                .distinct(AccountMetricSnapshot.account_id)
                .order_by(AccountMetricSnapshot.account_id, AccountMetricSnapshot.snapshot_date.desc())
            )
        }
        rates_by_account: dict[str, list[RateCard]] = defaultdict(list)
        for rate in self.session.scalars(
            select(RateCard).where(
                RateCard.account_id.in_(account_ids),
                RateCard.content_format.in_(brief.content_formats),
                RateCard.valid_from <= cutoff,
                RateCard.valid_to >= cutoff,
            )
        ):
            rates_by_account[rate.account_id].append(rate)
        collaborations_by_account: dict[str, list[Collaboration]] = defaultdict(list)
        for collaboration in self.session.scalars(
            select(Collaboration).where(
                Collaboration.account_id.in_(account_ids),
                Collaboration.ended_at <= cutoff,
            )
        ):
            collaborations_by_account[collaboration.account_id].append(collaboration)
        cohort_collaborations = list(
            self.session.scalars(
                select(Collaboration).where(
                    Collaboration.brand_category == brief.product_category,
                    Collaboration.status == "completed",
                    Collaboration.ended_at <= cutoff,
                )
            )
        )

        results = []
        primary_kpi = resolve_primary_kpi(brief)
        history_checker = HistoricalDataAvailabilityChecker()
        for retrieval_rank, candidate in enumerate(candidates, start=1):
            account = accounts[candidate.account_id]
            audience = audiences.get(candidate.account_id)
            metric = metrics.get(candidate.account_id)
            collaborations = collaborations_by_account[candidate.account_id]
            rates = rates_by_account[candidate.account_id]
            historical_data_availability = history_checker.evaluate(
                collaborations,
                campaign_category=brief.product_category,
                compatible_formats=brief.content_formats,
                primary_kpi=primary_kpi,
                evaluated_at=cutoff,
            )
            valid_kpi_history = [
                item
                for item in collaborations
                if valid_history_sample(
                    item,
                    primary_kpi=primary_kpi,
                    evaluated_at=cutoff,
                )
            ]

            content_relevance = self._content(candidate)
            audience_fit = self._audience(brief, account, audience)
            performance = self._performance(
                brief,
                metric,
                valid_kpi_history,
                cohort_collaborations,
                historical_data_availability,
            )
            cost_efficiency = self._cost(brief, metric, rates)
            traffic_quality = self._traffic(audience, metric)
            delivery_reliability = self._delivery(collaborations)
            data_quality = self._data_quality(account, audience, metric, cutoff)
            snapshot_id = f"feat_{run_id}_{candidate.account_id}"
            result = CandidateFeatureRead(
                feature_snapshot_id=snapshot_id,
                account_id=candidate.account_id,
                creator_id=candidate.creator_id,
                handle=candidate.handle,
                platform=candidate.platform,
                retrieval_rank=retrieval_rank,
                keyword_rank=candidate.keyword_rank,
                vector_rank=candidate.vector_rank,
                rrf_score=candidate.rrf_score,
                feature_version=FEATURE_VERSION,
                matched_focus_terms=(
                    candidate.keyword_evidence.matched_expanded_terms
                    if candidate.keyword_evidence is not None
                    else []
                ),
                matched_campaign_terms=(
                    candidate.keyword_evidence.campaign_base_matched_terms
                    if candidate.keyword_evidence is not None
                    else []
                ),
                historical_data_availability=historical_data_availability,
                content_relevance=content_relevance,
                audience_fit=audience_fit,
                performance=performance,
                cost_efficiency=cost_efficiency,
                traffic_quality=traffic_quality,
                delivery_reliability=delivery_reliability,
                data_quality=data_quality,
                match_warnings=[
                    *candidate.match_warnings,
                    *self._history_warnings(historical_data_availability),
                ],
                risk_warnings=candidate.risk_warnings,
            )
            self.session.add(
                CandidateFeatureSnapshot(
                    feature_snapshot_id=snapshot_id,
                    run_id=run_id,
                    campaign_id=brief.campaign_id,
                    account_id=candidate.account_id,
                    feature_version=FEATURE_VERSION,
                    calculated_at=evaluated_at,
                    retrieval_rank=retrieval_rank,
                    features=result.model_dump(mode="json"),
                )
            )
            results.append(result)
        self.session.flush()
        return results

    def _content(self, candidate: HybridCandidate) -> FeatureDimension:
        keyword_score = candidate.keyword_score
        vector_raw = candidate.vector_score
        vector_scaled = clamp((vector_raw + 1.0) / 2.0) if vector_raw is not None else None
        components = {
            "keyword_relevance": value(
                score=keyword_score,
                raw_value=keyword_score,
                data_source="keyword_retriever",
                confidence=1.0,
                evidence="Campaign基础相关性40%+用户焦点词相关性60%的关键词分数。",
            ),
            "vector_similarity": value(
                score=vector_scaled,
                raw_value=vector_raw,
                data_source="pgvector_cosine_similarity",
                confidence=0.55,
                evidence="余弦相似度线性映射到0-1；当前为本地哈希Embedding基线。",
            ),
        }
        return dimension(components, {"keyword_relevance": 0.6, "vector_similarity": 0.4}, "内容相关性特征，不直接使用RRF作为适配度。")

    def _audience(self, brief: CampaignBrief, account: CreatorAccount, snapshot) -> FeatureDimension:
        if snapshot is None:
            missing = value(
                score=None,
                raw_value=None,
                data_source="audience_snapshots",
                confidence=0.0,
                evidence="无可用受众快照。",
                missing=True,
            )
            return dimension({"audience_snapshot": missing}, {}, "受众数据缺失，未进行中性填充。")

        target = brief.target_audience
        gender = target["gender_preference"]
        gender_distribution = snapshot.audience_gender_distribution
        female = float(gender_distribution.get("female", 0.0))
        male = float(gender_distribution.get("male", 0.0))
        if gender == "balanced":
            known = female + male
            gender_score = 1.0 - abs(female - male) / known if known else None
            gender_evidence = "目标性别为均衡，按已知男女受众差异计算。"
        else:
            target_share = female if gender == "female" else male
            gender_score = clamp(target_share / 0.5)
            gender_evidence = f"目标性别为{gender}，对应受众占比为{target_share:.1%}。"

        age_band = target["primary_age_band"]
        age_share = float(snapshot.audience_age_distribution.get(age_band, 0.0))
        target_interests = set(target["interest_tags"])
        audience_interests = set(snapshot.audience_interest_tags)
        matched_interests = sorted(target_interests & audience_interests)
        interest_coverage = len(matched_interests) / len(target_interests) if target_interests else 0.0
        nationwide = "全国" in brief.target_regions
        region_share = sum(float(snapshot.top_regions.get(region, 0.0)) for region in brief.target_regions)
        region_score = None if nationwide else clamp(region_share / 0.30)
        location_match = nationwide or account.region in brief.target_regions
        confidence = float(snapshot.confidence)
        components = {
            "audience_age_distribution": value(
                score=None,
                raw_value=snapshot.audience_age_distribution,
                data_source="audience_snapshots",
                as_of=snapshot.snapshot_date,
                confidence=confidence,
                evidence="年龄分布仅用于组合受众重叠代理估计，不直接计入受众适配得分。",
            ),
            "audience_region_distribution": value(
                score=None,
                raw_value=snapshot.top_regions,
                data_source="audience_snapshots",
                as_of=snapshot.snapshot_date,
                confidence=confidence,
                evidence="地区分布仅用于组合受众重叠代理估计。",
            ),
            "audience_interest_tags": value(
                score=None,
                raw_value=snapshot.audience_interest_tags,
                data_source="audience_snapshots",
                as_of=snapshot.snapshot_date,
                confidence=confidence,
                evidence="完整兴趣标签仅用于组合受众重叠代理估计。",
            ),
            "gender_fit": value(
                score=gender_score,
                raw_value=gender_distribution,
                data_source="audience_snapshots",
                as_of=snapshot.snapshot_date,
                confidence=confidence,
                evidence=gender_evidence,
            ),
            "age_fit": value(
                score=clamp(age_share / 0.30),
                raw_value=age_share,
                unit="share",
                data_source="audience_snapshots",
                as_of=snapshot.snapshot_date,
                confidence=confidence,
                evidence=f"目标年龄段{age_band}的受众占比为{age_share:.1%}。",
            ),
            "interest_fit": value(
                score=interest_coverage,
                raw_value=matched_interests,
                data_source="audience_snapshots",
                as_of=snapshot.snapshot_date,
                confidence=confidence,
                evidence=f"命中{len(matched_interests)}/{len(target_interests)}个目标兴趣标签。",
            ),
            "audience_region_coverage": value(
                score=region_score,
                raw_value=region_share,
                unit="share",
                data_source="audience_snapshots",
                as_of=snapshot.snapshot_date,
                confidence=confidence,
                evidence=(
                    "Campaign为全国投放，地区不计分。"
                    if nationwide
                    else f"已观测目标地区受众占比合计{region_share:.1%}，仅低权重参与。"
                ),
                missing=nationwide,
            ),
            "creator_location_match": value(
                score=1.0 if location_match else 0.0,
                raw_value=account.region,
                data_source="creator_accounts",
                as_of=account.collected_at,
                confidence=float(account.data_confidence),
                evidence="达人常驻地仅作运营参考；Brief未声明到店/到场要求，暂不计入受众得分。",
            ),
        }
        return dimension(
            components,
            {"gender_fit": 0.25, "age_fit": 0.35, "interest_fit": 0.30, "audience_region_coverage": 0.10},
            "受众适配度由性别、年龄、兴趣和低权重地区覆盖组成。",
        )

    def _performance(
        self,
        brief: CampaignBrief,
        metric,
        collaborations: list[Collaboration],
        cohort_collaborations: list[Collaboration],
        historical_data_availability: HistoricalDataAvailability | None = None,
    ) -> FeatureDimension:
        components = {}
        if metric is not None:
            engagement = float(metric.engagement_rate_by_followers_30d)
            reach_ratio = metric.median_views_last_30d / max(metric.follower_count, 1)
            components["median_views_30d"] = value(
                score=None,
                raw_value=metric.median_views_last_30d,
                unit="views/post",
                data_source="account_metric_snapshots",
                as_of=metric.snapshot_date,
                confidence=0.9,
                evidence=f"近30日单条内容中位播放量为{metric.median_views_last_30d:,}。",
            )
            components["engagement_rate"] = value(
                score=clamp(engagement / 0.05), raw_value=engagement, unit="rate",
                data_source="account_metric_snapshots", as_of=metric.snapshot_date, confidence=0.9,
                evidence=f"30日粉丝互动率{engagement:.2%}。",
            )
            components["median_view_reach"] = value(
                score=clamp(reach_ratio / 0.50), raw_value=reach_ratio, unit="views/follower",
                data_source="account_metric_snapshots", as_of=metric.snapshot_date, confidence=0.9,
                evidence=f"30日中位播放量约为粉丝数的{reach_ratio:.1%}。",
            )
        if collaborations:
            average_roi = fmean(float(item.roi) for item in collaborations)
            components["historical_roi"] = value(
                score=clamp(average_roi / 2.0), raw_value=average_roi, unit="ratio",
                data_source="collaborations", as_of=max(item.ended_at for item in collaborations), confidence=0.8,
                evidence=f"基于{len(collaborations)}次历史合作的平均ROI为{average_roi:.2f}。",
            )
        primary_kpi = resolve_primary_kpi(brief)
        same_category_history = [
            item
            for item in collaborations
            if item.status == "completed" and item.brand_category == brief.product_category
        ]
        cohort_rate = self._kpi_rate(
            cohort_collaborations,
            primary_kpi,
            fallback=KPI_RATE_FALLBACKS[primary_kpi],
        )
        account_numerator, account_views = self._kpi_totals(same_category_history, primary_kpi)
        blended_rate = (account_numerator + cohort_rate * KPI_PRIOR_VIEWS) / (
            account_views + KPI_PRIOR_VIEWS
        )
        if metric is not None:
            expected_primary_kpi = (
                metric.median_views_last_30d * brief.deliverables_per_creator * blended_rate
            )
            history_share = account_views / (account_views + KPI_PRIOR_VIEWS)
            if historical_data_availability is None:
                projection_confidence = 0.6 + 0.3 * history_share
                source_label = "达人同品类历史与品类基线融合"
            elif historical_data_availability.tier == "COLD_START":
                projection_confidence = 0.45
                source_label = "品类基线代理（完全冷启动）"
            elif historical_data_availability.tier == "HISTORY_LIMITED":
                projection_confidence = 0.55 + 0.25 * historical_data_availability.history_reliability
                source_label = "有限历史与品类基线融合"
            else:
                projection_confidence = 0.6 + 0.3 * history_share
                source_label = "充分历史与品类基线融合"
            components["expected_primary_kpi_baseline"] = value(
                score=None,
                raw_value=round(expected_primary_kpi, 4),
                unit=primary_kpi,
                data_source="account_metric_snapshots+same_category_collaborations",
                as_of=metric.snapshot_date,
                confidence=projection_confidence,
                evidence=(
                    f"按{metric.median_views_last_30d:,}的30日中位播放、"
                    f"{brief.deliverables_per_creator}份交付与同品类历史收缩率，"
                    f"估算基线{primary_kpi}为{expected_primary_kpi:,.2f}；{source_label}。"
                ),
            )
        if not components:
            components["performance_data"] = value(
                score=None, raw_value=None, data_source="account_metric_snapshots/collaborations",
                confidence=0.0, evidence="无可用效果数据。", missing=True,
            )
        return dimension(
            components,
            {"engagement_rate": 0.40, "median_view_reach": 0.35, "historical_roi": 0.25},
            "效果特征使用互动、播放触达与历史ROI。",
        )

    @staticmethod
    def _history_warnings(availability: HistoricalDataAvailability) -> list[MatchWarning]:
        if availability.tier == "HISTORY_LIMITED":
            return [
                MatchWarning(
                    code="LIMITED_CREATOR_HISTORY",
                    message=(
                        "历史数据有限，Fit已降低历史效果权重并提高可观测稳定性信号权重；"
                        "建议人工复核。"
                    ),
                    query_terms=[],
                )
            ]
        if availability.tier == "COLD_START":
            return [
                MatchWarning(
                    code="COLD_START_NO_ATTRIBUTED_HISTORY",
                    message=(
                        "当前Campaign口径下无有效归因历史，预测主要使用内容、受众、"
                        "流量质量及品类基线代理；建议人工复核。"
                    ),
                    query_terms=[],
                )
            ]
        return []

    @staticmethod
    def _kpi_totals(collaborations: list[Collaboration], primary_kpi: str) -> tuple[float, float]:
        numerator = 0.0
        views = 0.0
        for collaboration in collaborations:
            performance = collaboration.performance
            collaboration_views = float(performance.get("views", 0) or 0)
            kpi_value = float(performance.get(primary_kpi, 0) or 0)
            if collaboration_views > 0 and kpi_value >= 0:
                numerator += kpi_value
                views += collaboration_views
        return numerator, views

    @classmethod
    def _kpi_rate(
        cls,
        collaborations: list[Collaboration],
        primary_kpi: str,
        *,
        fallback: float,
    ) -> float:
        numerator, views = cls._kpi_totals(collaborations, primary_kpi)
        return numerator / views if views > 0 else fallback

    def _cost(self, brief: CampaignBrief, metric, rates: list[RateCard]) -> FeatureDimension:
        if not rates:
            missing = value(score=None, raw_value=None, data_source="rate_cards", confidence=0.0,
                            evidence="无当前有效且形式兼容的报价。", missing=True)
            return dimension({"effective_quote": missing}, {}, "成本数据缺失。")
        rate = min(
            rates,
            key=lambda item: float(item.base_price_cny) * (1 + float(item.agency_fee_rate)),
        )
        unit_cost = float(rate.base_price_cny) * (1 + float(rate.agency_fee_rate))
        estimated_cost = unit_cost * brief.deliverables_per_creator
        budget_ratio = estimated_cost / brief.max_budget_per_creator_cny
        components = {
            "budget_headroom": value(
                score=clamp(1.0 - budget_ratio), raw_value=budget_ratio, unit="share_of_per_creator_budget",
                data_source="rate_cards+campaign_briefs", as_of=rate.valid_from, confidence=0.95,
                evidence=f"含代理费与{brief.deliverables_per_creator}份交付的估算成本为¥{estimated_cost:,.0f}，占单人预算{budget_ratio:.1%}。",
            ),
            "estimated_cost_cny": value(
                score=None, raw_value=round(estimated_cost, 2), unit="CNY", data_source="rate_cards",
                as_of=rate.valid_from, confidence=0.95, evidence=f"选用当前最低有效{rate.content_format}报价。",
            ),
        }
        if metric is not None and metric.median_views_last_30d > 0:
            cpm = estimated_cost / metric.median_views_last_30d * 1000
            components["estimated_cpm"] = value(
                score=None, raw_value=round(cpm, 2), unit="CNY/1000 views",
                data_source="rate_cards+account_metric_snapshots", as_of=metric.snapshot_date,
                confidence=0.75, evidence=f"按30日中位播放量估算CPM为¥{cpm:.2f}，待候选池分位数归一化。",
            )
        return dimension(components, {"budget_headroom": 1.0}, "v1成本得分只表示预算余量，CPM暂作原始特征。")

    def _traffic(self, audience, metric) -> FeatureDimension:
        components = {}
        if audience is not None:
            active = float(audience.active_follower_ratio)
            suspicious = float(audience.suspicious_account_ratio_observed)
            components["active_follower_ratio"] = value(
                score=active, raw_value=active, unit="rate", data_source="audience_snapshots",
                as_of=audience.snapshot_date, confidence=float(audience.confidence), evidence=f"活跃粉丝比例{active:.1%}。",
            )
            components["audience_authenticity"] = value(
                score=1.0 - suspicious, raw_value=suspicious, unit="observed_suspicious_rate",
                data_source="audience_snapshots", as_of=audience.snapshot_date,
                confidence=float(audience.confidence), evidence=f"观测到的可疑账号比例{suspicious:.1%}。",
            )
        if metric is not None:
            repetitive = float(metric.repetitive_comment_ratio_observed)
            view_cv = float(metric.view_cv_30d)
            components["comment_authenticity"] = value(
                score=1.0 - repetitive, raw_value=repetitive, unit="observed_repetitive_rate",
                data_source="account_metric_snapshots", as_of=metric.snapshot_date, confidence=0.8,
                evidence=f"观测到的重复评论比例{repetitive:.1%}。",
            )
            components["view_stability"] = value(
                score=1.0 - clamp(view_cv), raw_value=view_cv, unit="coefficient_of_variation",
                data_source="account_metric_snapshots", as_of=metric.snapshot_date, confidence=0.8,
                evidence=f"30日播放变异系数{view_cv:.2f}。",
            )
        if not components:
            components["traffic_data"] = value(score=None, raw_value=None, data_source="audience/metrics",
                                                 confidence=0.0, evidence="无流量质量数据。", missing=True)
        return dimension(components, {name: 1.0 for name in components}, "流量质量是观测性信号，不作为作弊事实认定。")

    def _delivery(self, collaborations: list[Collaboration]) -> FeatureDimension:
        if not collaborations:
            missing = value(score=None, raw_value=None, data_source="collaborations", confidence=0.0,
                            evidence="无历史合作，不以默认中分替代。", missing=True)
            return dimension({"collaboration_history": missing}, {}, "履约数据缺失。")
        on_time = sum(item.delivered_on_time for item in collaborations) / len(collaborations)
        average_revisions = fmean(item.revision_count for item in collaborations)
        components = {
            "on_time_delivery": value(
                score=on_time, raw_value=on_time, unit="rate", data_source="collaborations",
                as_of=max(item.ended_at for item in collaborations), confidence=0.85,
                evidence=f"{len(collaborations)}次历史合作的准时交付率为{on_time:.1%}。",
            ),
            "revision_efficiency": value(
                score=1.0 - clamp(average_revisions / 3.0), raw_value=average_revisions,
                unit="average_revisions", data_source="collaborations",
                as_of=max(item.ended_at for item in collaborations), confidence=0.8,
                evidence=f"历史平均修改次数{average_revisions:.2f}。",
            ),
        }
        return dimension(components, {"on_time_delivery": 0.7, "revision_efficiency": 0.3}, "履约特征来自Campaign开始前已结束的历史合作。")

    def _data_quality(self, account, audience, metric, cutoff) -> FeatureDimension:
        components = {
            "account_confidence": value(
                score=float(account.data_confidence), raw_value=float(account.data_confidence),
                data_source="creator_accounts", as_of=account.collected_at,
                confidence=float(account.data_confidence), evidence="账号基础数据置信度。",
            )
        }
        if audience is not None:
            days = max(0, (cutoff - audience.snapshot_date).days)
            components["audience_freshness"] = value(
                score=clamp(1.0 - days / 180), raw_value=days, unit="days_old",
                data_source="audience_snapshots", as_of=audience.snapshot_date,
                confidence=float(audience.confidence), evidence=f"受众快照距运行日{days}天。",
            )
            components["audience_sample_quality"] = value(
                score=clamp(audience.sample_size / 50000), raw_value=audience.sample_size, unit="accounts",
                data_source="audience_snapshots", as_of=audience.snapshot_date,
                confidence=float(audience.confidence), evidence=f"受众样本量{audience.sample_size:,}。",
            )
        if metric is not None:
            days = max(0, (cutoff - metric.snapshot_date).days)
            components["metric_freshness"] = value(
                score=clamp(1.0 - days / 90), raw_value=days, unit="days_old",
                data_source="account_metric_snapshots", as_of=metric.snapshot_date,
                confidence=0.9, evidence=f"账号指标快照距运行日{days}天。",
            )
        return dimension(components, {name: 1.0 for name in components}, "数据质量将在后续评分中用于置信度调整。")
