from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.session import SessionLocal
from app.models import AudienceSnapshot, ContentItem, Creator, CreatorAccount, CreatorSearchDocument


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def build_search_text(
    creator: Creator,
    account: CreatorAccount,
    topic_tags: list[str],
    audience_interests: list[str],
    representative_contents: list[ContentItem],
) -> str:
    content_lines = [f"{item.title}；{item.caption}" for item in representative_contents]
    sections = [
        f"达人：{creator.display_name}",
        f"平台：{account.platform}",
        f"主营类目：{'、'.join(account.category_tags)}",
        f"内容风格：{'、'.join(account.style_tags)}",
        f"近期主题：{'、'.join(topic_tags)}",
        f"受众兴趣：{'、'.join(audience_interests)}",
        f"达人简介：{creator.public_persona_summary}",
        f"代表内容：{'；'.join(content_lines)}",
    ]
    return "\n".join(sections)


def build_documents() -> int:
    with SessionLocal() as session:
        creator_by_id = {row.creator_id: row for row in session.scalars(select(Creator)).all()}
        accounts = session.scalars(select(CreatorAccount).order_by(CreatorAccount.account_id)).all()

        latest_audience: dict[str, AudienceSnapshot] = {}
        audience_rows = session.scalars(
            select(AudienceSnapshot).order_by(AudienceSnapshot.account_id, AudienceSnapshot.snapshot_date.desc())
        ).all()
        for row in audience_rows:
            latest_audience.setdefault(row.account_id, row)

        contents_by_account: dict[str, list[ContentItem]] = defaultdict(list)
        for content in session.scalars(select(ContentItem)).all():
            contents_by_account[content.account_id].append(content)

        rows = []
        for account in accounts:
            creator = creator_by_id[account.creator_id]
            cutoff = account.collected_at - timedelta(days=90)
            recent = [content for content in contents_by_account[account.account_id] if content.published_at >= cutoff]
            topic_counts = Counter(tag for content in recent for tag in content.topic_tags if tag not in account.category_tags)
            topic_tags = [tag for tag, _ in topic_counts.most_common(10)]
            representative = sorted(
                recent,
                key=lambda content: int(content.metrics.get("views", 0)),
                reverse=True,
            )[:5]
            audience_interests = (
                latest_audience[account.account_id].audience_interest_tags
                if account.account_id in latest_audience
                else []
            )
            rows.append(
                {
                    "account_id": account.account_id,
                    "search_text": build_search_text(
                        creator,
                        account,
                        topic_tags,
                        audience_interests,
                        representative,
                    ),
                    "category_tags": unique(account.category_tags),
                    "style_tags": unique(account.style_tags),
                    "topic_tags": unique(topic_tags),
                    "audience_interest_tags": unique(audience_interests),
                    "representative_content_ids": [content.content_id for content in representative],
                    "content_count": len(recent),
                    "generated_at": account.collected_at,
                }
            )

        if rows:
            statement = insert(CreatorSearchDocument).values(rows)
            statement = statement.on_conflict_do_update(
                index_elements=["account_id"],
                set_={
                    column.name: getattr(statement.excluded, column.name)
                    for column in CreatorSearchDocument.__table__.columns
                    if column.name != "account_id"
                },
            )
            session.execute(statement)
            session.commit()
        return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build one keyword/embedding source document per creator account")
    parser.parse_args()
    count = build_documents()
    print(f"creator_search_documents: upserted {count} rows")

