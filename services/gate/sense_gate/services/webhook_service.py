"""
Sense Gate — Webhook Service
Delivers signed event payloads to tenant-registered webhook endpoints.
Uses HMAC-SHA256 signatures so tenants can verify authenticity.
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx

from sense_gate.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def sign_payload(secret: str, payload: bytes) -> str:
    """Generate HMAC-SHA256 signature for a webhook payload."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


async def deliver_webhook(
    url: str,
    secret: str,
    event_type: str,
    data: dict[str, Any],
    retry: int = 0,
) -> bool:
    """
    Deliver a signed webhook POST to a tenant endpoint.

    Payload shape:
        {
            "event": "room.participant_joined",
            "timestamp": 1712345678,
            "data": { ... }
        }

    Headers:
        X-Sense-Signature: sha256=<hmac>
        X-Sense-Event: room.participant_joined
        X-Sense-Timestamp: 1712345678

    Returns:
        True if delivered successfully, False otherwise.
    """
    timestamp = int(time.time())
    body = json.dumps({
        "event": event_type,
        "timestamp": timestamp,
        "data": data,
    }).encode()

    signature = sign_payload(secret, body)

    headers = {
        "Content-Type": "application/json",
        "X-Sense-Signature": f"sha256={signature}",
        "X-Sense-Event": event_type,
        "X-Sense-Timestamp": str(timestamp),
    }

    try:
        async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
            resp = await client.post(url, content=body, headers=headers)
            if resp.status_code < 300:
                logger.info("Webhook delivered — event=%s url=%s", event_type, url)
                return True
            else:
                logger.warning(
                    "Webhook failed — event=%s url=%s status=%d",
                    event_type, url, resp.status_code,
                )
                return False
    except Exception as e:
        logger.error("Webhook delivery error — url=%s error=%s", url, e)
        return False


# ── Well-known event types ────────────────────────────────────────────────────

class WebhookEvents:
    ROOM_CREATED = "room.created"
    ROOM_ENDED = "room.ended"
    PARTICIPANT_JOINED = "room.participant_joined"
    PARTICIPANT_LEFT = "room.participant_left"
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    LENS_EVENT = "lens.event"
    CALL_ESCALATED = "call.escalated"
