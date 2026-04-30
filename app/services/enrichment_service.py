import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

import weaviate
import weaviate.classes.init as wvc
from weaviate.classes.query import Filter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings

logger = logging.getLogger(__name__)

_BATCH_SEGMENT_QUERY = text("""
    SELECT
        ds.id            AS segment_id,
        ds.dataset_id,
        ds.index_node_id,
        uf.name          AS file_name,
        uf.key           AS file_key
    FROM document_segments ds
    JOIN documents d  ON d.id = ds.document_id
    JOIN upload_files uf
        ON uf.id = (d.data_source_info::jsonb ->> 'upload_file_id')::uuid
    WHERE ds.id = ANY(:segment_ids)
""")


@dataclass(frozen=True, slots=True)
class SegmentMeta:
    segment_id: str
    dataset_id: str
    index_node_id: str
    file_name: str
    file_key: str


def _collection_name(dataset_id: str) -> str:
    return f"Vector_index_{dataset_id.replace('-', '_')}_Node"


def _batch_weaviate_pages(
    settings: Settings,
    lookups: list[tuple[str, str]],
) -> dict[str, int | None]:
    if not lookups:
        return {}

    by_collection: dict[str, list[str]] = defaultdict(list)
    for col_name, node_id in lookups:
        by_collection[col_name].append(node_id)

    result: dict[str, int | None] = {}

    client = weaviate.connect_to_local(
        host=settings.DIFY_WEAVIATE_HOST.replace("http://", "").replace("https://", ""),
        port=settings.DIFY_WEAVIATE_PORT,
        grpc_port=settings.DIFY_WEAVIATE_GRPC_PORT,
        auth_credentials=wvc.Auth.api_key(settings.DIFY_WEAVIATE_KEY),
    )
    if not client.is_ready():
        client.close()
        raise ConnectionError("Failed to connect to Weaviate")

    try:
        for col_name, node_ids in by_collection.items():
            try:
                collection = client.collections.get(col_name)

                combined_filter = Filter.by_property("doc_id").equal(node_ids[0])
                for nid in node_ids[1:]:
                    combined_filter = combined_filter | Filter.by_property("doc_id").equal(nid)

                objects = collection.query.fetch_objects(
                    filters=combined_filter,
                    limit=len(node_ids),
                ).objects

                found: dict[str, int | None] = {}
                for obj in objects:
                    doc_id = obj.properties.get("doc_id")
                    page = obj.properties.get("page")
                    if doc_id is not None:
                        found[doc_id] = int(page) if page is not None else None

                for nid in node_ids:
                    result[nid] = found.get(nid)

            except Exception as exc:
                logger.warning(
                    "Weaviate batch lookup failed for collection %s: %s",
                    col_name, exc,
                )
                for nid in node_ids:
                    result[nid] = None
    finally:
        client.close()

    return result


async def enrich_messages(
    data: dict,
    session: AsyncSession,
    settings: Settings,
    pdf_url_builder: Callable[[str], str],
) -> None:
    """Enrich all retriever_resources in a messages response dict, in-place.

    1. Collect unique segment_ids across all messages
    2. Single batch SQL query -> segment metadata
    3. Single batch Weaviate call (in thread) -> page numbers
    4. Attach enriched_metadata to each resource
    """
    # 1. Collect all segment_ids
    resource_refs: list[tuple[dict, str]] = []
    for message in data.get("data", []):
        for resource in message.get("retriever_resources", []):
            sid = resource.get("segment_id")
            if sid:
                resource_refs.append((resource, sid))

    if not resource_refs:
        return

    unique_ids = list({sid for _, sid in resource_refs})

    # 2. Batch SQL query
    try:
        result = await session.execute(
            _BATCH_SEGMENT_QUERY, {"segment_ids": unique_ids}
        )
        rows = result.all()
    except Exception as exc:
        logger.warning("Batch DB lookup failed: %s", exc)
        return

    meta_map: dict[str, SegmentMeta] = {}
    for row in rows:
        meta_map[str(row.segment_id)] = SegmentMeta(
            segment_id=str(row.segment_id),
            dataset_id=str(row.dataset_id),
            index_node_id=str(row.index_node_id),
            file_name=row.file_name,
            file_key=row.file_key,
        )

    if not meta_map:
        return

    # 3. Batch Weaviate (single connection, grouped by collection)
    lookups = [
        (_collection_name(m.dataset_id), m.index_node_id)
        for m in meta_map.values()
    ]

    try:
        page_map = await asyncio.to_thread(
            _batch_weaviate_pages, settings, lookups
        )
    except Exception as exc:
        logger.warning("Batch Weaviate lookup failed: %s", exc)
        page_map = {}

    # 4. Attach enriched_metadata
    for resource, sid in resource_refs:
        meta = meta_map.get(sid)
        if meta is None:
            continue
        resource["enriched_metadata"] = {
            "page_number": page_map.get(meta.index_node_id),
            "file_name": meta.file_name,
            "pdf_url": pdf_url_builder(meta.file_key),
        }
