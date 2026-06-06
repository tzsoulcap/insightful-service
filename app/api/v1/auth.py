from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import create_access_token, decode_access_token
from app.models.user import User
from ldap3 import ALL, Connection, Server
from ldap3.core.exceptions import LDAPBindError, LDAPException

from app.schemas.auth import LDAPLoginRequest, LDAPLoginResponse, Token, UserRequest, UserResponse
from app.services.auth_service import authenticate_user, create_user, get_user_by_id, get_user_by_username

router = APIRouter(prefix="/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/token")


# ── Dependency: get_current_user ─────────────────────────────────
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    payload = decode_access_token(token, settings)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# ── POST /auth/register ─────────────────────────────────────────
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    existing = await get_user_by_username(session, body.username)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    user = await create_user(session, body.username, body.password, body.role)
    return user


# ── POST /auth/token  (OAuth2 compatible) ────────────────────────
@router.post("/token", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    user = await authenticate_user(session, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token({"sub": user.id, "role": user.role}, settings)
    return Token(access_token=access_token)


# ── POST /auth/ldap-login  (AD/LDAP test) ────────────────────────
@router.post("/ldap-login", response_model=LDAPLoginResponse)
async def ldap_login(
    body: LDAPLoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Test LDAP/AD authentication against the configured LDAP server."""
    if not settings.LDAP_SERVER_IP:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LDAP server is not configured",
        )

    user_dn = f"{body.username}@{settings.LDAP_DOMAIN}"

    try:
        server = Server(settings.LDAP_SERVER_IP, get_info=ALL, connect_timeout=5)
        conn = Connection(server, user=user_dn, password=body.password, raise_exceptions=True)
        conn.bind()
        conn.unbind()
        return LDAPLoginResponse(success=True, message="Login สำเร็จ", user_dn=user_dn)
    except LDAPBindError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="รหัสผ่านไม่ถูกต้อง หรือ username ไม่มีในระบบ",
        )
    except LDAPException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ไม่สามารถเชื่อมต่อกับ LDAP Server: {exc}",
        )


# ── GET /auth/me  (protected) ───────────────────────────────────
@router.get("/me", response_model=UserResponse)
async def me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user
