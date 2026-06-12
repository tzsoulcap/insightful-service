import asyncio
import hashlib
import logging
import uuid

from app.schemas.retrieval import AllowedKnowledgeBase, ChunkMetadata, NormalizedChunk
from app.services.dify import DifyService

logger = logging.getLogger(__name__)

_PER_DATASET_TOP_K = 5
_FINAL_TOP_K = 8
_MAX_PARALLEL_REQUESTS = 3
_SCORE_THRESHOLD = 0.3


class RetrievalService:
    def __init__(self, dify_service: DifyService) -> None:
        self._dify = dify_service

    # ── Normalization ─────────────────────────────────────────────────────────

    def _normalize_record(
        self,
        record: dict,
        knowledge_id: uuid.UUID,
        dify_dataset_id: str,
        dify_dataset_name: str,
    ) -> NormalizedChunk | None:
        segment = record.get("segment") or {}
        content = segment.get("content", "").strip()
        if not content:
            return None
        document = segment.get("document") or {}
        return NormalizedChunk(
            knowledge_id=knowledge_id,
            dify_dataset_id=dify_dataset_id,
            dify_dataset_name=dify_dataset_name,
            dify_document_id=segment.get("document_id", ""),
            dify_document_name=document.get("name", ""),
            dify_segment_id=segment.get("id", ""),
            segment_position=segment.get("position", 0),
            content=content,
            score=float(record.get("score") or 0.0),
            metadata=ChunkMetadata(
                index_node_id=segment.get("index_node_id", ""),
                index_node_hash=segment.get("index_node_hash", ""),
                word_count=segment.get("word_count", 0),
                tokens=segment.get("tokens", 0),
            ),
        )

    # ── Single dataset retrieval ──────────────────────────────────────────────

    async def _retrieve_single(
        self,
        semaphore: asyncio.Semaphore,
        knowledge_id: uuid.UUID,
        dify_dataset_id: str,
        dify_dataset_name: str,
        query: str,
    ) -> list[NormalizedChunk]:
        async with semaphore:
            try:
                records = await self._dify.retrieve_dataset(
                    dify_dataset_id,
                    query,
                    top_k=_PER_DATASET_TOP_K,
                    score_threshold=_SCORE_THRESHOLD,
                    score_threshold_enabled=True,
                )
            except Exception as exc:
                logger.warning(
                    "Retrieval failed for dataset %s: %s",
                    dify_dataset_id,
                    exc,
                )
                return []

        chunks: list[NormalizedChunk] = []
        for record in records:
            chunk = self._normalize_record(
                record, knowledge_id, dify_dataset_id, dify_dataset_name
            )
            if chunk is not None:
                chunks.append(chunk)
        return chunks

    # ── Deduplication ─────────────────────────────────────────────────────────

    def _deduplicate(self, chunks: list[NormalizedChunk]) -> list[NormalizedChunk]:
        # Dedup by segment_id — keep highest score
        best_by_segment: dict[str, NormalizedChunk] = {}
        for chunk in chunks:
            sid = chunk.dify_segment_id
            if sid not in best_by_segment or chunk.score > best_by_segment[sid].score:
                best_by_segment[sid] = chunk

        # Secondary dedup by content hash — keep highest score
        best_by_hash: dict[str, NormalizedChunk] = {}
        for chunk in best_by_segment.values():
            h = hashlib.sha256(chunk.content.encode()).hexdigest()
            if h not in best_by_hash or chunk.score > best_by_hash[h].score:
                best_by_hash[h] = chunk

        return list(best_by_hash.values())

    # ── Context builder ───────────────────────────────────────────────────────

    def _build_context(self, chunks: list[NormalizedChunk]) -> str:
        return "\n\n".join(f"[{i}] {c.content}" for i, c in enumerate(chunks, 1))

    # ── Public API ────────────────────────────────────────────────────────────

    async def retrieve_allowed_context(
        self,
        allowed_kbs: list[AllowedKnowledgeBase],
        query: str,
    ) -> tuple[list[NormalizedChunk], str]:
        """Retrieve, deduplicate, and rank chunks from all allowed knowledge bases.

        Returns:
            (selected_chunks, context_text) where selected_chunks is the
            top-ranked deduplicated list and context_text is the formatted
            string ready to pass into Dify Chatflow.
        """
        if not allowed_kbs:
            return [], ""

        semaphore = asyncio.Semaphore(_MAX_PARALLEL_REQUESTS)
        tasks = [
            self._retrieve_single(
                semaphore,
                kb.knowledge_id,
                kb.dify_dataset_id,
                kb.dify_dataset_name,
                query,
            )
            for kb in allowed_kbs
        ]
        results = await asyncio.gather(*tasks)

        all_chunks: list[NormalizedChunk] = [
            chunk for batch in results for chunk in batch
        ]
        logger.debug(
            "Retrieved %d raw chunks from %d datasets",
            len(all_chunks),
            len(allowed_kbs),
        )

        deduped = self._deduplicate(all_chunks)
        selected = sorted(deduped, key=lambda c: c.score, reverse=True)[:_FINAL_TOP_K]

        logger.debug("Selected %d chunks after dedup+sort", len(selected))

        context = self._build_context(selected)
        return selected, context
