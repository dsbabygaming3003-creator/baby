import secrets
from dataclasses import dataclass
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware

from .config import Settings, get_settings


@dataclass(frozen=True)
class Principal:
    id: str
    role: str
    correlation_id: str


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_principal(
    request: Request,
    api_key: str | None = Depends(api_key_header),
    settings: Settings = Depends(get_settings),
) -> Principal:
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    if settings.api_key is None:
        if settings.production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="TITAN_API_KEY must be configured in production",
            )
        return Principal(id="local-development-user", role="admin", correlation_id=correlation_id)
    if api_key is None or not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key"
        )
    return Principal(id="api-key-user", role="admin", correlation_id=correlation_id)


def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Administrator permission required"
        )
    return principal


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))[:36]
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response
