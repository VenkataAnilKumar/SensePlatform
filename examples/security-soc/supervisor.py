"""
Security SOC — Multi-Zone Python Supervisor
=============================================
Uses the sense-py SDK to monitor multiple security zones simultaneously.
Receives GuardLens and FaceLens events from all zones via Sense Wire
and dispatches alerts to the security team.

Usage:
    pip install sense-platform
    SENSE_API_KEY=sk_live_... python examples/security-soc/supervisor.py
"""

import asyncio
import logging
import os

from sense import SenseClient, SenseWire, LensStream, GuardEvent, FaceEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger("soc-supervisor")

GATE_URL = os.environ.get("SENSE_GATE_URL", "http://localhost:3000")
WIRE_URL = os.environ.get("SENSE_WIRE_URL", "ws://localhost:3001")
API_KEY  = os.environ.get("SENSE_API_KEY", "")

CRITICAL_GUARD_TYPES = {"weapon", "fire", "smoke", "device_tampering"}
HIGH_GUARD_TYPES     = {"explicit_content", "tailgating"}


async def monitor_zone(client: SenseClient, room_id: str) -> None:
    """Open a Wire connection for one security zone and subscribe to lens events."""
    async with SenseWire(client, channel_type="lens", channel_id=room_id) as wire:
        stream = LensStream(wire)

        @stream.on_guard
        async def on_guard(event: GuardEvent):
            if not event.violation:
                return
            severity = "CRITICAL" if event.violation_type in CRITICAL_GUARD_TYPES else "HIGH"
            log.warning(
                "[%s] GuardEvent — type=%s severity=%s confidence=%.2f",
                room_id, event.violation_type, severity, event.confidence,
            )
            if severity == "CRITICAL":
                log.error("CRITICAL THREAT in %s — dispatching guard + locking zone", room_id)
                # In production: call access control API here

        @stream.on_face
        def on_face(event: FaceEvent):
            log.info("[%s] Occupancy: %d face(s) detected", room_id, event.count)
            if event.count > 5:
                log.warning("[%s] HIGH occupancy: %d people", room_id, event.count)

        log.info("Monitoring zone: %s", room_id)
        await wire.wait()


async def main() -> None:
    async with SenseClient(api_key=API_KEY, gate_url=GATE_URL) as client:
        await client.connect()
        log.info("SOC supervisor connected — tenant: %s", client.tenant.slug)

        rooms = await client.rooms.list()
        security_rooms = [r for r in rooms if r.name.startswith("security-")]
        log.info("Found %d security zone(s): %s", len(security_rooms), [r.id for r in security_rooms])

        if not security_rooms:
            log.warning("No active security zones found. Start some agents first.")
            return

        await asyncio.gather(*[
            monitor_zone(client, room.id)
            for room in security_rooms
        ])


if __name__ == "__main__":
    asyncio.run(main())
