from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from statistics import fmean

from sqlalchemy.orm import Session

from app.models import CandidateScoreSnapshot
from app.schemas.features import CandidateFeatureRead, FeatureDimension
from app.schemas.ranking import DimensionContribution, RankedCandidate

SCORING_VERSION = "fit_scoring_v2_history_tiering"
NEUTRAL_PRIOR = 0.5
DIMENSION_WEIGHTS = {
    "content_relevance": 0.30,
    "audience_fit": 0.20,
    "performance": 0.15,
    "cost_efficiency": 0.10,
    "traffic_quality": 0.10,
    "delivery_reliability": 0.10,
    "data_quality": 0.05,
}
CONFIDENCE_POLICY = "dimension_score * confidence + 0.5 * (1 - confidence)"
MISSING_VALUE_POLICY = "renormalize available weights, then multiply by 0.7 + 0.3 * feature_coverage"
LIMITED_HISTORY_REDISTRIBUTION = {
    "content_relevance": 0.40,
    "audience_fit": 0.30,
    "traffic_quality": 0.20,
    "data_quality": 0.10,
}
COLD_START_WEIGHTS = {
    "content_relevance": 0.36,
    "audience_fit": 0.24,
    "performance": 0.0,
    "cost_efficiency": 0.10,
    "traffic_quality": 0.13,
    "delivery_reliability": 0.10,
    "data_quality": 0.07,
}
HISTORY_WEIGHT_POLICY = (
    "历史有限时按可靠度保留历史效果权重，释放部分按内容40%/受众30%/流量20%/数据10%分配；"
    "完全冷启动使用系统固定冷启动权重。"
)


def scoring_version_for(fit_mode: str, weights: dict[str, float]) -> str:
    if fit_mode == "default":
        return SCORING_VERSION
    serialized = json.dumps(weights, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode()).hexdigest()[:10]
    return f"fit_custom_v1_{digest}"


def dimension_confidence(dimension: FeatureDimension) -> float:
    confidences = [
        component.confidence
        for component in dimension.components.values()
        if not component.missing and component.score is not None
    ]
    return fmean(confidences) if confidences else 0.0


def effective_dimension_weights(
    feature: CandidateFeatureRead, base_weights: dict[str, float]
) -> dict[str, float]:
    availability = feature.historical_data_availability
    if availability.tier == "HISTORY_SUFFICIENT":
        return dict(base_weights)
    if availability.tier == "COLD_START":
        return dict(COLD_START_WEIGHTS)

    reliability = availability.history_reliability
    released_weight = base_weights["performance"] * (1.0 - reliability)
    weights = dict(base_weights)
    weights["performance"] = base_weights["performance"] * reliability
    for name, share in LIMITED_HISTORY_REDISTRIBUTION.items():
        weights[name] += released_weight * share
    return {name: round(weight, 10) for name, weight in weights.items()}


class FitRanker:
    def __init__(self, session: Session | None) -> None:
        self.session = session

    def rank(
        self,
        features: list[CandidateFeatureRead],
        *,
        run_id: str,
        campaign_id: str,
        evaluated_at: datetime,
        dimension_weights: dict[str, float] | None = None,
        scoring_version: str = SCORING_VERSION,
        persist: bool = True,
    ) -> list[RankedCandidate]:
        weights = dimension_weights or DIMENSION_WEIGHTS
        if set(weights) != set(DIMENSION_WEIGHTS) or abs(sum(weights.values()) - 1.0) > 1e-6:
            raise ValueError("dimension weights must contain all seven dimensions and sum to 1.0")
        drafts = [self._score(feature, weights) for feature in features]
        fit_order = sorted(drafts, key=lambda draft: (-draft["fit_score"], draft["feature"].retrieval_rank))
        fit_ranks = {draft["feature"].account_id: rank for rank, draft in enumerate(fit_order, start=1)}
        recommendation_order = sorted(
            drafts,
            key=lambda draft: (
                0 if draft["risk_decision"] == "PASS" else 1,
                -draft["fit_score"],
                draft["feature"].retrieval_rank,
            ),
        )

        results = []
        for recommendation_rank, draft in enumerate(recommendation_order, start=1):
            feature = draft["feature"]
            score_snapshot_id = f"score_{run_id}_{feature.account_id}"
            result = RankedCandidate(
                score_snapshot_id=score_snapshot_id,
                account_id=feature.account_id,
                creator_id=feature.creator_id,
                handle=feature.handle,
                platform=feature.platform,
                retrieval_rank=feature.retrieval_rank,
                fit_rank=fit_ranks[feature.account_id],
                recommendation_rank=recommendation_rank,
                fit_score=draft["fit_score"],
                feature_coverage=draft["feature_coverage"],
                overall_confidence=draft["overall_confidence"],
                missing_dimensions=draft["missing_dimensions"],
                risk_decision=draft["risk_decision"],
                dimension_contributions=draft["dimension_contributions"],
                score_explanation=draft["score_explanation"],
                features=feature,
            )
            if persist:
                if self.session is None:
                    raise ValueError("a database session is required when persist=True")
                self.session.add(
                    CandidateScoreSnapshot(
                        score_snapshot_id=score_snapshot_id,
                        feature_snapshot_id=feature.feature_snapshot_id,
                        run_id=run_id,
                        campaign_id=campaign_id,
                        account_id=feature.account_id,
                        scoring_version=scoring_version,
                        calculated_at=evaluated_at,
                        fit_score=Decimal(str(result.fit_score)),
                        fit_rank=result.fit_rank,
                        recommendation_rank=result.recommendation_rank,
                        risk_decision=result.risk_decision,
                        scoring_detail=result.model_dump(mode="json", exclude={"features"}),
                    )
                )
            results.append(result)
        if persist and self.session is not None:
            self.session.flush()
        return results

    def _score(self, feature: CandidateFeatureRead, weights: dict[str, float]) -> dict:
        weights = effective_dimension_weights(feature, weights)
        dimensions = {name: getattr(feature, name) for name in weights}
        available_weight = sum(
            weights[name] for name, dimension in dimensions.items() if dimension.score is not None
        )
        feature_coverage = round(available_weight, 6)
        coverage_factor = 0.7 + 0.3 * feature_coverage
        contributions = {}
        confidence_weighted_sum = 0.0
        total_points = 0.0
        missing_dimensions = []
        for name, dimension in dimensions.items():
            weight = weights[name]
            confidence = dimension_confidence(dimension)
            if dimension.score is None:
                missing_dimensions.append(name)
                contributions[name] = DimensionContribution(
                    weight=weight,
                    raw_score=None,
                    confidence=0.0,
                    confidence_adjusted_score=None,
                    contribution_points=0.0,
                    missing=True,
                )
                continue
            adjusted = dimension.score * confidence + NEUTRAL_PRIOR * (1.0 - confidence)
            points = weight * adjusted / available_weight * coverage_factor * 100 if available_weight else 0.0
            total_points += points
            confidence_weighted_sum += weight * confidence
            contributions[name] = DimensionContribution(
                weight=weight,
                raw_score=dimension.score,
                confidence=round(confidence, 6),
                confidence_adjusted_score=round(adjusted, 6),
                contribution_points=round(points, 4),
                missing=False,
            )

        fit_score = round(total_points, 4)
        overall_confidence = (
            round(confidence_weighted_sum / available_weight, 6) if available_weight else 0.0
        )
        present = [(name, contribution) for name, contribution in contributions.items() if not contribution.missing]
        strongest = sorted(present, key=lambda item: item[1].contribution_points, reverse=True)[:2]
        explanations = [
            f"{name}贡献{contribution.contribution_points:.2f}分（原始得分"
            f"{contribution.raw_score:.3f}，置信度{contribution.confidence:.3f}）"
            for name, contribution in strongest
        ]
        if missing_dimensions:
            explanations.append(
                f"缺失维度：{', '.join(missing_dimensions)}；已重新归一化可用权重并施加覆盖率惩罚。"
            )
        if feature.historical_data_availability.tier != "HISTORY_SUFFICIENT":
            explanations.append(
                f"historical-data-availability-checker：{feature.historical_data_availability.tier_label}；"
                "已应用对应的系统权重与置信度策略。"
            )
        risk_decision = "REVIEW" if feature.risk_warnings else "PASS"
        if risk_decision == "REVIEW":
            explanations.append("适配度未因风险扣分；该候选人存在待复核风险线索。")
        return {
            "feature": feature,
            "fit_score": fit_score,
            "feature_coverage": feature_coverage,
            "overall_confidence": overall_confidence,
            "missing_dimensions": missing_dimensions,
            "risk_decision": risk_decision,
            "dimension_contributions": contributions,
            "score_explanation": explanations,
        }
