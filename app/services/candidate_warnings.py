from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Protocol

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import RiskEvent
from app.schemas.retrieval import RiskWarning


class CandidateWithRiskWarnings(Protocol):
    account_id: str
    risk_warnings: list[RiskWarning]


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def attach_active_risk_warnings(
    session: Session,
    candidates: list[CandidateWithRiskWarnings],
    *,
    evaluated_at: datetime,
) -> None:
    account_ids = [candidate.account_id for candidate in candidates]
    if not account_ids:
        return
    evaluation_date = evaluated_at.date()
    statement = select(RiskEvent).where(
        RiskEvent.account_id.in_(account_ids),
        RiskEvent.observed_at <= evaluation_date,
        or_(RiskEvent.expires_at.is_(None), RiskEvent.expires_at >= evaluation_date),
        RiskEvent.decision == "REVIEW",
        or_(RiskEvent.is_false_positive.is_(None), RiskEvent.is_false_positive.is_(False)),
    )
    events_by_account: dict[str, list[RiskEvent]] = defaultdict(list)
    for event in session.scalars(statement):
        events_by_account[event.account_id].append(event)

    for candidate in candidates:
        events = sorted(
            events_by_account[candidate.account_id],
            key=lambda event: (
                SEVERITY_ORDER.get(event.severity, 99),
                -event.observed_at.toordinal(),
                event.risk_event_id,
            ),
        )
        candidate.risk_warnings = [
            RiskWarning(
                code="active_review_risk",
                message=(
                    f"存在待复核的{event.severity}级风险线索：{event.evidence_text}；"
                    "该线索不构成违规或事实认定。"
                ),
                risk_event_id=event.risk_event_id,
                risk_type=event.risk_type,
                risk_subtype=event.risk_subtype,
                severity=event.severity,
                confidence=float(event.confidence),
                decision=event.decision,
                review_status=event.review_status,
                observed_at=event.observed_at,
                expires_at=event.expires_at,
            )
            for event in events
        ]
