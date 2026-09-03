from types import SimpleNamespace

from app.services.recommendation_explainer import (
    build_business_explanation,
    build_selection_explanations,
)


def component(raw_value):
    return SimpleNamespace(raw_value=raw_value)


def test_business_explanation_retains_evidence_without_technical_jargon():
    features = SimpleNamespace(
        matched_focus_terms=["成分", "配料表"],
        matched_campaign_terms=["食品饮料", "硬核测评"],
        content_relevance=SimpleNamespace(score=0.82),
        audience_fit=SimpleNamespace(
            score=0.76,
            components={
                "age_fit": component(0.36),
                "interest_fit": component(["品质生活"]),
            },
        ),
        performance=SimpleNamespace(
            components={
                "engagement_rate": component(0.045),
                "historical_roi": component(1.8),
            }
        ),
        delivery_reliability=SimpleNamespace(
            components={"on_time_delivery": component(1.0)}
        ),
        cost_efficiency=SimpleNamespace(
            components={
                "budget_headroom": component(0.36),
                "estimated_cost_cny": component(36_000),
            }
        ),
    )
    candidate = SimpleNamespace(
        features=features,
        risk_decision="PASS",
        missing_dimensions=[],
    )

    reasons, notes = build_business_explanation(candidate)
    statements = " ".join(reason.statement for reason in reasons)
    note_text = " ".join(notes).lower()

    assert "内容相关性82.0分" in statements
    assert "成分、配料表" in statements
    assert "历史准时交付率100.0%" in statements
    assert "估算成本占单人预算36.0%" in statements
    assert notes[0] == "内容契合度为系统初筛结果，最终合作前需人工确认。"
    assert "embedding" not in note_text
    assert "vector" not in note_text
    assert "rrf" not in note_text


def test_selection_explanations_distinguish_candidate_and_portfolio_selection():
    candidate = SimpleNamespace(
        fit_score=82.5,
        fit_rank=2,
        recommendation_rank=1,
        risk_decision="PASS",
        dimension_contributions={
            "content_relevance": SimpleNamespace(
                missing=False, contribution_points=24.6
            ),
            "audience_fit": SimpleNamespace(missing=False, contribution_points=15.2),
            "performance": SimpleNamespace(missing=False, contribution_points=9.5),
            "data_quality": SimpleNamespace(missing=True, contribution_points=0),
        },
    )
    selected = SimpleNamespace(
        primary_kpi="conversions",
        baseline_expected_primary_kpi=137.79,
        campaign_transfer_factor=0.726116,
        confidence_factor=0.946838,
        expected_primary_kpi=94.7337,
        estimated_cost_cny=16_700,
        average_audience_similarity_to_selected=0.525528,
        overlap_penalty_contribution=7.0545,
    )
    budget = SimpleNamespace(
        selected_total_cost_cny=87_595,
        total_budget_cny=100_000,
        audience_overlap_is_proxy=True,
    )

    creator_reason, combination_reason = build_selection_explanations(
        candidate, selected, budget
    )

    assert "业务适配度82.5分" in creator_reason.statement
    assert "内容相关性24.6分" in creator_reason.statement
    assert creator_reason.evidence_values["risk_decision"] == "PASS"
    assert combination_reason is not None
    assert "进入最终组合" in combination_reason.statement
    assert "预计贡献转化94.73" in combination_reason.statement
    assert "平均受众相似度52.6%" in combination_reason.statement
    assert combination_reason.evidence_values["full_overlap_impact_proxy"] == 14.109
    assert (
        combination_reason.evidence_values["estimated_marginal_objective_contribution"]
        == 80.6247
    )


def test_non_selected_candidate_has_no_portfolio_explanation():
    candidate = SimpleNamespace(
        fit_score=70.0,
        fit_rank=4,
        recommendation_rank=4,
        risk_decision="REVIEW",
        dimension_contributions={},
    )
    budget = SimpleNamespace()

    creator_reason, combination_reason = build_selection_explanations(
        candidate, None, budget
    )

    assert "进入推荐候选" in creator_reason.statement
    assert "需人工复核" in creator_reason.statement
    assert combination_reason is None
