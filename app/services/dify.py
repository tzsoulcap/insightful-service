import json
import logging
from collections.abc import AsyncGenerator

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class DifyService:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.DIFY_BASE_URL.rstrip("/")
        self._api_key = settings.DIFY_API_KEY

    async def chat_stream(
        self,
        query: str,
        dataset_ids: list[str],
        user: str,
        conversation_id: str | None = None,
        inputs: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        merged_inputs = dict(inputs or {})
        merged_inputs["dataset_ids"] = dataset_ids

        payload: dict = {
            "query": query,
            "inputs": merged_inputs,
            "response_mode": "streaming",
            "user": user,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

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
