import uuid

from pydantic import BaseModel, Field

from app.schemas.common import DatetimeTZ7


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None


class GroupMemberResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    user_id: uuid.UUID

    model_config = {"from_attributes": True}


class GroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    created_at: DatetimeTZ7

    model_config = {"from_attributes": True}


class GroupDetailResponse(GroupResponse):
    members: list[GroupMemberResponse] = []


class GroupListResponse(BaseModel):
    data: list[GroupResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class AddGroupMemberRequest(BaseModel):
    user_id: uuid.UUID


class AddGroupMembersRequest(BaseModel):
    user_ids: list[uuid.UUID] = Field(..., min_length=1)
