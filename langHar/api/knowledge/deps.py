from __future__ import annotations

from fastapi import HTTPException, Request, status

from langHar.api.deps import get_container
from langHar.api.knowledge.ports import KnowledgeIngestionPort


def get_knowledge_ingestion(request: Request) -> KnowledgeIngestionPort:
    service = get_container(request).knowledge_ingestion
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="知识库入库服务未配置。",
        )
    return service
