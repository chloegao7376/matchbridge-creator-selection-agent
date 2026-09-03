from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.briefs import BriefRepository
from app.repositories.recommendation_runs import RecommendationRunRepository
from app.schemas.brief import CampaignBriefCreate, CampaignBriefRead, CampaignBriefUpdate
from app.schemas.eligibility import EligibilityResponse
from app.services.eligibility_filter import EligibilityFilter

router = APIRouter(prefix="/api/briefs", tags=["campaign-briefs"])
DbSession = Annotated[Session, Depends(get_db)]


def get_or_404(repository: BriefRepository, campaign_id: str):
    brief = repository.get(campaign_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="campaign brief not found")
    return brief


@router.post("", response_model=CampaignBriefRead, status_code=status.HTTP_201_CREATED)
def create_brief(payload: CampaignBriefCreate, db: DbSession):
    return BriefRepository(db).create(payload)


@router.get("", response_model=list[CampaignBriefRead])
def list_briefs(
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    return BriefRepository(db).list(offset=offset, limit=limit)


@router.get("/{campaign_id}", response_model=CampaignBriefRead)
def get_brief(campaign_id: str, db: DbSession):
    repository = BriefRepository(db)
    return get_or_404(repository, campaign_id)


@router.patch("/{campaign_id}", response_model=CampaignBriefRead)
def update_brief(campaign_id: str, payload: CampaignBriefUpdate, db: DbSession):
    repository = BriefRepository(db)
    brief = get_or_404(repository, campaign_id)
    try:
        return repository.update(brief, payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors(include_url=False))) from exc


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brief(campaign_id: str, db: DbSession) -> Response:
    repository = BriefRepository(db)
    brief = get_or_404(repository, campaign_id)
    repository.delete(brief)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{campaign_id}/eligibility", response_model=EligibilityResponse)
def evaluate_eligibility(
    campaign_id: str,
    db: DbSession,
    include_excluded: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    repository = BriefRepository(db)
    brief = get_or_404(repository, campaign_id)
    run_repository = RecommendationRunRepository(db)
    run = run_repository.create(campaign_id=campaign_id, run_type="eligibility")
    try:
        result = EligibilityFilter(db).evaluate(
            brief,
            include_excluded=include_excluded,
            limit=limit,
            evaluated_at=run.evaluated_at,
            recommendation_run_id=run.run_id,
        )
    except Exception:
        run_repository.fail(run.run_id)
        raise
    run_repository.complete(run)
    return result
