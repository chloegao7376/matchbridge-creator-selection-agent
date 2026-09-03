from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CampaignBrief
from app.schemas.brief import CampaignBriefCreate, CampaignBriefPayload, CampaignBriefUpdate


class BriefRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, payload: CampaignBriefCreate) -> CampaignBrief:
        brief = CampaignBrief(
            campaign_id=f"cmp_{uuid4().hex[:12]}",
            created_at=datetime.now(UTC).date(),
            **payload.model_dump(),
        )
        self.session.add(brief)
        self.session.commit()
        self.session.refresh(brief)
        return brief

    def get(self, campaign_id: str) -> CampaignBrief | None:
        return self.session.get(CampaignBrief, campaign_id)

    def list(self, offset: int = 0, limit: int = 50) -> Sequence[CampaignBrief]:
        statement = select(CampaignBrief).order_by(CampaignBrief.created_at.desc(), CampaignBrief.campaign_id).offset(offset).limit(limit)
        return self.session.scalars(statement).all()

    def update(self, brief: CampaignBrief, payload: CampaignBriefUpdate) -> CampaignBrief:
        current = {
            column.name: getattr(brief, column.name)
            for column in CampaignBrief.__table__.columns
            if column.name not in {"campaign_id", "created_at"}
        }
        merged = {**current, **payload.model_dump(exclude_unset=True, exclude_none=True)}
        validated = CampaignBriefPayload.model_validate(merged)
        for field, value in validated.model_dump().items():
            setattr(brief, field, value)
        self.session.commit()
        self.session.refresh(brief)
        return brief

    def delete(self, brief: CampaignBrief) -> None:
        self.session.delete(brief)
        self.session.commit()
