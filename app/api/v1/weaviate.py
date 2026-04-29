from fastapi import APIRouter, HTTPException
import weaviate
import weaviate.classes.init as wvc
from weaviate.classes.query import Filter

router = APIRouter(tags=["Weaviate"])

# ตั้งค่าการเชื่อมต่อ (แนะนำให้ใช้จาก .env)
WEAVIATE_KEY = "WVF5YThaHlkYwhGUSmCRgsX3tD5ngdN8pkih"
COLLECTION_NAME = "Vector_index_7c8d4f7d_ee62_45d4_9a31_966270b292a7_Node"

@router.get("/api/get-page-number/{node_hash}")
async def get_page_number(node_hash: str):
    client = weaviate.connect_to_local(
        host="localhost",
        port=8090,
        grpc_port=50051,
        auth_credentials=wvc.Auth.api_key(WEAVIATE_KEY)
    )
    
    try:
        print(f"Connecting to Weaviate collection: {COLLECTION_NAME} to fetch page number for node_hash: {node_hash}")
        collection = client.collections.get(COLLECTION_NAME)
        print(f"Connected to Weaviate collection: {COLLECTION_NAME}")
        # ดึงเฉพาะฟิลด์ page โดยระบุ UUID ของ Node
        # หมายเหตุ: node_hash ที่ได้จาก Dify API คือ UUID ของวัตถุใน Weaviate
        print(f"Fetching object with ID: {node_hash} from Weaviate...")
        obj = collection.query.fetch_objects(
            filters=Filter.by_property("index_node_hash").equal(node_hash),
            limit=1
        )
        print(f"Received object from Weaviate: {obj}")
        
        if not obj:
            raise HTTPException(status_code=404, detail="Node not found")
            
        page_number = obj.properties.get("page")
        
        return {
            "node_hash": node_hash,
            "page_number": int(page_number) if page_number is not None else None,
            "document_id": obj.properties.get("document_id")
        }
        
    finally:
        client.close()