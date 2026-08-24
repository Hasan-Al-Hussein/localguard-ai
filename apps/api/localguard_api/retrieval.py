"""Revision-aware exact-vector/full-text retrieval with deterministic RRF."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings
from .models import Chunk, Document, DocumentRevision, DocumentState, SourceAnchor
from .providers import EmbeddingProvider


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk: Chunk
    score: float
    vector_rank: int | None
    text_rank: int | None
    vector_similarity: float | None
    text_score: float | None


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    chunks: tuple[RetrievedChunk, ...]
    elapsed_ms: float
    sufficient: bool


@dataclass(slots=True)
class _FusedCandidate:
    chunk: Chunk
    score: float = 0.0
    vector_rank: int | None = None
    text_rank: int | None = None
    vector_similarity: float | None = None
    text_score: float | None = None


class HybridRetriever:
    def __init__(self, settings: Settings, embeddings: EmbeddingProvider) -> None:
        self.settings = settings
        self.embeddings = embeddings

    async def search(
        self,
        db: AsyncSession,
        question: str,
        document_ids: list[uuid.UUID],
    ) -> RetrievalResult:
        started = time.perf_counter()
        query_vector = (await self.embeddings.embed([question]))[0]
        candidates = self.settings.retrieval_candidate_limit
        predicate = [
            Document.deleted_at.is_(None),
            Document.state == DocumentState.READY,
            DocumentRevision.id == Document.current_revision_id,
            Chunk.embedding.is_not(None),
        ]
        if document_ids:
            predicate.append(Document.id.in_(document_ids))

        distance = Chunk.embedding.cosine_distance(query_vector)
        vector_rows = (
            await db.execute(
                select(Chunk, distance.label("distance"))
                .join(DocumentRevision, DocumentRevision.id == Chunk.revision_id)
                .join(Document, Document.id == DocumentRevision.document_id)
                .where(*predicate)
                .order_by(distance.asc(), Chunk.stable_id.asc())
                .limit(candidates)
            )
        ).all()

        document_predicate = [
            Document.deleted_at.is_(None),
            Document.state == DocumentState.READY,
            DocumentRevision.id == Document.current_revision_id,
        ]
        if document_ids:
            document_predicate.append(Document.id.in_(document_ids))
        query = func.plainto_tsquery("english", question)
        vector = func.to_tsvector("english", Chunk.content)
        rank = func.ts_rank_cd(vector, query)
        text_rows = (
            await db.execute(
                select(Chunk, rank.label("rank"))
                .join(DocumentRevision, DocumentRevision.id == Chunk.revision_id)
                .join(Document, Document.id == DocumentRevision.document_id)
                .where(*document_predicate, vector.op("@@")(query))
                .order_by(rank.desc(), Chunk.stable_id.asc())
                .limit(candidates)
            )
        ).all()

        fused: dict[uuid.UUID, _FusedCandidate] = {}
        for position, row in enumerate(vector_rows, start=1):
            item = fused.setdefault(row[0].id, _FusedCandidate(chunk=row[0]))
            item.score += 1.0 / (60 + position)
            item.vector_rank = position
            item.vector_similarity = max(-1.0, min(1.0, 1.0 - float(row[1])))
        for position, row in enumerate(text_rows, start=1):
            item = fused.setdefault(row[0].id, _FusedCandidate(chunk=row[0]))
            item.score += 1.0 / (60 + position)
            item.text_rank = position
            item.text_score = max(0.0, float(row[1]))

        ranked = sorted(
            fused.values(),
            key=lambda item: (-item.score, item.chunk.stable_id),
        )[: self.settings.retrieval_limit]
        chunks = tuple(
            RetrievedChunk(
                chunk=item.chunk,
                score=item.score,
                vector_rank=item.vector_rank,
                text_rank=item.text_rank,
                vector_similarity=item.vector_similarity,
                text_score=item.text_score,
            )
            for item in ranked
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        top = chunks[0] if chunks else None
        has_absolute_relevance = bool(
            top
            and (
                (top.vector_similarity or -1.0) >= self.settings.retrieval_min_vector_similarity
                or (top.text_score or 0.0) >= self.settings.retrieval_min_text_score
            )
        )
        sufficient = bool(
            top and top.score >= self.settings.retrieval_min_score and has_absolute_relevance
        )
        return RetrievalResult(chunks=chunks, elapsed_ms=elapsed_ms, sufficient=sufficient)


class EvidenceResolver:
    """Resolve model-returned identifiers against authoritative current revisions."""

    async def resolve_chunks(self, db: AsyncSession, stable_ids: list[str]) -> dict[str, Chunk]:
        if not stable_ids:
            return {}
        rows = list(
            (
                await db.scalars(
                    select(Chunk)
                    .join(DocumentRevision, DocumentRevision.id == Chunk.revision_id)
                    .join(Document, Document.id == DocumentRevision.document_id)
                    .where(
                        Chunk.stable_id.in_(stable_ids),
                        Document.deleted_at.is_(None),
                        Document.state == DocumentState.READY,
                        Document.current_revision_id == DocumentRevision.id,
                    )
                )
            )
            .unique()
            .all()
        )
        return {item.stable_id: item for item in rows}

    async def get_section(
        self, db: AsyncSession, document_id: uuid.UUID, anchor_key: str
    ) -> SourceAnchor | None:
        return cast(
            SourceAnchor | None,
            await db.scalar(
                select(SourceAnchor)
                .join(DocumentRevision, DocumentRevision.id == SourceAnchor.revision_id)
                .join(Document, Document.id == DocumentRevision.document_id)
                .where(
                    Document.id == document_id,
                    Document.deleted_at.is_(None),
                    Document.state == DocumentState.READY,
                    Document.current_revision_id == DocumentRevision.id,
                    SourceAnchor.stable_key == anchor_key,
                )
            ),
        )


evidence_resolver = EvidenceResolver()
