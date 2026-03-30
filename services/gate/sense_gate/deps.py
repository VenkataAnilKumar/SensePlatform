"""
Sense Gate — FastAPI Dependencies
Reusable dependency injectors for auth, tenant lookup, and DB sessions.
"""

import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sense_gate.database import get_db
from sense_gate.models.tenant import ApiKey, Tenant
from sense_gate.services.jwt_service import decode_token

logger = logging.getLogger(__name__)


async def get_tenant_from_api_key(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """
    Authenticate a request using an API key.
    Accepts key via Authorization: Bearer sk_live_... or X-API-Key header.
    """
    raw_key = None

    if x_api_key:
        raw_key = x_api_key
    elif authorization and authorization.startswith("Bearer "):
        raw_key = authorization.removeprefix("Bearer ").strip()

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Use X-API-Key header or Authorization: Bearer <key>",
        )

    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.key == raw_key, ApiKey.is_active == True)  # noqa: E712
        .join(Tenant)
        .where(Tenant.is_active == True)  # noqa: E712
    )
    api_key_row = result.scalar_one_or_none()

    if not api_key_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    # Lazy update last_used_at (fire-and-forget — don't block the request)
    from datetime import datetime, timezone
    api_key_row.last_used_at = datetime.now(timezone.utc)

    return api_key_row.tenant


async def get_current_user_from_jwt(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """
    Authenticate a request using a JWT issued by Sense Gate.
    Returns the decoded token payload.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT required. Use Authorization: Bearer <token>",
        )

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = decode_token(token)
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
        )


# Type aliases for cleaner router signatures
TenantDep = Annotated[Tenant, Depends(get_tenant_from_api_key)]
UserDep = Annotated[dict, Depends(get_current_user_from_jwt)]
DBDep = Annotated[AsyncSession, Depends(get_db)]
