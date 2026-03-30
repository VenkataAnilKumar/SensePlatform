"""
Sense Gate — Webhooks Router
Register, list, and delete webhook endpoints for a tenant.
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from sense_gate.deps import DBDep, TenantDep
from sense_gate.models.tenant import Webhook

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


class RegisterWebhookRequest(BaseModel):
    url: str
    events: str = "*"
    # e.g. "*" for all, or "room.created,agent.started,lens.event"


class WebhookResponse(BaseModel):
    id: uuid.UUID
    url: str
    events: str
    secret: str  # only shown on creation
    is_active: bool

    model_config = {"from_attributes": True}


class WebhookListItem(BaseModel):
    id: uuid.UUID
    url: str
    events: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def register_webhook(body: RegisterWebhookRequest, tenant: TenantDep, db: DBDep):
    """
    Register a webhook endpoint to receive Sense Platform events.

    Payloads are signed with HMAC-SHA256. Verify using the returned `secret`:
    ```
    X-Sense-Signature: sha256=<hmac>
    ```

    **Available events**:
    - `room.created` / `room.ended`
    - `room.participant_joined` / `room.participant_left`
    - `agent.started` / `agent.stopped`
    - `lens.event` — vision detection events (mood, pose, guard, face)
    - `call.escalated` — escalation trigger from MoodLens

    Set `events: "*"` to receive all events.

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    webhook = Webhook(
        tenant_id=tenant.id,
        url=str(body.url),
        events=body.events,
    )
    db.add(webhook)
    await db.flush()
    return webhook


@router.get("", response_model=list[WebhookListItem])
async def list_webhooks(tenant: TenantDep, db: DBDep):
    """
    List registered webhooks for this tenant.

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    result = await db.execute(
        select(Webhook).where(
            Webhook.tenant_id == tenant.id,
            Webhook.is_active == True,  # noqa: E712
        )
    )
    return result.scalars().all()


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(webhook_id: uuid.UUID, tenant: TenantDep, db: DBDep):
    """
    Delete (deactivate) a webhook.

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.tenant_id == tenant.id,
        )
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    webhook.is_active = False


@router.post("/{webhook_id}/test", status_code=status.HTTP_200_OK)
async def test_webhook(webhook_id: uuid.UUID, tenant: TenantDep, db: DBDep):
    """
    Send a test ping to a webhook endpoint to verify it's reachable.

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    from sense_gate.services.webhook_service import deliver_webhook

    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.tenant_id == tenant.id,
        )
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    delivered = await deliver_webhook(
        url=webhook.url,
        secret=webhook.secret,
        event_type="webhook.test",
        data={"message": "This is a test event from Sense Gate.", "tenant": tenant.slug},
    )

    return {"delivered": delivered, "url": webhook.url}
