from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.services.candidate_warnings import attach_active_risk_warnings


class FakeSession:
    def __init__(self, events):
        self.events = events

    def scalars(self, _statement):
        return self.events


def risk_event(event_id: str, account_id: str, severity: str, observed_at: date):
    return SimpleNamespace(
        risk_event_id=event_id,
        account_id=account_id,
        risk_type="content_compliance",
        risk_subtype="claim_requires_review",
        severity=severity,
        confidence=Decimal("0.82"),
        decision="REVIEW",
        review_status="pending",
        observed_at=observed_at,
        expires_at=date(2026, 9, 30),
        evidence_text="检测到待复核表述",
    )


def test_active_risk_warnings_are_attached_per_candidate_and_sorted_by_severity():
    candidates = [SimpleNamespace(account_id="a1", risk_warnings=[]), SimpleNamespace(account_id="a2", risk_warnings=[])]
    session = FakeSession(
        [
            risk_event("medium", "a1", "medium", date(2026, 8, 30)),
            risk_event("high", "a1", "high", date(2026, 8, 29)),
        ]
    )

    attach_active_risk_warnings(
        session,
        candidates,
        evaluated_at=datetime(2026, 9, 1, tzinfo=UTC),
    )

    assert [warning.risk_event_id for warning in candidates[0].risk_warnings] == ["high", "medium"]
    assert candidates[0].risk_warnings[0].decision == "REVIEW"
    assert "不构成违规或事实认定" in candidates[0].risk_warnings[0].message
    assert candidates[1].risk_warnings == []
