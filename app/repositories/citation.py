import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.citation import ChatMessageCitation


class CitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, citation_id: uuid.UUID) -> ChatMessageCitation | None:
        result = await self._session.execute(
            select(ChatMessageCitation).where(ChatMessageCitation.id == citation_id)
        )
        return result.scalar_one_or_none()

    async def find_by_message_id(self, dify_message_id: str) -> list[ChatMessageCitation]:
        result = await self._session.execute(
            select(ChatMessageCitation)
            .where(ChatMessageCitation.dify_message_id == dify_message_id)
            .order_by(ChatMessageCitation.position)
        )
        return list(result.scalars().all())

    async def find_by_message_ids(
        self, dify_message_ids: list[str]
    ) -> list[ChatMessageCitation]:
        if not dify_message_ids:
            return []
        result = await self._session.execute(
            select(ChatMessageCitation)
            .where(ChatMessageCitation.dify_message_id.in_(dify_message_ids))
            .order_by(ChatMessageCitation.dify_message_id, ChatMessageCitation.position)
        )
        return list(result.scalars().all())

    async def find_by_conversation_id(
        self, dify_conversation_id: str
    ) -> list[ChatMessageCitation]:
        result = await self._session.execute(
            select(ChatMessageCitation)
            .where(ChatMessageCitation.dify_conversation_id == dify_conversation_id)
            .order_by(ChatMessageCitation.dify_message_id, ChatMessageCitation.position)
        )
        return list(result.scalars().all())

    async def bulk_insert(self, citations: list[ChatMessageCitation]) -> list[ChatMessageCitation]:
        for c in citations:
            self._session.add(c)
        await self._session.flush()
        return citations

    async def delete_by_message_id(self, dify_message_id: str) -> None:
        citations = await self.find_by_message_id(dify_message_id)
        for c in citations:
            await self._session.delete(c)
        await self._session.flush()
