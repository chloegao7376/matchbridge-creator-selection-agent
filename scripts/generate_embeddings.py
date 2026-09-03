from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import SessionLocal
from app.embedding import get_embedding_provider
from app.models import CreatorAccount, CreatorSearchDocument


def document_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunks(rows: list[tuple[CreatorAccount, CreatorSearchDocument]], size: int):
    for index in range(0, len(rows), size):
        yield rows[index : index + size]


def generate_embeddings(*, batch_size: int = 64, force: bool = False) -> tuple[int, int]:
    provider = get_embedding_provider()
    if provider.dimension != 1536:
        raise ValueError("current database schema requires 1536-dimensional embeddings")

    generated = 0
    skipped = 0
    with SessionLocal() as session:
        rows = session.execute(
            select(CreatorAccount, CreatorSearchDocument)
            .join(CreatorSearchDocument, CreatorSearchDocument.account_id == CreatorAccount.account_id)
            .order_by(CreatorAccount.account_id)
        ).all()
        pending = []
        for account, document in rows:
            fingerprint = document_hash(document.search_text)
            if (
                not force
                and account.profile_embedding is not None
                and account.embedding_model == provider.model_name
                and account.embedding_document_hash == fingerprint
            ):
                skipped += 1
                continue
            pending.append((account, document))

        for batch in chunks(pending, batch_size):
            vectors = provider.embed_documents([document.search_text for _, document in batch])
            generated_at = datetime.now(UTC)
            for (account, document), vector in zip(batch, vectors, strict=True):
                account.profile_embedding = vector
                account.embedding_model = provider.model_name
                account.embedding_document_hash = document_hash(document.search_text)
                account.embedding_generated_at = generated_at
            session.commit()
            generated += len(batch)
            print(f"embedded {generated}/{len(pending)}")
    return generated, skipped


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate versioned embeddings for creator search documents")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    generated, skipped = generate_embeddings(batch_size=args.batch_size, force=args.force)
    print(f"complete: generated={generated}, skipped={skipped}")
