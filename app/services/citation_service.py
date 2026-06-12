import hashlib
import logging
import uuid

import weaviate
import weaviate.classes.init as wvc
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from weaviate.classes.query import Filter

from app.core.config import Settings
from app.models.batch import ProcessPdf
from app.models.citation import ChatMessageCitation
from app.repositories.citation import CitationRepository
from app.schemas.retrieval import NormalizedChunk

logger = logging.getLogger(__name__)

SEGMENT_QUERY = text("""
    SELECT
        ds.dataset_id,
        ds.index_node_id,
        d.id AS document_id
    FROM document_segments ds
    JOIN documents d ON d.id = ds.document_id
    WHERE ds.id = :segment_id
    LIMIT 1
""")


def collection_name_for_dataset(dataset_id: str) -> str:
    return f"Vector_index_{dataset_id.replace('-', '_')}_Node"


def get_page_from_weaviate(
    settings: Settings, collection_name: str, index_node_id: str
) -> int | None:
    client = weaviate.connect_to_local(
        host=settings.DIFY_WEAVIATE_HOST.replace("http://", "").replace("https://", ""),
        port=settings.DIFY_WEAVIATE_PORT,
        grpc_port=settings.DIFY_WEAVIATE_GRPC_PORT,
        auth_credentials=wvc.Auth.api_key(settings.DIFY_WEAVIATE_KEY),
    )
    if not client.is_ready():
        raise ConnectionError("Failed to connect to Weaviate")
    try:
        collection = client.collections.get(collection_name)
        objects = collection.query.fetch_objects(
            filters=Filter.by_property("doc_id").equal(index_node_id),
            limit=1,
        ).objects
        if not objects:
            return None
        page = objects[0].properties.get("page")
        return int(page) if page is not None else None
    finally:
        client.close()


# ── CitationService ───────────────────────────────────────────────────────────


class CitationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CitationRepository(session)

    async def _resolve_process_pdf(
        self, dify_document_id: str
    ) -> tuple[uuid.UUID | None, str | None, str | None]:
        """Return (process_pdf_id, filename, original_file_path) for a dify_document_id."""
        result = await self._session.execute(
            select(ProcessPdf.id, ProcessPdf.filename, ProcessPdf.original_file_path).where(
                ProcessPdf.dify_document_id == dify_document_id
            )
        )
        row = result.first()
        if row is None:
            return None, None, None
        return row.id, row.filename, row.original_file_path

    async def save_message_citations(
        self,
        dify_conversation_id: str,
        dify_message_id: str,
        user_id: uuid.UUID,
        selected_chunks: list[NormalizedChunk],
    ) -> list[ChatMessageCitation]:
        """Build and insert ChatMessageCitation rows for all selected chunks.

        Resolves process_pdf_id and file metadata from ProcessPdf table.
        Citation insert errors are logged but do not propagate — the caller
        should still deliver the answer to the Frontend.
        """
        if not selected_chunks:
            return []

        # Batch-resolve process_pdf info for all unique document_ids
        doc_ids = list({c.dify_document_id for c in selected_chunks if c.dify_document_id})
        pdf_map: dict[str, tuple[uuid.UUID | None, str | None, str | None]] = {}
        for doc_id in doc_ids:
            pdf_map[doc_id] = await self._resolve_process_pdf(doc_id)

        rows: list[ChatMessageCitation] = []
        for rank, chunk in enumerate(selected_chunks, 1):
            pdf_id, file_name, file_path = pdf_map.get(
                chunk.dify_document_id, (None, None, None)
            )
            content_hash = hashlib.sha256(chunk.content.encode()).hexdigest()
            rows.append(
                ChatMessageCitation(
                    dify_conversation_id=dify_conversation_id,
                    dify_message_id=dify_message_id,
                    user_id=user_id,
                    knowledge_id=chunk.knowledge_id,
                    process_pdf_id=pdf_id,
                    position=rank,
                    dify_dataset_id=chunk.dify_dataset_id,
                    dify_dataset_name=chunk.dify_dataset_name,
                    dify_document_id=chunk.dify_document_id,
                    dify_document_name=chunk.dify_document_name,
                    dify_segment_id=chunk.dify_segment_id,
                    segment_position=chunk.segment_position,
                    score=chunk.score,
                    retrieval_rank=rank,
                    search_method="hybrid_search",
                    content=chunk.content,
                    content_hash=content_hash,
                    file_name=file_name or chunk.dify_document_name,
                    file_path=file_path,
                    page_no=None,
                    extra_metadata=chunk.metadata.model_dump(),
                )
            )

        try:
            saved = await self._repo.bulk_insert(rows)
            await self._session.commit()
            logger.info(
                "Saved %d citations for message_id=%s", len(saved), dify_message_id
            )
            return saved
        except Exception as exc:
            await self._session.rollback()
            logger.error(
                "Failed to save citations for message_id=%s: %s", dify_message_id, exc
            )
            return []
