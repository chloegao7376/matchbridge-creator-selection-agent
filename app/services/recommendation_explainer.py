from __future__ import annotations

from app.schemas.budget import BudgetOptimizationSummary, BudgetSelectedCandidate
from app.schemas.ranking import RankedCandidate
from app.schemas.recommendation import RecommendationReason

DIMENSION_LABELS = {
    "content_relevance": "内容相关性",
    "audience_fit": "受众适配度",
    "performance": "历史效果",
    "cost_efficiency": "成本效率",
    "traffic_quality": "流量质量",
    "delivery_reliability": "履约能力",
    "data_quality": "数据质量",
}
KPI_LABELS = {
    "impressions": "曝光",
    "engagements": "互动",
    "conversions": "转化",
}


def as_percent(number: float) -> str:
    return f"{number:.1%}"


def build_business_explanation(candidate: RankedCandidate) -> tuple[list[RecommendationReason], list[str]]:
    features = candidate.features
    reasons: list[RecommendationReason] = []

    content_score = features.content_relevance.score
    if content_score is not None:
        matched_terms = list(dict.fromkeys([*features.matched_focus_terms, *features.matched_campaign_terms]))
        match_text = f"；近期内容命中：{'、'.join(matched_terms[:6])}" if matched_terms else ""
        reasons.append(
            RecommendationReason(
                dimension="content_relevance",
                statement=f"内容相关性{content_score * 100:.1f}分{match_text}。",
                evidence_values={
                    "content_relevance_score": round(content_score, 6),
                    "matched_terms": matched_terms,
                },
            )
        )

    audience = features.audience_fit
    if audience.score is not None:
        age = audience.components.get("age_fit")
        interests = audience.components.get("interest_fit")
        evidence_parts = []
        evidence_values = {"audience_fit_score": audience.score}
        if age is not None and age.raw_value is not None:
            evidence_parts.append(f"目标年龄段受众占比{as_percent(float(age.raw_value))}")
            evidence_values["target_age_share"] = age.raw_value
        if interests is not None and interests.raw_value:
            evidence_parts.append(f"命中兴趣标签{'、'.join(interests.raw_value)}")
            evidence_values["matched_interest_tags"] = interests.raw_value
        suffix = f"；{'；'.join(evidence_parts)}" if evidence_parts else ""
        reasons.append(
            RecommendationReason(
                dimension="audience_fit",
                statement=f"受众适配度{audience.score * 100:.1f}分{suffix}。",
                evidence_values=evidence_values,
            )
        )

    performance = features.performance.components
    engagement = performance.get("engagement_rate")
    historical_roi = performance.get("historical_roi")
    if engagement is not None and engagement.raw_value is not None:
        statement = f"近30日粉丝互动率{as_percent(float(engagement.raw_value))}"
        evidence_values = {"engagement_rate_30d": engagement.raw_value}
        if historical_roi is not None and historical_roi.raw_value is not None:
            statement += f"，历史平均ROI {float(historical_roi.raw_value):.2f}"
            evidence_values["historical_average_roi"] = historical_roi.raw_value
        reasons.append(
            RecommendationReason(
                dimension="performance",
                statement=f"{statement}。",
                evidence_values=evidence_values,
            )
        )

    delivery = features.delivery_reliability.components.get("on_time_delivery")
    if delivery is not None and delivery.raw_value is not None:
        reasons.append(
            RecommendationReason(
                dimension="delivery_reliability",
                statement=f"历史准时交付率{as_percent(float(delivery.raw_value))}。",
                evidence_values={"historical_on_time_delivery_rate": delivery.raw_value},
            )
        )

    cost = features.cost_efficiency.components
    budget = cost.get("budget_headroom")
    estimated_cost = cost.get("estimated_cost_cny")
    if budget is not None and budget.raw_value is not None:
        budget_ratio = float(budget.raw_value)
        statement = f"估算成本占单人预算{as_percent(budget_ratio)}"
        evidence_values = {"per_creator_budget_share": budget_ratio}
        if estimated_cost is not None and estimated_cost.raw_value is not None:
            statement += f"，估算金额¥{float(estimated_cost.raw_value):,.0f}"
            evidence_values["estimated_cost_cny"] = estimated_cost.raw_value
        reasons.append(
            RecommendationReason(
                dimension="cost_efficiency",
                statement=f"{statement}。",
                evidence_values=evidence_values,
            )
        )

    notes = ["内容契合度为系统初筛结果，最终合作前需人工确认。"]
    history = getattr(features, "historical_data_availability", None)
    if history is not None and history.tier == "HISTORY_LIMITED":
        notes.append(
            f"历史数据有限（有效历史样本量{history.effective_history_n:.2f}），"
            "已降低历史效果权重并提高稳定性信号权重，建议人工复核。"
        )
    elif history is not None and history.tier == "COLD_START":
        notes.append(
            "该达人属于完全冷启动，当前结果主要依据可观测稳定性信号和品类基线代理，"
            "不代表已有历史转化验证，建议人工复核。"
        )
    if estimated_cost is not None and estimated_cost.raw_value is not None:
        notes.append("当前金额为估算成本，最终以商务确认的报价、权益和税费为准。")
    if candidate.risk_decision == "REVIEW":
        notes.append("该达人存在待复核风险线索，需在确认合作前完成人工审核。")
    if candidate.missing_dimensions:
        notes.append(f"部分评估数据缺失：{', '.join(candidate.missing_dimensions)}。")
    return reasons, notes


def build_selection_explanations(
    candidate: RankedCandidate,
    selected: BudgetSelectedCandidate | None,
    budget: BudgetOptimizationSummary,
) -> tuple[RecommendationReason, RecommendationReason | None]:
    """Explain candidate-level selection and, when applicable, portfolio inclusion."""
    strongest_dimensions = sorted(
        (
            (name, contribution)
            for name, contribution in candidate.dimension_contributions.items()
            if not contribution.missing and contribution.contribution_points > 0
        ),
        key=lambda item: (-item[1].contribution_points, item[0]),
    )[:3]
    contribution_evidence = {
        name: round(contribution.contribution_points, 4)
        for name, contribution in strongest_dimensions
    }
    contribution_text = "、".join(
        f"{DIMENSION_LABELS.get(name, name)}{contribution.contribution_points:.1f}分"
        for name, contribution in strongest_dimensions
    )
    risk_text = (
        "当前风险审核结果为PASS"
        if candidate.risk_decision == "PASS"
        else "当前风险审核结果为REVIEW，合作前仍需人工复核"
    )
    strengths_text = f"；主要评分贡献为{contribution_text}" if contribution_text else ""
    why_this_creator = RecommendationReason(
        dimension="candidate_selection",
        statement=(
            f"该达人以业务适配度{candidate.fit_score:.1f}分进入推荐候选，"
            f"{risk_text}{strengths_text}。"
        ),
        evidence_values={
            "fit_score": round(candidate.fit_score, 4),
            "fit_rank": candidate.fit_rank,
            "final_rank": candidate.recommendation_rank,
            "risk_decision": candidate.risk_decision,
            "top_dimension_contributions": contribution_evidence,
        },
    )

    if selected is None:
        return why_this_creator, None

    kpi_label = KPI_LABELS.get(selected.primary_kpi, selected.primary_kpi)
    selected_cost_share = (
        selected.estimated_cost_cny / budget.selected_total_cost_cny
        if budget.selected_total_cost_cny > 0
        else 0.0
    )
    total_budget_share = selected.estimated_cost_cny / budget.total_budget_cny
    # The optimizer allocates each pairwise penalty equally to its two creators.
    # Removing one creator affects both allocated halves, so the full pair impact is 2x.
    full_overlap_impact = selected.overlap_penalty_contribution * 2
    marginal_objective_contribution = selected.expected_primary_kpi - full_overlap_impact
    why_in_final_combination = RecommendationReason(
        dimension="portfolio_selection",
        statement=(
            f"该达人进入最终组合：预计贡献{kpi_label}{selected.expected_primary_kpi:.2f}，"
            f"Campaign迁移系数{as_percent(selected.campaign_transfer_factor)}，"
            f"置信修正系数{as_percent(selected.confidence_factor)}；"
            f"估算报价¥{selected.estimated_cost_cny:,.0f}，占组合总报价{as_percent(selected_cost_share)}。"
            f"与其他入选达人平均受众相似度{as_percent(selected.average_audience_similarity_to_selected)}，"
            f"计入完整重叠代理影响后，估算边际目标贡献约{kpi_label}{marginal_objective_contribution:.2f}，"
            "因此在预算约束下有助于提升组合目标。"
        ),
        evidence_values={
            "primary_kpi": selected.primary_kpi,
            "baseline_expected_primary_kpi": selected.baseline_expected_primary_kpi,
            "campaign_transfer_factor": selected.campaign_transfer_factor,
            "confidence_factor": selected.confidence_factor,
            "expected_primary_kpi": selected.expected_primary_kpi,
            "estimated_cost_cny": selected.estimated_cost_cny,
            "selected_cost_share": round(selected_cost_share, 6),
            "total_budget_share": round(total_budget_share, 6),
            "average_audience_similarity_to_selected": (
                selected.average_audience_similarity_to_selected
            ),
            "allocated_overlap_penalty": selected.overlap_penalty_contribution,
            "full_overlap_impact_proxy": round(full_overlap_impact, 4),
            "estimated_marginal_objective_contribution": round(
                marginal_objective_contribution, 4
            ),
            "audience_overlap_is_proxy": budget.audience_overlap_is_proxy,
        },
    )
    return why_this_creator, why_in_final_combination
