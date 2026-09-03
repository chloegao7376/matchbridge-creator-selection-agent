from itertools import combinations
from random import Random
from types import SimpleNamespace

from app.services.budget_optimizer import BudgetOptimizer


def candidate(
    account_id: str,
    rank: int,
    score: float,
    cost: float | None,
    risk: str = "PASS",
    expected_kpi: float | None = None,
    audience_group: str = "shared",
):
    cost_component = SimpleNamespace(
        raw_value=cost,
        missing=cost is None,
    )
    audience_components = {
        "audience_age_distribution": SimpleNamespace(
            raw_value={audience_group: 1.0}, missing=False
        ),
        "audience_region_distribution": SimpleNamespace(
            raw_value={audience_group: 1.0}, missing=False
        ),
        "audience_interest_tags": SimpleNamespace(
            raw_value=[audience_group], missing=False
        ),
        "gender_fit": SimpleNamespace(
            raw_value={audience_group: 1.0}, missing=False
        ),
    }
    return SimpleNamespace(
        account_id=account_id,
        creator_id=f"creator_{account_id}",
        handle=f"handle_{account_id}",
        platform="微博",
        recommendation_rank=rank,
        fit_score=score,
        overall_confidence=1.0,
        risk_decision=risk,
        features=SimpleNamespace(
            cost_efficiency=SimpleNamespace(
                components={"estimated_cost_cny": cost_component},
            ),
            performance=SimpleNamespace(
                components={
                    "expected_primary_kpi_baseline": SimpleNamespace(
                        raw_value=score if expected_kpi is None else expected_kpi,
                        confidence=1.0,
                        missing=False,
                    )
                }
            ),
            content_relevance=SimpleNamespace(score=1.0),
            audience_fit=SimpleNamespace(score=1.0, components=audience_components),
            traffic_quality=SimpleNamespace(score=1.0),
            delivery_reliability=SimpleNamespace(score=1.0),
            data_quality=SimpleNamespace(score=1.0),
        ),
    )


def test_optimizer_maximizes_overlap_adjusted_expected_primary_kpi():
    result = BudgetOptimizer().optimize(
        [
            candidate("expensive", 1, 90, 100),
            candidate("value_a", 2, 61, 50, audience_group="a"),
            candidate("value_b", 3, 60, 50, audience_group="b"),
        ],
        total_budget_cny=100,
        target_creator_count=2,
        primary_kpi="conversions",
    )

    assert [item.account_id for item in result.selected_candidates] == ["value_a", "value_b"]
    assert result.selected_total_fit_score == 121
    assert result.selected_total_expected_primary_kpi == 121
    assert result.audience_overlap_penalty == 0
    assert result.overlap_adjusted_expected_primary_kpi == 121
    assert result.selected_total_cost_cny == 100
    assert result.staffing_status == "FULL"
    payload = result.model_dump()
    assert "suitability_weights" in payload
    assert "campaign_transfer_factor" in payload["selected_candidates"][0]
    assert "suitability_factor" not in payload["selected_candidates"][0]


def test_optimizer_respects_creator_count_and_uses_lower_cost_as_tie_breaker():
    result = BudgetOptimizer().optimize(
        [
            candidate("higher_cost", 1, 80, 80),
            candidate("lower_cost", 2, 80, 50),
            candidate("extra", 3, 70, 20),
        ],
        total_budget_cny=100,
        target_creator_count=1,
        primary_kpi="conversions",
    )

    assert [item.account_id for item in result.selected_candidates] == ["lower_cost"]
    assert result.remaining_budget_cny == 50


def test_v3_prefers_higher_expected_primary_kpi_over_higher_fit_score():
    result = BudgetOptimizer().optimize(
        [
            candidate("higher_fit", 1, 95, 50, expected_kpi=10),
            candidate("higher_kpi", 2, 70, 50, expected_kpi=20),
        ],
        total_budget_cny=50,
        target_creator_count=1,
        primary_kpi="conversions",
    )

    assert [item.account_id for item in result.selected_candidates] == ["higher_kpi"]
    assert result.selected_total_expected_primary_kpi == 20


def test_v3_penalizes_highly_overlapping_portfolio():
    result = BudgetOptimizer().optimize(
        [
            candidate("high_a", 1, 70, 50, expected_kpi=70, audience_group="same"),
            candidate("high_b", 2, 69, 50, expected_kpi=69, audience_group="same"),
            candidate("diverse", 3, 60, 50, expected_kpi=60, audience_group="different"),
        ],
        total_budget_cny=100,
        target_creator_count=2,
        primary_kpi="impressions",
    )

    assert [item.account_id for item in result.selected_candidates] == ["high_a", "diverse"]
    assert result.audience_overlap_penalty == 0
    assert result.overlap_adjusted_expected_primary_kpi == 130


def test_optimizer_excludes_review_and_missing_cost_candidates():
    result = BudgetOptimizer().optimize(
        [
            candidate("review", 1, 99, 10, risk="REVIEW"),
            candidate("missing", 2, 98, None),
            candidate("pass", 3, 70, 60),
        ],
        total_budget_cny=100,
        target_creator_count=2,
        primary_kpi="conversions",
    )

    assert [item.account_id for item in result.selected_candidates] == ["pass"]
    assert result.staffing_status == "PARTIAL"
    assert len(result.warnings) == 4


def test_optimizer_respects_locked_and_excluded_human_decisions():
    result = BudgetOptimizer().optimize(
        [
            candidate("best", 1, 100, 50, audience_group="best"),
            candidate("locked", 2, 40, 50, audience_group="locked"),
            candidate("other", 3, 80, 50, audience_group="other"),
        ],
        total_budget_cny=100,
        target_creator_count=2,
        primary_kpi="conversions",
        required_account_ids={"locked"},
        excluded_account_ids={"best"},
    )

    assert [item.account_id for item in result.selected_candidates] == ["locked", "other"]


def test_optimizer_allows_review_only_after_human_clearance():
    candidates = [
        candidate("review", 1, 100, 50, risk="REVIEW", audience_group="review"),
        candidate("pass", 2, 50, 50, audience_group="pass"),
    ]

    without_clearance = BudgetOptimizer().optimize(
        candidates,
        total_budget_cny=50,
        target_creator_count=1,
        primary_kpi="conversions",
    )
    with_clearance = BudgetOptimizer().optimize(
        candidates,
        total_budget_cny=50,
        target_creator_count=1,
        primary_kpi="conversions",
        allowed_review_account_ids={"review"},
    )

    assert [item.account_id for item in without_clearance.selected_candidates] == ["pass"]
    assert [item.account_id for item in with_clearance.selected_candidates] == ["review"]


def test_sparse_optimizer_matches_brute_force_on_small_random_cases():
    random = Random(20260902)
    for _ in range(20):
        candidates = [
            candidate(f"c{index}", index + 1, random.randint(1, 100), random.randint(1, 80))
            for index in range(7)
        ]
        budget = random.randint(40, 180)
        target_count = random.randint(1, 4)
        result = BudgetOptimizer().optimize(
            candidates,
            total_budget_cny=budget,
            target_creator_count=target_count,
            primary_kpi="conversions",
        )

        feasible = []
        for count in range(1, target_count + 1):
            for group in combinations(candidates, count):
                total_cost = sum(item.features.cost_efficiency.components["estimated_cost_cny"].raw_value for item in group)
                if total_cost <= budget:
                    gross = sum(item.fit_score for item in group)
                    pair_penalty = sum(
                        min(left.fit_score, right.fit_score)
                        for left, right in combinations(group, 2)
                    ) / max(target_count - 1, 1)
                    objective_units = round(gross * 1_000_000) - round(
                        pair_penalty * 1_000_000
                    )
                    feasible.append((objective_units, gross, total_cost))
        expected_units, expected_score, expected_cost = min(
            feasible,
            key=lambda item: (-item[0], -item[1], item[2]),
        )
        assert result.overlap_adjusted_expected_primary_kpi == round(expected_units / 1_000_000, 4)
        assert result.selected_total_fit_score == expected_score
        assert result.selected_total_cost_cny == expected_cost
