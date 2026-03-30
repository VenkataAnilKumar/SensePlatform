"""
Sense Gate — Tenants Router
CRUD for tenant management + API key issuance.
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from sense_gate.database import get_db
from sense_gate.deps import DBDep, TenantDep
from sense_gate.models.tenant import ApiKey, Tenant

router = APIRouter(prefix="/tenants", tags=["Tenants"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CreateTenantRequest(BaseModel):
    name: str
    slug: str
    email: str


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    email: str
    is_active: bool

    model_config = {"from_attributes": True}


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    is_test: bool

    model_config = {"from_attributes": True}


class CreateApiKeyRequest(BaseModel):
    name: str = "Default Key"
    test: bool = False


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(body: CreateTenantRequest, db: DBDep):
    """
    Create a new tenant (developer account / product deployment).

    Each tenant gets isolated rooms, agents, and channels.
    A default API key is automatically generated.

    **Note**: In production, protect this endpoint behind admin auth.
    """
    # Check slug uniqueness
    existing = await db.execute(select(Tenant).where(Tenant.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant with slug '{body.slug}' already exists",
        )

    tenant = Tenant(name=body.name, slug=body.slug, email=body.email)
    db.add(tenant)
    await db.flush()  # get tenant.id before creating API key

    # Auto-generate a default API key
    default_key = ApiKey.generate(tenant.id, name="Default Key")
    db.add(default_key)

    return tenant


@router.get("/me", response_model=TenantResponse)
async def get_current_tenant(tenant: TenantDep):
    """
    Get the tenant associated with the current API key.

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    return tenant


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: uuid.UUID, db: DBDep):
    """Get a tenant by ID."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.post("/me/api-keys", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(body: CreateApiKeyRequest, tenant: TenantDep, db: DBDep):
    """
    Create a new API key for the authenticated tenant.

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    key = ApiKey.generate(tenant.id, name=body.name, test=body.test)
    db.add(key)
    return key


@router.get("/me/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(tenant: TenantDep, db: DBDep):
    """
    List all active API keys for the authenticated tenant.

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.tenant_id == tenant.id,
            ApiKey.is_active == True,  # noqa: E712
        )
    )
    return result.scalars().all()


@router.delete("/me/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(key_id: uuid.UUID, tenant: TenantDep, db: DBDep):
    """
    Revoke an API key.

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == tenant.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = False
