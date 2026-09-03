import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from app.services.historical_data_availability import HistoricalDataAvailabilityChecker


def test_history_availability_ground_truth_covers_all_three_tiers():
    fixture_path = (
        Path(__file__).parents[1]
        / "data"
        / "evaluation"
        / "history_availability_ground_truth.jsonl"
    )
    scenarios = [json.loads(line) for line in fixture_path.read_text().splitlines() if line]
    checker = HistoricalDataAvailabilityChecker()
    observed_tiers = set()

    for scenario in scenarios:
        collaborations = [
            SimpleNamespace(
                **{
                    **row,
                    "ended_at": date.fromisoformat(row["ended_at"]),
                }
            )
            for row in scenario["collaborations"]
        ]
        result = checker.evaluate(
            collaborations,
            campaign_category=scenario["campaign_category"],
            compatible_formats=scenario["compatible_formats"],
            primary_kpi=scenario["primary_kpi"],
            evaluated_at=date.fromisoformat(scenario["evaluated_at"]),
        )
        observed_tiers.add(result.tier)
        assert result.tier == scenario["expected_tier"]
        assert result.effective_history_n == scenario["expected_effective_history_n"]

    assert observed_tiers == {"HISTORY_SUFFICIENT", "HISTORY_LIMITED", "COLD_START"}
