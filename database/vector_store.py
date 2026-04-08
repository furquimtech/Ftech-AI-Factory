"""
pgvector helper – upsert and similarity search for the Knowledge Agent.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import KnowledgeDocument
from database.session import AsyncSessionLocal


class VectorStore:
    """Thin wrapper around KnowledgeDocument for RAG operations."""

    # ── async API (used by KnowledgeAgent.search) ─────────────────────────────

    async def similarity_search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[dict]:
        async with AsyncSessionLocal() as session:
            # pgvector cosine distance operator: <=>
            stmt = (
                select(
                    KnowledgeDocument.id,
                    KnowledgeDocument.source,
                    KnowledgeDocument.content,
                    KnowledgeDocument.embedding.cosine_distance(query_embedding).label("distance"),
                )
                .order_by(text("distance"))
                .limit(top_k)
            )
            result = await session.execute(stmt)
            rows = result.all()

        return [
            {
                "id": str(r.id),
                "source": r.source,
                "content": r.content,
                "score": 1 - r.distance,  # cosine similarity
            }
            for r in rows
        ]

    # ── sync API (used inside agent execute, which is sync) ───────────────────

    def upsert_sync(
        self,
        content: str,
        embedding: list[float],
        metadata: dict | None = None,
    ) -> str:
        """
        Synchronous upsert – runs a new event loop iteration via asyncio.run().
        Safe to call from a non-async context (agent.execute).
        """
        import asyncio

        return asyncio.run(self._upsert(content, embedding, metadata))

    async def _upsert(
        self,
        content: str,
        embedding: list[float],
        metadata: dict | None = None,
    ) -> str:
        async with AsyncSessionLocal() as session:
            doc = KnowledgeDocument(
                id=uuid.uuid4(),
                source=metadata.get("source", "unknown") if metadata else "unknown",
                chunk_index=metadata.get("chunk_index", 0) if metadata else 0,
                content=content,
                embedding=embedding,
                metadata_=metadata or {},
            )
            session.add(doc)
            await session.commit()
            return str(doc.id)
