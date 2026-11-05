"""FastAPI dependencies: authentication, RBAC, rate limiting."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..security.core import Principal, decode_jwt, scopes_for_role
from ..services.observability import metrics

# In-process sliding-window rate limiter (single-node deployments).
_BUCKETS: dict[str, deque] = defaultdict(deque)
_LIMITS: dict[str, tuple[int, int]] = {}


def rate_limit(per_minute: int = 120, burst: int = 40) -> None:
    """Register a limiter profile (documented; enforced per-tenant below)."""
    _LIMITS["default"] = (per_minute, burst)


def enforce_rate_limit(key: str, per_minute: int, burst: int) -> None:
    now = time.time()
    bucket = _BUCKETS[key]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= per_minute + burst:
        retry_after = int(60 - (now - bucket[0])) if bucket else 60
        metrics.incr("rate_limited_total")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"rate limit exceeded; retry in {retry_after}s",
            headers={"Retry-After": str(retry_after)},
        )
    bucket.append(now)


async def current_principal(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Principal:
    """Resolve the caller. Accepts a bearer JWT or a TITAN API key."""
    from ..models import User
    from sqlalchemy import select

    per_minute, burst = _LIMITS.get("default", (120, 40))
    enforce_rate_limit(f"ip:{request.client.host if request.client else 'unknown'}", per_minute, burst)

    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing Authorization header")

    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() == "bearer":
        try:
            claims = decode_jwt(credential)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        user = (await session.execute(
            select(User).where(User.id == claims.get("sub"))
        )).scalar_one_or_none()
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user is not active")
        enforce_rate_limit(f"user:{user.id}", per_minute, burst)
        return Principal(user_id=user.id, org_id=user.org_id, role=user.role,
                         scopes=scopes_for_role(user.role))

    if scheme.lower() == "apikey":
        from ..models import ToolPermission  # noqa: F401  (ensure models imported)
        from ..security.core import hash_api_key
        from ..models import User as UserModel
        from sqlalchemy import select as select_

        digest = hash_api_key(credential)
        user = (await session.execute(
            select_(UserModel).where(UserModel.email == f"apikey:{digest}")
        )).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown API key")
        return Principal(user_id=user.id, org_id=user.org_id, role=user.role,
                         scopes=scopes_for_role(user.role))

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="unsupported authorization scheme (use Bearer or ApiKey)")


def require_scope(scope: str):
    """Dependency factory that enforces a scope on the resolved principal."""

    async def _dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if not principal.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role '{principal.role}' lacks scope '{scope}'",
            )
        return principal

    return _dependency
