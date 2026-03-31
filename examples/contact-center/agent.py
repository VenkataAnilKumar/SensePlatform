"""
Sense Platform — AI Contact Center Agent (Phase 8)
====================================================
Emotion-aware contact center agent:
  - Joins a Sense Relay room (self-hosted WebRTC)
  - Speaks and listens to customers in real time
  - MoodLens detects frustration / confusion / satisfaction
  - FaceLens monitors customer presence
  - Adapts tone automatically via LensEvent.context_text injection
  - escalate_to_supervisor() tool triggers human handoff

Quick start:
    cp .env.example .env         # fill ANTHROPIC_API_KEY
    docker compose up            # start platform
    python examples/contact-center/agent.py  # run agent
"""

import logging
import os

from sense_mind import SenseMind, SenseRunner
from sense_mind.plugins import anthropic

try:
    from sense_mind.plugins import deepgram
    _stt = deepgram.STT() if os.environ.get("DEEPGRAM_API_KEY") else None
except ImportError:
    _stt = None

try:
    from sense_mind.plugins import elevenlabs
    _tts = elevenlabs.TTS() if os.environ.get("ELEVENLABS_API_KEY") else None
except ImportError:
    _tts = None

try:
    from sense_mind.lenses import MoodLens, FaceLens
    _lenses = [
        MoodLens(throttle_seconds=3.0),   # emotion context injected every 3s
        FaceLens(throttle_seconds=10.0),  # presence check every 10s
    ]
except Exception:
    _lenses = []

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

INSTRUCTIONS = """
You are Alex, a professional AI contact center agent.

Your goal: resolve the customer's issue as quickly as possible.

Emotional context is injected automatically from MoodLens:
  [MOOD: frustrated] → Pause. Acknowledge: "I completely understand your frustration."
                       Then pivot to a concrete next step.
  [MOOD: confused]   → Slow down. Say "Let me walk you through this step by step."
  [MOOD: satisfied]  → Confirm resolution and ask if there's anything else.

Presence context from FaceLens:
  [FACE: 0 faces detected] → Pause and say "Are you still there?"

Tools:
  escalate_to_supervisor(reason: str) — hand off to a human. Use when:
    - Customer explicitly asks for a human
    - You cannot resolve the issue after 2 attempts
    - Mood stays frustrated for 60+ seconds

Rules:
  - Never speak more than 3 sentences before pausing
  - Never promise what you cannot deliver
  - Always confirm the customer's issue in your own words before solving it
""".strip()


def main():
    room = os.environ.get("SENSE_ROOM", "contact-center")
    port = int(os.environ.get("SENSE_MIND_PORT", "8080"))

    agent = SenseMind(
        instructions=INSTRUCTIONS,
        llm=anthropic.LLM(model="claude-sonnet-4-6", temperature=0.6),
        stt=_stt,
        tts=_tts,
        lenses=_lenses or None,
        agent_id="sense-agent-cc",
        agent_name="Alex (Sense AI)",
    )

    logger.info("Contact center agent starting — room: %s  port: %d", room, port)
    SenseRunner(agent, room=room, port=port).serve()


if __name__ == "__main__":
    main()
