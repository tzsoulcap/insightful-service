import uuid

from pydantic import BaseModel, Field

from app.schemas.common import DatetimeTZ7


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=8, max_length=128)
    user_type: str = Field("local", pattern=r"^(local|ad)$")
    role: str = Field("user", pattern=r"^(user|admin|super_admin)$")


class UserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=150)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field("user", pattern=r"^(user|admin|super_admin)$")


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    user_type: str
    role: str
    is_active: bool
    created_at: DatetimeTZ7
    updated_at: DatetimeTZ7 | None = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UpdateRoleRequest(BaseModel):
    role: str = Field(..., pattern=r"^(user|admin|super_admin)$")


class UpdateUserRequest(BaseModel):
    role: str | None = Field(None, pattern=r"^(user|admin|super_admin)$")
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class LDAPLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=1, max_length=128)


class LDAPLoginResponse(BaseModel):
    success: bool
    message: str
    user_dn: str | None = None


class UserListResponse(BaseModel):
    data: list[UserResponse]
    total: int
    page: int
    limit: int
    has_more: bool
