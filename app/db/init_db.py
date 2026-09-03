from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine
from app.models import entities  # noqa: F401


def init_db() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE creator_accounts ADD COLUMN IF NOT EXISTS embedding_document_hash VARCHAR(64)")
        )
        connection.execute(
            text("ALTER TABLE creator_accounts ADD COLUMN IF NOT EXISTS embedding_generated_at TIMESTAMPTZ")
        )
        connection.execute(
            text(
                "ALTER TABLE recommendation_runs ADD COLUMN IF NOT EXISTS "
                "retrieval_config JSONB NOT NULL DEFAULT '{}'::jsonb"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE recommendation_runs ADD COLUMN IF NOT EXISTS "
                "fit_config JSONB NOT NULL DEFAULT '{}'::jsonb"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE recommendation_runs ADD COLUMN IF NOT EXISTS "
                "budget_config JSONB NOT NULL DEFAULT '{}'::jsonb"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_creator_accounts_embedding_hnsw "
                "ON creator_accounts USING hnsw (profile_embedding vector_cosine_ops) "
                "WHERE profile_embedding IS NOT NULL"
            )
        )
    print("Database extension and tables are ready.")


if __name__ == "__main__":
    init_db()
