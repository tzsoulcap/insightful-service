import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class DifyService:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.DIFY_BASE_URL.rstrip("/")
        self._api_key = settings.DIFY_API_KEY

    @property
    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
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
        dataset_ids: list[str],
        user: str,
        conversation_id: str | None = None,
        inputs: dict | None = None,
        auto_generate_name: bool = False,
    ) -> AsyncGenerator[str, None]:
        merged_inputs = dict(inputs or {})
        merged_inputs["dataset_ids"] = dataset_ids

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
