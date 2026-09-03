from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import RecommendationRun


class RecommendationRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        campaign_id: str,
        run_type: str,
        query_text: str | None = None,
        keyword_weight_config: dict[str, float] | None = None,
        retrieval_config: dict | None = None,
        fit_config: dict | None = None,
        budget_config: dict | None = None,
    ) -> RecommendationRun:
        now = datetime.now(UTC)
        run = RecommendationRun(
            run_id=f"run_{uuid4().hex}",
            campaign_id=campaign_id,
            run_type=run_type,
            started_at=now,
            evaluated_at=now,
            data_cutoff_at=now,
            completed_at=None,
            status="running",
            filter_policy_version="hard_filter_v2_run_time",
            risk_policy_version="risk_gate_v1",
            keyword_weight_config=keyword_weight_config or {},
            retrieval_config=retrieval_config or {},
            fit_config=fit_config or {},
            budget_config=budget_config or {},
            query_text=query_text,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def complete(self, run: RecommendationRun) -> None:
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        self.session.commit()

    def fail(self, run_id: str) -> None:
        self.session.rollback()
        run = self.session.get(RecommendationRun, run_id)
        if run is not None:
            run.status = "failed"
            run.completed_at = datetime.now(UTC)
            self.session.commit()
