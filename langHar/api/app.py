from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from langHar.api.deps import ServiceContainer
from langHar.api.auth.route import router as auth_router
from langHar.api.chat.route import router as chat_router
from langHar.api.health.route import router as health_router
from langHar.api.session.route import router as session_router


def create_app(
    container_factory: Callable[[], ServiceContainer],
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container = container_factory()
        app.state.container = container
        try:
            yield
        finally:
            await container.aclose()

    application = FastAPI(
        title="TonyHar API",
        version="1.0.0",
        lifespan=lifespan,
    )

    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(session_router, prefix="/api/v1")
    application.include_router(chat_router, prefix="/api/v1")
    application.include_router(health_router)
    return application
