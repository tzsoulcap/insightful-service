import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

_DATASET_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class DifyService:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.DIFY_BASE_URL.rstrip("/")
        self._api_key = settings.DIFY_API_KEY
        self._knowledge_api_key = settings.DIFY_KNOWLEDGE_API_KEY

    @property
    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @property
    def _knowledge_auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._knowledge_api_key}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        payload: Any = None,
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = await client.request(
                method,
                f"{self._base_url}{path}",
                headers=self._auth_headers,
                params=params,
                json=payload,
            )
        return response

    async def _knowledge_request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        payload: Any = None,
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=_DATASET_TIMEOUT) as client:
            response = await client.request(
                method,
                f"{self._base_url}{path}",
                headers=self._knowledge_auth_headers,
                params=params,
                json=payload,
            )
        return response

    async def get_conversations(
        self,
        user: str,
        last_id: str | None = None,
        limit: int = 20,
        sort_by: str = "-updated_at",
    ) -> dict:
        params: dict = {"user": user, "limit": limit, "sort_by": sort_by}
        if last_id:
            params["last_id"] = last_id
        response = await self._request("GET", "/conversations", params=params)
        response.raise_for_status()
        return response.json()

    async def delete_conversation(self, conversation_id: str, user: str) -> None:
        response = await self._request(
            "DELETE",
            f"/conversations/{conversation_id}",
            payload={"user": user},
        )
        response.raise_for_status()

    async def rename_conversation(
        self,
        conversation_id: str,
        user: str,
        name: str | None = None,
        auto_generate: bool = False,
    ) -> dict:
        body: dict = {"user": user, "auto_generate": auto_generate}
        if name is not None:
            body["name"] = name
        response = await self._request(
            "POST",
            f"/conversations/{conversation_id}/name",
            payload=body,
        )
        response.raise_for_status()
        return response.json()

    async def get_messages(
        self,
        conversation_id: str,
        user: str,
        first_id: str | None = None,
        limit: int = 20,
    ) -> dict:
        params: dict = {"conversation_id": conversation_id, "user": user, "limit": limit}
        if first_id:
            params["first_id"] = first_id
        response = await self._request("GET", "/messages", params=params)
        response.raise_for_status()
        return response.json()

    async def chat_stream(
        self,
        query: str,
        user: str,
        conversation_id: str | None = None,
        inputs: dict | None = None,
        auto_generate_name: bool = False,
    ) -> AsyncGenerator[str, None]:
        merged_inputs = dict(inputs or {})

        payload: dict = {
            "query": query,
            "inputs": merged_inputs,
            "response_mode": "streaming",
            "user": user,
            "auto_generate_name": auto_generate_name,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        print(f"Sending chat request to Dify with payload: {payload}")

        headers = self._auth_headers

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat-messages",
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    logger.error("Dify API error %s: %s", response.status_code, body.decode())
                    error_event = {
                        "event": "error",
                        "status": response.status_code,
                        "message": "Dify API request failed",
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        yield f"{line}\n\n"
                    elif line.strip() == "":
                        continue
                    else:
                        yield f"data: {line}\n\n"

    # ── Knowledge Bases ───────────────────────────────────────────────────────

    async def list_datasets(
        self,
        page: int = 1,
        limit: int = 20,
        keyword: str | None = None,
        include_all: bool = False,
        tag_ids: list[str] | None = None,
    ) -> dict:
        params: dict = {"page": page, "limit": limit, "include_all": include_all}
        if keyword:
            params["keyword"] = keyword
        if tag_ids:
            params["tag_ids"] = tag_ids
        response = await self._knowledge_request("GET", "/datasets", params=params)
        response.raise_for_status()
        return response.json()

    async def create_dataset(self, payload: dict) -> dict:
        response = await self._knowledge_request("POST", "/datasets", payload=payload)
        response.raise_for_status()
        return response.json()

    async def get_dataset(self, dataset_id: str) -> dict:
        response = await self._knowledge_request("GET", f"/datasets/{dataset_id}")
        response.raise_for_status()
        return response.json()

    async def delete_dataset(self, dataset_id: str) -> None:
        response = await self._knowledge_request("DELETE", f"/datasets/{dataset_id}")
        response.raise_for_status()

    # ── Documents ─────────────────────────────────────────────────────────────

    async def list_documents(
        self,
        dataset_id: str,
        page: int = 1,
        limit: int = 20,
        keyword: str | None = None,
        status: str | None = None,
    ) -> dict:
        params: dict = {"page": page, "limit": limit}
        if keyword:
            params["keyword"] = keyword
        if status:
            params["status"] = status
        response = await self._knowledge_request("GET", f"/datasets/{dataset_id}/documents", params=params)
        response.raise_for_status()
        return response.json()

    async def create_document_by_text(self, dataset_id: str, payload: dict) -> dict:
        response = await self._knowledge_request(
            "POST", f"/datasets/{dataset_id}/document/create-by-text", payload=payload
        )
        response.raise_for_status()
        return response.json()

    async def create_document_by_file(
        self, dataset_id: str, file_content: bytes, filename: str, data_json: str
    ) -> dict:
        files = {"file": (filename, file_content)}
        form = {"data": data_json}
        async with httpx.AsyncClient(timeout=_DATASET_TIMEOUT) as client:
            response = await client.post(
                f"{self._base_url}/datasets/{dataset_id}/document/create-by-file",
                headers={"Authorization": f"Bearer {self._knowledge_api_key}"},
                files=files,
                data=form,
            )
        response.raise_for_status()
        return response.json()

    async def delete_document(self, dataset_id: str, document_id: str) -> None:
        response = await self._knowledge_request(
            "DELETE", f"/datasets/{dataset_id}/documents/{document_id}"
        )
        response.raise_for_status()

    async def get_indexing_status(self, dataset_id: str, batch: str) -> dict:
        response = await self._knowledge_request(
            "GET", f"/datasets/{dataset_id}/documents/{batch}/indexing-status"
        )
        response.raise_for_status()
        return response.json()
