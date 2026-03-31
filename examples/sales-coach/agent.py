"""
Sense Platform — AI Sales Coach Agent
=======================================
Real-time coaching whisper for live sales calls:
  - Watches the sales rep via PoseLens (engagement, confidence)
  - Watches the prospect via MoodLens (buying signals, objections)
  - Whispers coaching tips ONLY to the rep (silent to prospect)
  - Logs buying signals and deal stage transitions
  - Does NOT interrupt the call — acts as a silent advisor

Architecture:
    [Sales rep + prospect in room]
    ↓ video
    [SalesCoach agent — watches both feeds]
    ↓ coaching text
    [Rep-only channel in Sense Wire — coach writes, prospect never sees]

Quick start:
    SENSE_ROOM=sales-demo-001 python examples/sales-coach/agent.py
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
    from sense_mind.lenses import MoodLens, PoseLens
    _lenses = [
        MoodLens(throttle_seconds=4.0),   # prospect sentiment check every 4s
        PoseLens(throttle_seconds=3.0),   # rep posture / engagement every 3s
    ]
except Exception:
    _lenses = []

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

INSTRUCTIONS = """
You are a silent AI sales coach whispering to the sales representative during a live call.

The prospect CANNOT hear you. Speak only to the rep, briefly and actionably.

Observe the conversation and vision signals:

MoodLens context (prospect emotion):
  [MOOD: curious / happy]     → Buying signal. Whisper: "Good — lean in, ask about timeline."
  [MOOD: skeptical / neutral] → Whisper: "Address their doubts. Ask 'What concerns do you have?'"
  [MOOD: frustrated / bored]  → Whisper: "Energy dropping. Pivot with a compelling story or demo."
  [MOOD: excited]             → Whisper: "This is a closing moment. Ask for the commitment."

PoseLens context (rep body language):
  [POSE: slouching]           → Whisper: "Sit up — your confidence reads on camera."
  [POSE: arms_crossed]        → Whisper: "Open your posture — you appear defensive."
  [POSE: leaning_forward]     → Good signal — no action needed.

Tools:
  log_buying_signal(signal: str)          — record a prospect buying signal in the CRM
  suggest_objection_response(objection: str) — generate a reframe for a specific objection
  mark_deal_stage(stage: str)             — update deal stage: discovery|demo|proposal|close
  flag_coaching_moment(note: str)         — save a coaching note for post-call review

Coaching rules:
  - Keep whispers to 1 sentence. Rep is in the middle of a conversation.
  - Only whisper when there is something actionable. Silence is fine.
  - Never suggest scripts word-for-word — give the direction, not the line.
  - Log buying signals immediately when detected. They drive CRM updates.
""".strip()


def main():
    room = os.environ.get("SENSE_ROOM", "sales-demo")
    port = int(os.environ.get("SENSE_MIND_PORT", "8080"))

    agent = SenseMind(
        instructions=INSTRUCTIONS,
        llm=anthropic.LLM(model="claude-sonnet-4-6", temperature=0.4),
        stt=_stt,
        tts=None,           # Sales coach does NOT speak aloud — whispers via text channel
        lenses=_lenses or None,
        agent_id="sense-sales-coach",
        agent_name="SalesCoach (silent)",
    )

    logger.info("Sales coach agent starting — room: %s  port: %d", room, port)
    SenseRunner(agent, room=room, port=port).serve()


if __name__ == "__main__":
    main()
