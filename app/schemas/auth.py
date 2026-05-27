from pydantic import BaseModel, Field

from app.schemas.common import DatetimeTZ7


class UserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=150)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field("staff", pattern=r"^(admin|staff|guest)$")


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    created_at: DatetimeTZ7
    updated_at: DatetimeTZ7

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UpdateRoleRequest(BaseModel):
    role: str = Field(..., pattern=r"^(admin|staff|guest)$")


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class UserListResponse(BaseModel):
    data: list[UserResponse]
    total: int
    page: int
    limit: int
    has_more: bool
