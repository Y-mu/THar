from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from langHar.api.knowledge.deps import get_knowledge_ingestion
from langHar.api.knowledge.ports import KnowledgeIngestionPort
from langHar.api.knowledge.schemas import KnowledgeIngestResponse
from langHar.core.knowledge import SUPPORTED_DOCUMENT_SUFFIXES


router = APIRouter(prefix="/knowledge", tags=["knowledge"])
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.post(
    "/{knowledge_base_id}/documents",
    response_model=KnowledgeIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_document(
    knowledge_base_id: str,
    file: Annotated[UploadFile, File(...)],
    acl: Annotated[str, Form()] = "admin,l1,l2",
    version: Annotated[str, Form()] = "v1",
    ingestion: KnowledgeIngestionPort = Depends(get_knowledge_ingestion),
) -> KnowledgeIngestResponse:
    if knowledge_base_id != "default":
        raise HTTPException(status_code=404, detail="MVP 仅提供 default 知识库。")
    filename = (file.filename or "").strip()
    suffix = _suffix(filename)
    if suffix not in SUPPORTED_DOCUMENT_SUFFIXES:
        raise HTTPException(status_code=415, detail="不支持的文档类型。")
    if not version.strip():
        raise HTTPException(status_code=422, detail="version 不能为空。")
    normalized_acl = _normalize_acl(acl)
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="单个文档不能超过 20 MB。")
    if not content:
        raise HTTPException(status_code=422, detail="上传文件不能为空。")

    try:
        chunks_indexed = await ingestion.ingest_file(
            content,
            filename,
            tenant_id="default",
            knowledge_base_id=knowledge_base_id,
            acl=normalized_acl,
            version=version.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return KnowledgeIngestResponse(
        knowledge_base_id=knowledge_base_id,
        filename=filename,
        chunks_indexed=chunks_indexed,
        version=version.strip(),
    )


def _suffix(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot >= 0 else ""


def _normalize_acl(value: str) -> str:
    levels = {item.strip().lower() for item in value.split(",") if item.strip()}
    allowed = {"admin", "l0", "l1", "l2"}
    if not levels or not levels.issubset(allowed):
        raise HTTPException(status_code=422, detail="acl 只能包含 admin、l0、l1、l2。")
    return ",".join(sorted(levels))
