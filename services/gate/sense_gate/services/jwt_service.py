"""
Sense Gate — JWT Service
Issues and validates JWT tokens for tenant users.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from sense_gate.config import get_settings

settings = get_settings()


def create_access_token(
    subject: str,
    tenant_id: str,
    extra: dict[str, Any] | None = None,
    expires_minutes: int | None = None,
) -> str:
    """
    Issue a signed JWT for a user.

    Args:
        subject:     User ID or identifier.
        tenant_id:   Tenant this token belongs to.
        extra:       Additional claims (role, room, etc.)
        expires_minutes: Override default expiry.

    Returns:
        Signed JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.jwt_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra:
        payload.update(extra)

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT.

    Returns:
        Decoded payload dict.

    Raises:
        JWTError if token is invalid or expired.
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def create_room_token(
    tenant_id: str,
    user_id: str,
    room_id: str,
    role: str = "participant",
) -> str:
    """Issue a short-lived room-scoped JWT (15 minutes)."""
    return create_access_token(
        subject=user_id,
        tenant_id=tenant_id,
        extra={"room_id": room_id, "role": role},
        expires_minutes=15,
    )
