import json
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status

from app.api.deps import get_dify_service
from app.schemas.knowledge_base import (
    CreateDocumentByTextRequest,
    CreateDocumentResponse,
    CreateKnowledgeBaseRequest,
    DocumentListResponse,
    IndexingStatusResponse,
    KnowledgeBaseItem,
    KnowledgeBaseListResponse,
    UpdateKnowledgeBaseRequest,
)
from app.services.dify import DifyService

router = APIRouter(prefix="/knowledge-bases", tags=["Knowledge Bases"])


def _handle_dify_error(exc: Exception) -> None:
    """Re-raise httpx HTTP errors with Dify's original status code and body."""
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        raise HTTPException(status_code=exc.response.status_code, detail=detail)
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


# ── Knowledge Base endpoints ──────────────────────────────────────────────────

@router.get("", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    service: Annotated[DifyService, Depends(get_dify_service)],
    page: int = 1,
    limit: int = 20,
    keyword: str | None = None,
    include_all: bool = False,
) -> KnowledgeBaseListResponse:
    try:
        data = await service.list_datasets(
            page=page,
            limit=max(1, min(limit, 100)),
            keyword=keyword,
            include_all=include_all,
        )
    except Exception as exc:
        _handle_dify_error(exc)
    return KnowledgeBaseListResponse(**data)


@router.post("", response_model=KnowledgeBaseItem, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    body: CreateKnowledgeBaseRequest,
    service: Annotated[DifyService, Depends(get_dify_service)],
) -> KnowledgeBaseItem:
    payload = body.model_dump()
    try:
        data = await service.create_dataset(payload)
    except Exception as exc:
        _handle_dify_error(exc)
    return KnowledgeBaseItem(**data)


@router.get("/{dataset_id}", response_model=KnowledgeBaseItem)
async def get_knowledge_base(
    dataset_id: str,
    service: Annotated[DifyService, Depends(get_dify_service)],
) -> KnowledgeBaseItem:
    try:
        data = await service.get_dataset(dataset_id)
    except Exception as exc:
        _handle_dify_error(exc)
    return KnowledgeBaseItem(**data)


@router.patch("/{dataset_id}", response_model=KnowledgeBaseItem)
async def update_knowledge_base(
    dataset_id: str,
    body: UpdateKnowledgeBaseRequest,
    service: Annotated[DifyService, Depends(get_dify_service)],
) -> KnowledgeBaseItem:
    try:
        data = await service.patch_dataset(dataset_id, {"name": body.name})
    except Exception as exc:
        _handle_dify_error(exc)
    return KnowledgeBaseItem(**data)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    dataset_id: str,
    service: Annotated[DifyService, Depends(get_dify_service)],
) -> Response:
    try:
        await service.delete_dataset(dataset_id)
    except Exception as exc:
        _handle_dify_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Document endpoints ────────────────────────────────────────────────────────

@router.get("/{dataset_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    dataset_id: str,
    service: Annotated[DifyService, Depends(get_dify_service)],
    page: int = 1,
    limit: int = 20,
    keyword: str | None = None,
    status: str | None = None,
) -> DocumentListResponse:
    try:
        data = await service.list_documents(
            dataset_id=dataset_id,
            page=page,
            limit=max(1, min(limit, 100)),
            keyword=keyword,
            status=status,
        )
    except Exception as exc:
        _handle_dify_error(exc)
    data["has_more"] = (page * max(1, min(limit, 100))) < data.get("total", 0)
    return DocumentListResponse(**data)


@router.post("/{dataset_id}/documents/text", response_model=CreateDocumentResponse)
async def create_document_by_text(
    dataset_id: str,
    body: CreateDocumentByTextRequest,
    service: Annotated[DifyService, Depends(get_dify_service)],
) -> CreateDocumentResponse:
    payload = body.model_dump(exclude_none=True)
    try:
        data = await service.create_document_by_text(dataset_id, payload)
    except Exception as exc:
        _handle_dify_error(exc)
    return CreateDocumentResponse(**data)


@router.post("/{dataset_id}/documents/file", response_model=CreateDocumentResponse)
async def create_document_by_file(
    dataset_id: str,
    service: Annotated[DifyService, Depends(get_dify_service)],
    file: UploadFile = File(...),
    indexing_technique: str = Form("high_quality"),
    doc_form: str = Form("text_model"),
    doc_language: str = Form("English"),
) -> CreateDocumentResponse:
    file_content = await file.read()
    data_json = json.dumps({
        "indexing_technique": indexing_technique,
        "doc_form": doc_form,
        "doc_language": doc_language,
        "process_rule": {"mode": "automatic"},
    })
    try:
        data = await service.create_document_by_file(
            dataset_id=dataset_id,
            file_content=file_content,
            filename=file.filename or "upload",
            data_json=data_json,
        )
    except Exception as exc:
        _handle_dify_error(exc)
    return CreateDocumentResponse(**data)


@router.delete(
    "/{dataset_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    dataset_id: str,
    document_id: str,
    service: Annotated[DifyService, Depends(get_dify_service)],
) -> Response:
    try:
        await service.delete_document(dataset_id, document_id)
    except Exception as exc:
        _handle_dify_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{dataset_id}/documents/{batch}/indexing-status",
    response_model=IndexingStatusResponse,
)
async def get_indexing_status(
    dataset_id: str,
    batch: str,
    service: Annotated[DifyService, Depends(get_dify_service)],
) -> IndexingStatusResponse:
    try:
        data = await service.get_indexing_status(dataset_id, batch)
    except Exception as exc:
        _handle_dify_error(exc)
    return IndexingStatusResponse(**data)
