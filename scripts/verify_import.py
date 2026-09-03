from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import (
    AccountMetricSnapshot,
    AudienceSnapshot,
    CampaignBrief,
    Collaboration,
    ContentItem,
    Creator,
    CreatorAccount,
    PolicyRule,
    RateCard,
    RiskEvent,
)

MODELS = {
    "creators": Creator,
    "accounts": CreatorAccount,
    "audience_snapshots": AudienceSnapshot,
    "account_metric_snapshots": AccountMetricSnapshot,
    "content_items": ContentItem,
    "rate_cards": RateCard,
    "collaborations": Collaboration,
    "risk_events": RiskEvent,
    "campaign_briefs": CampaignBrief,
    "policy_rules": PolicyRule,
}


def verify(data_dir: Path) -> bool:
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    expected = manifest["row_counts"]
    ok = True
    with SessionLocal() as session:
        for name, model in MODELS.items():
            actual = session.scalar(select(func.count()).select_from(model)) or 0
            target = expected[name]
            matches = actual == target
            ok &= matches
            print(f"{'OK' if matches else 'MISMATCH':8} {name:28} database={actual:6} expected={target:6}")
    return ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare PostgreSQL row counts with data/manifest.json")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    raise SystemExit(0 if verify(args.data_dir.resolve()) else 1)
