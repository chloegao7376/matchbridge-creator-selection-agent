from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import RecommendationRun
from app.repositories.briefs import BriefRepository
from app.repositories.selection_reviews import SelectionReviewRepository
from app.schemas.selection_review import (
    ReviewActionRequest,
    SelectionReviewCreate,
    SelectionReviewItemUpdate,
    SelectionReviewRead,
)
from app.services.budget_optimizer import BudgetOptimizer
from app.services.feature_calculator import resolve_primary_kpi

router = APIRouter(prefix="/api/selection-reviews", tags=["human-selection-review"])
DbSession = Annotated[Session, Depends(get_db)]


def _review_or_404(repository: SelectionReviewRepository, review_id: str):
    review = repository.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="selection review not found")
    return review


@router.post("", response_model=SelectionReviewRead, status_code=201)
def create_selection_review(payload: SelectionReviewCreate, db: DbSession):
    run = db.get(RecommendationRun, payload.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="recommendation run not found")
    if run.status != "completed" or not run.budget_config:
        raise HTTPException(status_code=409, detail="recommendation run is not ready for review")
    repository = SelectionReviewRepository(db)
    review = repository.create(run, payload.reviewer_name)
    return repository.to_schema(review)


@router.get("/{review_id}", response_model=SelectionReviewRead)
def get_selection_review(review_id: str, db: DbSession):
    repository = SelectionReviewRepository(db)
    return repository.to_schema(_review_or_404(repository, review_id))


@router.patch("/{review_id}/items/{account_id}", response_model=SelectionReviewRead)
def update_selection_review_item(
    review_id: str,
    account_id: str,
    payload: SelectionReviewItemUpdate,
    db: DbSession,
):
    repository = SelectionReviewRepository(db)
    review = _review_or_404(repository, review_id)
    item = repository.get_item(review_id, account_id)
    if item is None:
        raise HTTPException(status_code=404, detail="creator is not part of this recommendation run")
    try:
        repository.mutate_item(
            review,
            item,
            action=payload.action,
            actor_name=payload.actor_name,
            locked=payload.locked,
            reason=payload.reason,
            risk_resolution=payload.risk_resolution,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return repository.to_schema(review)


@router.post("/{review_id}/recalculate", response_model=SelectionReviewRead)
def recalculate_selection_review(
    review_id: str,
    payload: ReviewActionRequest,
    db: DbSession,
):
    repository = SelectionReviewRepository(db)
    review = _review_or_404(repository, review_id)
    if review.status == "CONFIRMED":
        raise HTTPException(status_code=409, detail="confirmed selection reviews cannot be changed")
    brief = BriefRepository(db).get(review.campaign_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="campaign brief not found")
    items = repository.list_items(review.review_id)
    required_ids = {
        item.account_id
        for item in items
        if item.disposition == "INCLUDED" and item.locked
    }
    excluded_ids = {
        item.account_id
        for item in items
        if item.disposition == "EXCLUDED" or item.risk_resolution == "REJECTED"
    }
    cleared_review_ids = {
        item.account_id for item in items if item.risk_resolution == "CLEARED"
    }
    try:
        result = BudgetOptimizer().optimize(
            repository.load_ranked_candidates(review.run_id),
            total_budget_cny=brief.total_budget_cny,
            target_creator_count=brief.creator_count,
            primary_kpi=resolve_primary_kpi(brief),
            required_account_ids=required_ids,
            excluded_account_ids=excluded_ids,
            allowed_review_account_ids=cleared_review_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    repository.apply_optimization(
        review,
        {candidate.account_id for candidate in result.selected_candidates},
        result.model_dump(mode="json"),
        payload.actor_name,
    )
    return repository.to_schema(review)


@router.post("/{review_id}/confirm", response_model=SelectionReviewRead)
def confirm_selection_review(
    review_id: str,
    payload: ReviewActionRequest,
    db: DbSession,
):
    repository = SelectionReviewRepository(db)
    review = _review_or_404(repository, review_id)
    try:
        repository.confirm(review, payload.actor_name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return repository.to_schema(review)
