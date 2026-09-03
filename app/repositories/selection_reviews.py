from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CandidateFeatureSnapshot,
    CandidateScoreSnapshot,
    RecommendationRun,
    SelectionReview,
    SelectionReviewEvent,
    SelectionReviewItem,
)
from app.schemas.features import CandidateFeatureRead
from app.schemas.ranking import RankedCandidate
from app.schemas.selection_review import SelectionReviewItemRead, SelectionReviewRead


class SelectionReviewRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, review_id: str) -> SelectionReview | None:
        return self.session.get(SelectionReview, review_id)

    def get_by_run(self, run_id: str) -> SelectionReview | None:
        return self.session.scalar(select(SelectionReview).where(SelectionReview.run_id == run_id))

    def create(self, run: RecommendationRun, reviewer_name: str) -> SelectionReview:
        existing = self.get_by_run(run.run_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        review = SelectionReview(
            review_id=f"review_{uuid4().hex}",
            run_id=run.run_id,
            campaign_id=run.campaign_id,
            status="DRAFT",
            reviewer_name=reviewer_name,
            version=1,
            optimization_summary=run.budget_config,
            created_at=now,
            updated_at=now,
            confirmed_at=None,
        )
        selected_ids = {
            item["account_id"] for item in run.budget_config.get("selected_candidates", [])
        }
        scores = self.session.scalars(
            select(CandidateScoreSnapshot)
            .where(CandidateScoreSnapshot.run_id == run.run_id)
            .order_by(CandidateScoreSnapshot.recommendation_rank)
        ).all()
        self.session.add(review)
        for score in scores:
            risk_decision = score.risk_decision
            self.session.add(
                SelectionReviewItem(
                    item_id=f"item_{uuid4().hex}",
                    review_id=review.review_id,
                    account_id=score.account_id,
                    disposition="INCLUDED" if score.account_id in selected_ids else "AVAILABLE",
                    source="SYSTEM",
                    locked=False,
                    reason=None,
                    risk_resolution="PENDING" if risk_decision == "REVIEW" else "NOT_REQUIRED",
                    updated_at=now,
                )
            )
        self._add_event(review, "REVIEW_CREATED", reviewer_name, payload={"run_id": run.run_id})
        self.session.commit()
        self.session.refresh(review)
        return review

    def list_items(self, review_id: str) -> list[SelectionReviewItem]:
        return list(
            self.session.scalars(
                select(SelectionReviewItem)
                .where(SelectionReviewItem.review_id == review_id)
                .order_by(SelectionReviewItem.account_id)
            ).all()
        )

    def get_item(self, review_id: str, account_id: str) -> SelectionReviewItem | None:
        return self.session.scalar(
            select(SelectionReviewItem).where(
                SelectionReviewItem.review_id == review_id,
                SelectionReviewItem.account_id == account_id,
            )
        )

    def mutate_item(
        self,
        review: SelectionReview,
        item: SelectionReviewItem,
        *,
        action: str,
        actor_name: str,
        locked: bool | None = None,
        reason: str | None = None,
        risk_resolution: str | None = None,
    ) -> None:
        if review.status == "CONFIRMED":
            raise ValueError("confirmed selection reviews cannot be changed")
        before = {
            "disposition": item.disposition,
            "locked": item.locked,
            "reason": item.reason,
            "risk_resolution": item.risk_resolution,
        }
        if action == "include":
            if item.risk_resolution == "REJECTED":
                raise ValueError("a creator with rejected risk review cannot be included")
            item.disposition = "INCLUDED"
            item.source = "HUMAN"
            item.locked = True if locked is None else locked
            item.reason = reason
        elif action == "exclude":
            item.disposition = "EXCLUDED"
            item.source = "HUMAN"
            item.locked = False
            item.reason = reason.strip() if reason else None
        elif action == "restore":
            item.disposition = "AVAILABLE"
            item.source = "HUMAN"
            item.locked = False
            item.reason = None
        elif action == "set_lock":
            if item.disposition != "INCLUDED":
                raise ValueError("only included creators can be locked")
            item.locked = bool(locked)
            item.source = "HUMAN"
        elif action == "resolve_risk":
            item.risk_resolution = str(risk_resolution)
            item.source = "HUMAN"
            item.reason = reason
            if risk_resolution == "REJECTED":
                item.disposition = "EXCLUDED"
                item.locked = False
        else:
            raise ValueError(f"unsupported review action: {action}")
        now = datetime.now(UTC)
        item.updated_at = now
        review.updated_at = now
        review.version += 1
        self._add_event(
            review,
            "ITEM_UPDATED",
            actor_name,
            account_id=item.account_id,
            payload={
                "action": action,
                "before": before,
                "after": {
                    "disposition": item.disposition,
                    "locked": item.locked,
                    "reason": item.reason,
                    "risk_resolution": item.risk_resolution,
                },
            },
        )
        self.session.commit()

    def load_ranked_candidates(self, run_id: str) -> list[RankedCandidate]:
        rows = self.session.execute(
            select(CandidateScoreSnapshot, CandidateFeatureSnapshot)
            .join(
                CandidateFeatureSnapshot,
                CandidateFeatureSnapshot.feature_snapshot_id
                == CandidateScoreSnapshot.feature_snapshot_id,
            )
            .where(CandidateScoreSnapshot.run_id == run_id)
            .order_by(CandidateScoreSnapshot.recommendation_rank)
        ).all()
        return [
            RankedCandidate.model_validate(
                {
                    **score.scoring_detail,
                    "features": CandidateFeatureRead.model_validate(feature.features),
                }
            )
            for score, feature in rows
        ]

    def apply_optimization(
        self,
        review: SelectionReview,
        selected_account_ids: set[str],
        summary: dict,
        actor_name: str,
    ) -> None:
        now = datetime.now(UTC)
        for item in self.list_items(review.review_id):
            if item.disposition == "EXCLUDED":
                continue
            if item.account_id in selected_account_ids:
                item.disposition = "INCLUDED"
                if item.source != "HUMAN":
                    item.source = "OPTIMIZER"
            elif not item.locked:
                item.disposition = "AVAILABLE"
                if item.source != "HUMAN":
                    item.source = "OPTIMIZER"
            item.updated_at = now
        review.optimization_summary = summary
        review.updated_at = now
        review.version += 1
        self._add_event(
            review,
            "COMBINATION_RECALCULATED",
            actor_name,
            payload={"selected_account_ids": sorted(selected_account_ids)},
        )
        self.session.commit()

    def confirm(self, review: SelectionReview, actor_name: str) -> None:
        if review.status == "CONFIRMED":
            return
        included = [item for item in self.list_items(review.review_id) if item.disposition == "INCLUDED"]
        if not included:
            raise ValueError("at least one creator must be included before confirmation")
        unresolved = [
            item.account_id
            for item in included
            if item.risk_resolution in {"PENDING", "REJECTED"}
        ]
        if unresolved:
            raise ValueError("included creators have unresolved risk reviews: " + ", ".join(unresolved))
        now = datetime.now(UTC)
        review.status = "CONFIRMED"
        review.confirmed_at = now
        review.updated_at = now
        review.version += 1
        self._add_event(
            review,
            "FINAL_SELECTION_CONFIRMED",
            actor_name,
            payload={"selected_account_ids": [item.account_id for item in included]},
        )
        self.session.commit()

    def to_schema(self, review: SelectionReview) -> SelectionReviewRead:
        scores = self.session.scalars(
            select(CandidateScoreSnapshot).where(CandidateScoreSnapshot.run_id == review.run_id)
        ).all()
        score_by_account = {score.account_id: score for score in scores}
        items = []
        for item in self.list_items(review.review_id):
            score = score_by_account[item.account_id]
            detail = score.scoring_detail
            items.append(
                SelectionReviewItemRead(
                    account_id=item.account_id,
                    handle=detail["handle"],
                    platform=detail["platform"],
                    final_rank=score.recommendation_rank,
                    fit_score=float(score.fit_score),
                    risk_decision=score.risk_decision,
                    disposition=item.disposition,
                    source=item.source,
                    locked=item.locked,
                    reason=item.reason,
                    risk_resolution=item.risk_resolution,
                    updated_at=item.updated_at,
                )
            )
        items.sort(key=lambda item: item.final_rank)
        return SelectionReviewRead(
            review_id=review.review_id,
            run_id=review.run_id,
            campaign_id=review.campaign_id,
            status=review.status,
            reviewer_name=review.reviewer_name,
            version=review.version,
            optimization_summary=review.optimization_summary,
            created_at=review.created_at,
            updated_at=review.updated_at,
            confirmed_at=review.confirmed_at,
            items=items,
        )

    def _add_event(
        self,
        review: SelectionReview,
        event_type: str,
        actor_name: str,
        *,
        account_id: str | None = None,
        payload: dict | None = None,
    ) -> None:
        self.session.add(
            SelectionReviewEvent(
                event_id=f"event_{uuid4().hex}",
                review_id=review.review_id,
                event_type=event_type,
                actor_name=actor_name,
                account_id=account_id,
                payload=payload or {},
                created_at=datetime.now(UTC),
            )
        )
