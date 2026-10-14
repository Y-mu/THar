from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from langHar.api.deps import ServiceContainer
from langHar.api.health.route import router as health_router
from langHar.api.knowledge.route import router as knowledge_router


def create_app(
    container_factory: Callable[[], ServiceContainer],
    *,
    cors_options: Mapping[str, Any] | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container = container_factory()
        app.state.container = container
        try:
            yield
        finally:
            del app.state.container

    application = FastAPI(
        title="TonyHar API",
        version="1.0.0",
        lifespan=lifespan,
    )
    if cors_options:
        application.add_middleware(CORSMiddleware, **cors_options)

    application.include_router(knowledge_router, prefix="/api/v1")
    application.include_router(health_router)
    return application
