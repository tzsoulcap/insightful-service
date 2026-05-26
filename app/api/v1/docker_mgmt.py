import asyncio
from typing import Annotated

import docker
import docker.errors
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.v1.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/docker", tags=["Docker"])


class ContainerStatusResponse(BaseModel):
    name: str
    status: str  # running | exited | paused | restarting | dead | created | removing
    id: str
    image: str


def _get_client() -> docker.DockerClient:
    try:
        return docker.from_env()
    except docker.errors.DockerException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Docker daemon: {exc}",
        )


def _get_container(client: docker.DockerClient, name: str):
    try:
        return client.containers.get(name)
    except docker.errors.NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container '{name}' not found",
        )


def _require_admin(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )


# ── GET /docker/containers/{name} ─────────────────────────────────────────────

@router.get("/containers/{name}", response_model=ContainerStatusResponse)
async def get_container_status(
    name: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ContainerStatusResponse:
    _require_admin(current_user)

    def _check():
        client = _get_client()
        container = _get_container(client, name)
        container.reload()
        return ContainerStatusResponse(
            name=container.name,
            status=container.status,
            id=container.short_id,
            image=container.image.tags[0] if container.image.tags else container.image.short_id,
        )

    return await asyncio.to_thread(_check)


# ── POST /docker/containers/{name}/start ──────────────────────────────────────

@router.post("/containers/{name}/start", response_model=ContainerStatusResponse)
async def start_container(
    name: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ContainerStatusResponse:
    _require_admin(current_user)

    def _start():
        client = _get_client()
        container = _get_container(client, name)
        if container.status == "running":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Container '{name}' is already running",
            )
        container.start()
        container.reload()
        return ContainerStatusResponse(
            name=container.name,
            status=container.status,
            id=container.short_id,
            image=container.image.tags[0] if container.image.tags else container.image.short_id,
        )

    return await asyncio.to_thread(_start)


# ── POST /docker/containers/{name}/stop ───────────────────────────────────────

@router.post("/containers/{name}/stop", response_model=ContainerStatusResponse)
async def stop_container(
    name: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ContainerStatusResponse:
    _require_admin(current_user)

    def _stop():
        client = _get_client()
        container = _get_container(client, name)
        if container.status != "running":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Container '{name}' is not running (current status: {container.status})",
            )
        container.stop()
        container.reload()
        return ContainerStatusResponse(
            name=container.name,
            status=container.status,
            id=container.short_id,
            image=container.image.tags[0] if container.image.tags else container.image.short_id,
        )

    return await asyncio.to_thread(_stop)
