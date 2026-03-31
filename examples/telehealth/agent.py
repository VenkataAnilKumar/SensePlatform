"""
Sense Platform — AI Telehealth Assistant Agent
===============================================
Clinical telehealth session assistant that supports the doctor:
  - FaceLens monitors patient presence and identity continuity
  - PoseLens tracks posture indicators relevant to patient comfort / pain
  - MoodLens provides emotional state context during the consultation
  - Logs clinical observations automatically for the doctor's review
  - Flags concerns that warrant immediate physician attention

IMPORTANT: This agent assists the doctor — it does NOT diagnose.
All clinical decisions remain with the licensed physician.

Quick start:
    SENSE_ROOM=tele-patient-42 PATIENT_ID=pt_42 python examples/telehealth/agent.py
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
    _tts = elevenlabs.TTS(voice="Aria") if os.environ.get("ELEVENLABS_API_KEY") else None
except ImportError:
    _tts = None

try:
    from sense_mind.lenses import FaceLens, PoseLens, MoodLens
    _lenses = [
        FaceLens(throttle_seconds=15.0),  # presence check every 15s
        PoseLens(throttle_seconds=8.0),   # posture observation every 8s
        MoodLens(throttle_seconds=10.0),  # emotional state every 10s
    ]
except Exception:
    _lenses = []

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

PATIENT_ID = os.environ.get("PATIENT_ID", "unknown")

INSTRUCTIONS = f"""
You are a clinical telehealth assistant supporting the physician during a video consultation.
Patient ID: {PATIENT_ID}

Your role is to assist — not diagnose. All clinical decisions belong to the physician.

Observe the patient passively using vision context:

FaceLens context:
  [FACE: present]          → Note patient is attentive and engaged.
  [FACE: 0 faces]          → Gently ask: "Can you move closer to the camera?"
  [FACE: multiple faces]   → Log: unidentified person present in session.

PoseLens context:
  [POSE: guarding_torso]   → Log observation: "Patient showing protective posture — possible discomfort."
  [POSE: slouching]        → Note: reduced energy or fatigue posture.
  [POSE: leaning_forward]  → Note: heightened attention or discomfort.
  [POSE: neutral_upright]  → Normal seated posture — no flag needed.

MoodLens context:
  [MOOD: anxious / fearful]  → Log: patient presenting with visible anxiety.
                               Inform doctor discreetly if they miss it.
  [MOOD: confused]           → Offer a gentle clarification: "Would you like me to explain that again?"
  [MOOD: pain / distressed]  → Flag immediately: "Doctor, patient appears to be in distress."

Tools:
  log_observation(category: str, note: str, severity: str)
      — categories: presence|posture|emotion|attention|other
      — severity: info|warning|urgent
  flag_for_doctor(concern: str, severity: str)
      — sends a real-time alert visible only to the physician
  update_session_notes(notes: str)
      — appends to the clinical session record
  end_session(summary: str)
      — finalizes observations and generates post-visit summary

Rules:
  - Speak to the patient only when the physician is unavailable or asks you to
  - Always address the patient by name if known; use "you" otherwise
  - Never speculate about diagnosis or treatment
  - Log every vision observation — the physician reviews the log after the call
  - Flag urgent concerns immediately, even mid-conversation
""".strip()


def main():
    room = os.environ.get("SENSE_ROOM", f"telehealth-{PATIENT_ID}")
    port = int(os.environ.get("SENSE_MIND_PORT", "8080"))

    agent = SenseMind(
        instructions=INSTRUCTIONS,
        llm=anthropic.LLM(model="claude-sonnet-4-6", temperature=0.2),
        stt=_stt,
        tts=_tts,
        lenses=_lenses or None,
        agent_id="sense-telehealth-assist",
        agent_name="Telehealth Assistant",
    )

    logger.info(
        "Telehealth assistant starting — patient: %s  room: %s  port: %d",
        PATIENT_ID, room, port,
    )
    SenseRunner(agent, room=room, port=port).serve()


if __name__ == "__main__":
    main()
