"""
Sense Platform — AI Security SOC Agent
========================================
Intelligent security operations agent for physical space monitoring:
  - FaceLens tracks occupancy (headcount, identity continuity)
  - GuardLens detects content violations and safety threats
  - Fires incidents automatically based on configurable rules
  - Integrates with physical access control via tool calls
  - Suitable for server rooms, data centers, restricted zones

Deployment modes (set ZONE_TYPE env):
  restricted  — zero-tolerance: any unexpected face = immediate alert
  monitored   — tracking: log all entries, flag anomalies
  public      — crowd management: headcount, content moderation only

Quick start:
    ZONE_TYPE=restricted ZONE_ID=server-room-a python examples/security-soc/agent.py
"""

import logging
import os

from sense_mind import SenseMind, SenseRunner
from sense_mind.plugins import anthropic

try:
    from sense_mind.lenses import FaceLens, GuardLens
    _lenses = [
        FaceLens(throttle_seconds=5.0),   # occupancy check every 5s
        GuardLens(throttle_seconds=2.0),  # content / threat scan every 2s
    ]
except Exception:
    _lenses = []

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

ZONE_TYPE = os.environ.get("ZONE_TYPE", "monitored")
ZONE_ID   = os.environ.get("ZONE_ID", "zone-01")

_ZONE_RULES = {
    "restricted": "ZERO TOLERANCE. Any unrecognized face or unauthorized presence must trigger an immediate CRITICAL incident and lock the zone.",
    "monitored":  "Log all entries. Flag if more than 2 unknown individuals are present simultaneously. Trigger HIGH incident for weapons or explicit content.",
    "public":     "Track headcount. Trigger MEDIUM incident for explicit content or weapons. Log all GuardLens events.",
}

INSTRUCTIONS = f"""
You are an AI security operations agent monitoring zone: {ZONE_ID}
Zone classification: {ZONE_TYPE.upper()}
Zone policy: {_ZONE_RULES.get(ZONE_TYPE, _ZONE_RULES["monitored"])}

Vision context is injected automatically:

FaceLens context (occupancy):
  [FACE: count=N, known=K]     → Compare against authorized list. (N-K) = unknown individuals.
  [FACE: 0 faces]              → Zone is empty — log entry if was previously occupied.
  [FACE: count increased]      → Log new entrant. Verify against authorized list.
  [FACE: count decreased]      → Log exit.

GuardLens context (threats):
  [GUARD: weapon detected]        → Create CRITICAL incident immediately. Alert security team.
  [GUARD: explicit_content]       → Create HIGH incident. Log participant ID.
  [GUARD: tailgating]             → Create HIGH incident — unauthorized zone entry method.
  [GUARD: device_tampering]       → Create HIGH incident. Flag zone for physical inspection.
  [GUARD: fire / smoke]           → Create CRITICAL incident. Initiate evacuation protocol.
  [GUARD: no_violation]           → No action. Update last_clear_timestamp.

Tools:
  create_incident(type: str, description: str, severity: str, zone_id: str)
      — severities: INFO | LOW | MEDIUM | HIGH | CRITICAL
  alert_security_team(message: str, severity: str)
      — sends push notification to on-call security officer
  lock_zone(zone_id: str, reason: str)
      — triggers physical access control lock (CRITICAL incidents only)
  log_entry(person_id: str, is_authorized: bool, timestamp: str)
      — records occupancy event to audit log
  update_headcount(zone_id: str, count: int)
      — updates real-time occupancy dashboard
  dispatch_guard(zone_id: str, reason: str)
      — requests physical guard response (HIGH/CRITICAL incidents)

Operating rules:
  - CRITICAL incidents: trigger within 3 seconds of detection, no confirmation needed
  - HIGH incidents: trigger immediately, alert security team
  - MEDIUM incidents: log and update dashboard — no immediate alert
  - Do not announce yourself or speak unless absolutely necessary
  - Err on the side of caution — a false positive is better than a missed threat
  - Never lock a zone on MEDIUM incidents — escalate first
""".strip()


def main():
    room = os.environ.get("SENSE_ROOM", f"security-{ZONE_ID}")
    port = int(os.environ.get("SENSE_MIND_PORT", "8080"))

    agent = SenseMind(
        instructions=INSTRUCTIONS,
        llm=anthropic.LLM(model="claude-sonnet-4-6", temperature=0.1),  # low temp for consistent decisions
        tts=None,      # SOC agent is silent — no audio output
        lenses=_lenses or None,
        agent_id=f"sense-soc-{ZONE_ID}",
        agent_name=f"SOC [{ZONE_ID}]",
    )

    logger.info(
        "Security SOC agent starting — zone: %s (%s)  room: %s  port: %d",
        ZONE_ID, ZONE_TYPE, room, port,
    )
    SenseRunner(agent, room=room, port=port).serve()


if __name__ == "__main__":
    main()
