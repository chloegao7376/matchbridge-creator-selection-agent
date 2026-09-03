from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

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

DATE_FIELDS = {
    "creators": ["created_at"],
    "accounts": ["collected_at"],
    "audience_snapshots": ["snapshot_date"],
    "account_metric_snapshots": ["snapshot_date"],
    "content_items": ["published_at", "metric_collected_at"],
    "rate_cards": ["valid_from", "valid_to"],
    "collaborations": ["started_at", "ended_at", "exclusive_until"],
    "risk_events": ["observed_at", "expires_at"],
    "campaign_briefs": ["campaign_start_at", "campaign_end_at", "created_at"],
}


TABLES: list[tuple[str, Path, type, tuple[str, ...]]] = [
    ("creators", Path("creators.jsonl"), Creator, ("creator_id",)),
    ("accounts", Path("accounts.jsonl"), CreatorAccount, ("account_id",)),
    ("audience_snapshots", Path("audience_snapshots.jsonl"), AudienceSnapshot, ("account_id", "snapshot_date")),
    ("account_metric_snapshots", Path("account_metric_snapshots.jsonl"), AccountMetricSnapshot, ("account_id", "snapshot_date")),
    ("content_items", Path("content_items.jsonl"), ContentItem, ("content_id",)),
    ("rate_cards", Path("rate_cards.jsonl"), RateCard, ("rate_card_id",)),
    ("collaborations", Path("collaborations.jsonl"), Collaboration, ("collaboration_id",)),
    ("risk_events", Path("risk_events.jsonl"), RiskEvent, ("risk_event_id",)),
    ("campaign_briefs", Path("campaign_briefs.jsonl"), CampaignBrief, ("campaign_id",)),
]


def parse_dates(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
    for field in DATE_FIELDS.get(table_name, []):
        if row.get(field):
            row[field] = date.fromisoformat(row[field])
    return row


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc


def chunks(rows: Iterator[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def upsert_batch(session: Session, model: type, rows: list[dict[str, Any]], primary_keys: tuple[str, ...]) -> None:
    statement = insert(model).values(rows)
    update_values = {column.name: getattr(statement.excluded, column.name) for column in model.__table__.columns if column.name not in primary_keys}
    statement = statement.on_conflict_do_update(index_elements=list(primary_keys), set_=update_values)
    session.execute(statement)


def import_jsonl_table(session: Session, data_dir: Path, table_name: str, relative_path: Path, model: type, primary_keys: tuple[str, ...], batch_size: int) -> int:
    source = data_dir / relative_path
    if not source.exists():
        raise FileNotFoundError(source)
    count = 0
    parsed = (parse_dates(table_name, row) for row in read_jsonl(source))
    for batch in chunks(parsed, batch_size):
        upsert_batch(session, model, batch, primary_keys)
        count += len(batch)
    session.commit()
    return count


def import_policy_rules(session: Session, data_dir: Path) -> int:
    rows = json.loads((data_dir / "policy_rules.json").read_text(encoding="utf-8"))
    upsert_batch(session, PolicyRule, rows, ("rule_id", "version"))
    session.commit()
    return len(rows)


def run_import(data_dir: Path, batch_size: int) -> None:
    with SessionLocal() as session:
        for table_name, path, model, primary_keys in TABLES:
            count = import_jsonl_table(session, data_dir, table_name, path, model, primary_keys, batch_size)
            print(f"{table_name}: upserted {count} rows")
        count = import_policy_rules(session, data_dir)
        print(f"policy_rules: upserted {count} rows")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import production JSONL files into PostgreSQL")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--batch-size", type=int, default=500)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_import(args.data_dir.resolve(), args.batch_size)
