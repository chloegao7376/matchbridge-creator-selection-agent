from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.schemas.budget import BudgetOptimizationSummary, BudgetSelectedCandidate
from app.schemas.ranking import RankedCandidate

SUITABILITY_WEIGHTS = {
    "content_relevance": 0.50,
    "audience_fit": 0.35,
    "traffic_quality": 0.10,
    "delivery_reliability": 0.05,
}
AUDIENCE_SIMILARITY_WEIGHTS = {
    "age_distribution_overlap": 0.35,
    "region_distribution_overlap": 0.30,
    "interest_tag_similarity": 0.20,
    "gender_distribution_overlap": 0.15,
}
KPI_SCALE = 1_000_000


@dataclass(frozen=True)
class _AudienceProfile:
    age: dict[str, float] | None
    region: dict[str, float] | None
    interests: frozenset[str] | None
    gender: dict[str, float] | None

    @property
    def complete(self) -> bool:
        return all(value is not None for value in (self.age, self.region, self.interests, self.gender))


@dataclass(frozen=True)
class _Candidate:
    ranked: RankedCandidate
    cost_fen: int
    expected_kpi_units: int
    fit_units: int
    baseline_expected_primary_kpi: float
    campaign_transfer_factor: float
    confidence_factor: float
    expected_primary_kpi: float
    audience: _AudienceProfile


@dataclass(frozen=True)
class _State:
    gross_kpi_units: int
    pair_penalty_units: int
    fit_units: int
    cost_fen: int
    selected_indices: tuple[int, ...]


def _to_fen(amount: float | Decimal) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _estimated_cost(candidate: RankedCandidate) -> float | None:
    component = candidate.features.cost_efficiency.components.get("estimated_cost_cny")
    if component is None or component.missing or component.raw_value is None:
        return None
    cost = float(component.raw_value)
    return cost if cost > 0 else None


def _kpi_projection(candidate: RankedCandidate) -> tuple[float, float] | None:
    component = candidate.features.performance.components.get("expected_primary_kpi_baseline")
    if component is None or component.missing or component.raw_value is None:
        return None
    baseline = float(component.raw_value)
    if baseline < 0:
        return None
    return baseline, float(component.confidence)


def _campaign_transfer_factor(candidate: RankedCandidate) -> float:
    available = []
    for name, weight in SUITABILITY_WEIGHTS.items():
        score = getattr(candidate.features, name).score
        if score is not None:
            available.append((score, weight))
    if not available:
        return 0.0
    return sum(score * weight for score, weight in available) / sum(weight for _, weight in available)


def _component_raw(candidate: RankedCandidate, name: str):
    component = candidate.features.audience_fit.components.get(name)
    if component is None or component.missing:
        return None
    return component.raw_value


def _as_distribution(raw) -> dict[str, float] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    distribution = {str(key): max(0.0, float(value)) for key, value in raw.items()}
    total = sum(distribution.values())
    if total <= 0:
        return None
    if total < 1.0:
        distribution["__other__"] = 1.0 - total
        total = 1.0
    return {key: value / total for key, value in distribution.items()}


def _audience_profile(candidate: RankedCandidate) -> _AudienceProfile:
    interests_raw = _component_raw(candidate, "audience_interest_tags")
    interests = (
        frozenset(str(item) for item in interests_raw)
        if isinstance(interests_raw, list) and interests_raw
        else None
    )
    return _AudienceProfile(
        age=_as_distribution(_component_raw(candidate, "audience_age_distribution")),
        region=_as_distribution(_component_raw(candidate, "audience_region_distribution")),
        interests=interests,
        gender=_as_distribution(_component_raw(candidate, "gender_fit")),
    )


def _distribution_overlap(left: dict[str, float] | None, right: dict[str, float] | None) -> float:
    if left is None or right is None:
        return 0.5
    return sum(min(left.get(key, 0.0), right.get(key, 0.0)) for key in left.keys() | right.keys())


def _interest_similarity(left: frozenset[str] | None, right: frozenset[str] | None) -> float:
    if left is None or right is None:
        return 0.5
    union = left | right
    return len(left & right) / len(union) if union else 0.5


def audience_similarity(left: _AudienceProfile, right: _AudienceProfile) -> float:
    components = {
        "age_distribution_overlap": _distribution_overlap(left.age, right.age),
        "region_distribution_overlap": _distribution_overlap(left.region, right.region),
        "interest_tag_similarity": _interest_similarity(left.interests, right.interests),
        "gender_distribution_overlap": _distribution_overlap(left.gender, right.gender),
    }
    return sum(components[name] * weight for name, weight in AUDIENCE_SIMILARITY_WEIGHTS.items())


def _objective_units(state: _State, penalty_denominator: int) -> int:
    normalized_penalty = round(state.pair_penalty_units / penalty_denominator)
    return max(0, state.gross_kpi_units - normalized_penalty)


def _state_sort_key(state: _State, penalty_denominator: int):
    return (
        -_objective_units(state, penalty_denominator),
        -state.gross_kpi_units,
        -state.fit_units,
        state.cost_fen,
        state.selected_indices,
    )


class BudgetOptimizer:
    """Beam-search a budget-feasible portfolio with a pairwise audience-overlap proxy."""

    def optimize(
        self,
        candidates: list[RankedCandidate],
        *,
        total_budget_cny: float,
        target_creator_count: int,
        primary_kpi: str,
        required_account_ids: set[str] | None = None,
        excluded_account_ids: set[str] | None = None,
        allowed_review_account_ids: set[str] | None = None,
    ) -> BudgetOptimizationSummary:
        required_account_ids = required_account_ids or set()
        excluded_account_ids = excluded_account_ids or set()
        allowed_review_account_ids = allowed_review_account_ids or set()
        if required_account_ids & excluded_account_ids:
            raise ValueError("the same creator cannot be both required and excluded")
        budget_fen = _to_fen(total_budget_cny)
        prepared: list[_Candidate] = []
        missing_cost_count = 0
        missing_kpi_count = 0
        incomplete_overlap_count = 0
        review_count = 0
        cold_start_count = 0
        for ranked in sorted(candidates, key=lambda item: item.recommendation_rank):
            if ranked.account_id in excluded_account_ids:
                continue
            history = getattr(ranked.features, "historical_data_availability", None)
            if (
                getattr(history, "tier", "HISTORY_SUFFICIENT") == "COLD_START"
                and ranked.account_id not in required_account_ids
            ):
                cold_start_count += 1
                continue
            if (
                ranked.risk_decision != "PASS"
                and ranked.account_id not in allowed_review_account_ids
            ):
                review_count += 1
                continue
            cost = _estimated_cost(ranked)
            if cost is None:
                missing_cost_count += 1
                continue
            projection = _kpi_projection(ranked)
            if projection is None:
                missing_kpi_count += 1
                continue
            cost_fen = _to_fen(cost)
            if cost_fen > budget_fen:
                continue
            baseline_kpi, projection_confidence = projection
            transfer_factor = _campaign_transfer_factor(ranked)
            confidence_factor = 0.7 + 0.3 * min(projection_confidence, ranked.overall_confidence)
            expected_primary_kpi = baseline_kpi * transfer_factor * confidence_factor
            profile = _audience_profile(ranked)
            if not profile.complete:
                incomplete_overlap_count += 1
            prepared.append(
                _Candidate(
                    ranked=ranked,
                    cost_fen=cost_fen,
                    expected_kpi_units=round(expected_primary_kpi * KPI_SCALE),
                    fit_units=round(ranked.fit_score * 10_000),
                    baseline_expected_primary_kpi=baseline_kpi,
                    campaign_transfer_factor=transfer_factor,
                    confidence_factor=confidence_factor,
                    expected_primary_kpi=expected_primary_kpi,
                    audience=profile,
                )
            )

        prepared_by_account = {item.ranked.account_id: index for index, item in enumerate(prepared)}
        missing_required = required_account_ids - prepared_by_account.keys()
        if missing_required:
            raise ValueError(
                "required creators are not eligible for optimization: "
                + ", ".join(sorted(missing_required))
            )
        required_indices = tuple(
            sorted(prepared_by_account[account_id] for account_id in required_account_ids)
        )
        if len(required_indices) > target_creator_count:
            raise ValueError("required creator count exceeds campaign target creator count")

        max_count = min(target_creator_count, len(prepared))
        penalty_denominator = max(target_creator_count - 1, 1)
        beam_width = 500 if max_count <= 15 else 150
        similarities = [
            [audience_similarity(left.audience, right.audience) for right in prepared]
            for left in prepared
        ]
        required_cost = sum(prepared[index].cost_fen for index in required_indices)
        if required_cost > budget_fen:
            raise ValueError("required creators exceed the campaign total budget")
        required_pair_penalty = sum(
            round(
                similarities[left_index][right_index]
                * min(
                    prepared[left_index].expected_kpi_units,
                    prepared[right_index].expected_kpi_units,
                )
            )
            for position, left_index in enumerate(required_indices)
            for right_index in required_indices[position + 1 :]
        )
        base_state = _State(
            gross_kpi_units=sum(prepared[index].expected_kpi_units for index in required_indices),
            pair_penalty_units=required_pair_penalty,
            fit_units=sum(prepared[index].fit_units for index in required_indices),
            cost_fen=required_cost,
            selected_indices=required_indices,
        )
        beams: list[list[_State]] = [[] for _ in range(max_count + 1)]
        required_count = len(required_indices)
        beams[required_count] = [base_state]
        optional_indices = [index for index in range(len(prepared)) if index not in required_indices]
        for optional_position, index in enumerate(optional_indices):
            candidate = prepared[index]
            upper_count = min(max_count, required_count + optional_position + 1)
            for count in range(upper_count, required_count, -1):
                additions = []
                for prior in beams[count - 1]:
                    new_cost = prior.cost_fen + candidate.cost_fen
                    if new_cost > budget_fen:
                        continue
                    pair_increment = sum(
                        round(
                            similarities[index][prior_index]
                            * min(
                                candidate.expected_kpi_units,
                                prepared[prior_index].expected_kpi_units,
                            )
                        )
                        for prior_index in prior.selected_indices
                    )
                    additions.append(
                        _State(
                            gross_kpi_units=prior.gross_kpi_units + candidate.expected_kpi_units,
                            pair_penalty_units=prior.pair_penalty_units + pair_increment,
                            fit_units=prior.fit_units + candidate.fit_units,
                            cost_fen=new_cost,
                            selected_indices=(*prior.selected_indices, index),
                        )
                    )
                beams[count] = sorted(
                    [*beams[count], *additions],
                    key=lambda state: _state_sort_key(state, penalty_denominator),
                )[:beam_width]

        solutions = [
            state
            for count, count_beam in enumerate(beams)
            if count >= max(required_count, 1)
            for state in count_beam
        ]
        if required_count and not solutions:
            solutions = [base_state]
        if solutions:
            selected_state = min(
                solutions,
                key=lambda state: _state_sort_key(state, penalty_denominator),
            )
            selected_items = [prepared[index] for index in selected_state.selected_indices]
        else:
            selected_state = _State(0, 0, 0, 0, ())
            selected_items = []

        selected_candidates = []
        for item_index, item in zip(selected_state.selected_indices, selected_items, strict=True):
            other_indices = [index for index in selected_state.selected_indices if index != item_index]
            similarities_to_selected = [
                similarities[item_index][other_index] for other_index in other_indices
            ]
            raw_pair_contribution = sum(
                similarities[item_index][other_index]
                * min(item.expected_kpi_units, prepared[other_index].expected_kpi_units)
                / KPI_SCALE
                for other_index in other_indices
            )
            selected_candidates.append(
                BudgetSelectedCandidate(
                    account_id=item.ranked.account_id,
                    creator_id=item.ranked.creator_id,
                    handle=item.ranked.handle,
                    platform=item.ranked.platform,
                    final_rank=item.ranked.recommendation_rank,
                    fit_score=item.ranked.fit_score,
                    estimated_cost_cny=float(_estimated_cost(item.ranked)),
                    primary_kpi=primary_kpi,
                    baseline_expected_primary_kpi=round(item.baseline_expected_primary_kpi, 4),
                    campaign_transfer_factor=round(item.campaign_transfer_factor, 6),
                    confidence_factor=round(item.confidence_factor, 6),
                    expected_primary_kpi=round(item.expected_primary_kpi, 4),
                    average_audience_similarity_to_selected=(
                        round(sum(similarities_to_selected) / len(similarities_to_selected), 6)
                        if similarities_to_selected
                        else 0
                    ),
                    overlap_penalty_contribution=round(
                        raw_pair_contribution / (2 * penalty_denominator),
                        4,
                    ),
                )
            )

        selected_count = len(selected_candidates)
        staffing_status = (
            "EMPTY"
            if selected_count == 0
            else "FULL"
            if selected_count == target_creator_count
            else "PARTIAL"
        )
        warnings = []
        if cold_start_count:
            warnings.append(
                f"{cold_start_count}位完全冷启动候选未被自动纳入预算组合；"
                "需人工明确加入并锁定后，才可参与重新优化。"
            )
        if review_count:
            warnings.append(f"{review_count}位REVIEW候选未被自动纳入预算组合，需人工复核后再决定。")
        if missing_cost_count:
            warnings.append(f"{missing_cost_count}位PASS候选因缺少有效估算成本未进入组合优化。")
        if missing_kpi_count:
            warnings.append(f"{missing_kpi_count}位PASS候选因缺少主KPI预测基线未进入组合优化。")
        if incomplete_overlap_count:
            warnings.append(
                f"{incomplete_overlap_count}位候选的受众分布不完整，缺失的相似度分项使用0.5中性代理值。"
            )
        if staffing_status != "FULL":
            warnings.append(
                f"当前组合选中{selected_count}位，未达到Brief目标{target_creator_count}位；"
                "可能由预算、风险资格、数据缺失或重叠惩罚后的非正边际效用造成。"
            )
        warnings.append(
            "audience_overlap是基于受众分布的代理估计，不是真实粉丝去重结果；"
            "获得平台侧去重触达数据后应替换为真正的边际KPI模型。"
        )

        total_budget = budget_fen / 100
        selected_cost = selected_state.cost_fen / 100
        gross_kpi = selected_state.gross_kpi_units / KPI_SCALE
        overlap_penalty = selected_state.pair_penalty_units / KPI_SCALE / penalty_denominator
        objective_value = max(0.0, gross_kpi - overlap_penalty)
        total_fit = selected_state.fit_units / 10_000
        return BudgetOptimizationSummary(
            staffing_status=staffing_status,
            primary_kpi=primary_kpi,
            total_budget_cny=total_budget,
            target_creator_count=target_creator_count,
            eligible_candidate_count=len(prepared),
            selected_creator_count=selected_count,
            selected_total_cost_cny=selected_cost,
            remaining_budget_cny=round(total_budget - selected_cost, 2),
            budget_utilization=round(selected_cost / total_budget, 6),
            selected_total_expected_primary_kpi=round(gross_kpi, 4),
            selected_average_expected_primary_kpi=(
                round(gross_kpi / selected_count, 4) if selected_count else 0
            ),
            audience_overlap_penalty=round(overlap_penalty, 4),
            overlap_adjusted_expected_primary_kpi=round(objective_value, 4),
            selected_total_fit_score=round(total_fit, 4),
            selected_average_fit_score=round(total_fit / selected_count, 4) if selected_count else 0,
            selected_candidates=selected_candidates,
            warnings=warnings,
        )
