import logging

import weaviate
import weaviate.classes.init as wvc
from weaviate.classes.query import Filter
from sqlalchemy import text

from app.core.config import Settings

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
