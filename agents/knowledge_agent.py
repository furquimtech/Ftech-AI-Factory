"""
Knowledge Agent
───────────────
Continuous learning loop:
  • Reads generated documentation / code artifacts
  • Generates embeddings via the LLM provider
  • Stores vectors in PostgreSQL (pgvector)
  • Exposes a search helper used by other agents to enrich prompts
"""
from __future__ import annotations

from agents.base_agent import BaseAgent
from config.settings import LLM_KNOWLEDGE
from database.vector_store import VectorStore
from llm import get_provider


class KnowledgeAgent(BaseAgent):
    name = "knowledge"

    def __init__(self) -> None:
        super().__init__()
        self.llm = get_provider(LLM_KNOWLEDGE)
        self.vector_store = VectorStore()

    # ── public helper (called by other agents) ────────────────────────────────

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Return the top-k most relevant knowledge chunks for a query."""
        query_embedding = self.llm.embed(query)
        return await self.vector_store.similarity_search(query_embedding, top_k=top_k)

    # ── agent execute ─────────────────────────────────────────────────────────

    def execute(self, task: dict) -> dict:
        """
        Ingest a document (markdown, code, etc.) into the knowledge base.
        task must contain:
          - content: str  (the text to ingest)
          - source: str   (file path or URL, used as metadata)
        """
        content: str = task.get("content", "")
        source: str = task.get("source", "unknown")

        if not content:
            raise ValueError("KnowledgeAgent requires 'content' in task payload")

        self.logger.info(f"Ingesting knowledge from source='{source}' ({len(content)} chars)")

        # Chunk the content (simple fixed-size with overlap)
        chunks = self._chunk(content, size=800, overlap=100)
        ids = []

        for i, chunk in enumerate(chunks):
            embedding = self.llm.embed(chunk)
            doc_id = self.vector_store.upsert_sync(
                content=chunk,
                embedding=embedding,
                metadata={"source": source, "chunk_index": i},
            )
            ids.append(doc_id)

        self.logger.info(f"Ingested {len(ids)} chunks from '{source}'")
        return {"source": source, "chunks_stored": len(ids), "doc_ids": ids}

    # ── private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _chunk(text: str, size: int = 800, overlap: int = 100) -> list[str]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            chunks.append(text[start:end])
            start += size - overlap
        return chunks
