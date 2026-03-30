"""
Sense Gate — Auth Router
POST /auth/token — issue a JWT for a tenant user
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from sense_gate.deps import TenantDep
from sense_gate.services.jwt_service import create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])


class TokenRequest(BaseModel):
    user_id: str
    user_name: str = ""
    role: str = "user"
    expires_minutes: int | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


@router.post("/token", response_model=TokenResponse)
async def issue_token(body: TokenRequest, tenant: TenantDep):
    """
    Issue a Sense Gate JWT for a user in the authenticated tenant.

    Use this token to:
    - Authenticate WebSocket connections to Sense Wire
    - Call tenant-scoped endpoints

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    expires_minutes = body.expires_minutes or 60 * 24  # 24h default

    token = create_access_token(
        subject=body.user_id,
        tenant_id=str(tenant.id),
        extra={"role": body.role, "name": body.user_name, "tenant_slug": tenant.slug},
        expires_minutes=expires_minutes,
    )

    return TokenResponse(
        access_token=token,
        expires_in=expires_minutes * 60,
    )
