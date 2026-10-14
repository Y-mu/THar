"""跨 API 模块的最小容器契约。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from fastapi import Request

if TYPE_CHECKING:
    from langHar.api.knowledge.ports import KnowledgeIngestionPort


class ServiceContainer(Protocol):
    knowledge_ingestion: KnowledgeIngestionPort | None


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container
