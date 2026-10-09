"""进程存活和应用就绪检查。"""

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    required_services = (
        "agent_service",
        "auth_service",
        "chat_service",
        "session_service",
    )
    if any(
        getattr(request.app.state, name, None) is None
        for name in required_services
    ):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready"},
        )
    return JSONResponse(content={"status": "ready"})
