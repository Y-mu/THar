from contextlib import asynccontextmanager

from fastapi import FastAPI

from langHar.agents.agent_factory import create_agent_service
from langHar.api.modules.auth.router import router as auth_router
from langHar.api.modules.auth.service import AuthService
from langHar.api.modules.chat.router import router as chat_router
from langHar.api.modules.chat.service import ChatService
from langHar.api.modules.conversation.router import router as conversation_router
from langHar.api.modules.conversation.service import ConversationService
from langHar.api.modules.health.router import router as health_router

def create_app(
    agent_service_factory=create_agent_service,
    auth_service_factory=AuthService,
    conversation_service_factory=ConversationService,
    chat_service_factory=ChatService,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        agent_service = agent_service_factory()
        auth_service = auth_service_factory()
        conversation_service = conversation_service_factory()
        chat_service = chat_service_factory(
            conversations=conversation_service,
            agent=agent_service,
        )

        app.state.agent_service = agent_service
        app.state.auth_service = auth_service
        app.state.conversation_service = conversation_service
        app.state.chat_service = chat_service

        try:
            yield
        finally:
            await agent_service.aclose()

    application = FastAPI(
        title="TonyHar API",
        version="1.0.0",
        lifespan=lifespan,
    )

    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(conversation_router, prefix="/api/v1")
    application.include_router(chat_router, prefix="/api/v1")
    application.include_router(health_router)
    return application


app = create_app()
