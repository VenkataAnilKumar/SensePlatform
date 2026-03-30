"""
Sense Platform — AI Contact Center Agent
=========================================
A complete contact center AI agent that:
  - Joins a Sense Relay room (self-hosted WebRTC, no cloud)
  - Speaks and listens to customers in real-time
  - Watches the customer's mood via MoodLens (YOLO emotion detection)
  - Adapts its tone when frustration or escalation is detected
  - Flags escalations to a supervisor via a tool call

Run locally:
    ANTHROPIC_API_KEY=sk-... python examples/contact_center/agent.py

Run via Docker:
    docker compose up

Environment variables:
    ANTHROPIC_API_KEY   — required
    DEEPGRAM_API_KEY    — optional (STT, falls back to silence)
    ELEVENLABS_API_KEY  — optional (TTS, falls back to silence)
    SENSE_RELAY_URL     — default ws://localhost:7880
    SENSE_ROOM          — default "contact-center"
"""

import logging
import os

from sense_mind import SenseMind, SenseRunner

# Import LLM / STT / TTS plugins
from sense_mind.plugins import anthropic

# Optional STT / TTS — graceful fallback if keys not set
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

# Vision lens — MoodLens watches customer emotion
try:
    from sense_mind.lenses import MoodLens
    _lenses = [MoodLens(throttle_seconds=4.0)]
except Exception:
    _lenses = []

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

INSTRUCTIONS = """
You are Alex, a professional and empathetic AI contact center agent for Sense Platform.

Your job is to help customers with their questions quickly and effectively.

Vision context will be injected automatically when mood changes are detected:
  - If the customer appears frustrated → acknowledge their frustration, stay calm and solution-focused
  - If the customer appears confused → simplify your language and offer step-by-step guidance
  - If escalation is detected → offer to connect them with a human supervisor

Tools available:
  - escalate_to_supervisor(reason): Transfer to a human agent with a brief handoff summary

Always be concise. Never speak for more than 3 sentences without pausing for the customer's response.
""".strip()


def main():
    room = os.environ.get("SENSE_ROOM", "contact-center")

    agent = SenseMind(
        relay_url=os.environ.get("SENSE_RELAY_URL", "ws://localhost:7880"),
        instructions=INSTRUCTIONS,
        llm=anthropic.LLM(
            model="claude-sonnet-4-6",
            temperature=0.7,
        ),
        stt=_stt,
        tts=_tts,
        lenses=_lenses,
        agent_id="sense-agent-cc",
        agent_name="Alex (Sense AI)",
    )

    logger.info("Starting contact center agent — room: %s", room)
    SenseRunner(agent, room=room, port=8080).serve()


if __name__ == "__main__":
    main()
