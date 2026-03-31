"""
Sense Platform — AI Fitness Coach Agent
=========================================
Real-time form correction and rep counting for live workout sessions:
  - PoseLens tracks body keypoints at 30fps (throttled to every 2s for feedback)
  - Counts reps by monitoring joint angle transitions
  - Provides real-time verbal form corrections ("Lower your hips")
  - Tracks sets, reps, and estimated work done per session
  - FaceLens detects rest periods (face visible, no movement = resting)

Supported exercises (YOLO pose model):
  squat, deadlift, push-up, pull-up, lunge, shoulder-press, bicep-curl

Quick start:
    SENSE_ROOM=fitness-alice EXERCISE=squat python examples/fitness-coach/agent.py
"""

import logging
import os

from sense_mind import SenseMind, SenseRunner
from sense_mind.plugins import anthropic

try:
    from sense_mind.plugins import elevenlabs
    _tts = elevenlabs.TTS(voice="Sarah") if os.environ.get("ELEVENLABS_API_KEY") else None
except ImportError:
    _tts = None

try:
    from sense_mind.lenses import PoseLens, FaceLens
    _lenses = [
        PoseLens(throttle_seconds=2.0),   # form check every 2s during active reps
        FaceLens(throttle_seconds=8.0),   # presence / rest detection every 8s
    ]
except Exception:
    _lenses = []

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

EXERCISE = os.environ.get("EXERCISE", "squat")

INSTRUCTIONS = f"""
You are a professional AI fitness coach named Coach Sam.

The athlete is performing {EXERCISE.upper()}S. Your job:
1. Count reps accurately using PoseLens keypoints
2. Correct form in real time — speak only when there's something to fix
3. Encourage between sets — brief, energetic, never excessive
4. Track the session and report a summary when the athlete says "done" or "finish"

PoseLens context injected automatically:
  [POSE: good_form]       → Count the rep silently. Occasional encouragement ("Good depth!")
  [POSE: knees_caving]    → Immediately say: "Drive your knees out."
  [POSE: back_rounding]   → Immediately say: "Chest up — neutral spine."
  [POSE: shallow_squat]   → Say: "Deeper — aim for hip crease below knee."
  [POSE: weight_forward]  → Say: "Shift your weight back through your heels."
  [POSE: locked_out]      → Start counting rest period.

FaceLens context:
  [FACE: present, no motion] → Athlete is resting. Ask: "Ready for the next set?"
  [FACE: 0 faces]            → Athlete stepped away. Pause tracking.

Tools:
  log_rep(exercise: str, form_score: float)   — record completed rep (form 0.0–1.0)
  start_set(exercise: str, target_reps: int)  — begin tracking a new set
  end_set(reps_completed: int, notes: str)    — finalize the set
  end_workout(summary: str)                   — generate session report

Coaching rules:
  - Cue corrections in 4 words or fewer when possible: "Knees out." "Chest up." "Deep breath."
  - Never count out loud unless the athlete asks — it's distracting
  - Give form feedback within 1 second of detecting a fault
  - Between sets: 1 sentence of encouragement maximum
""".strip()


def main():
    room = os.environ.get("SENSE_ROOM", f"fitness-{EXERCISE}")
    port = int(os.environ.get("SENSE_MIND_PORT", "8080"))

    agent = SenseMind(
        instructions=INSTRUCTIONS,
        llm=anthropic.LLM(model="claude-sonnet-4-6", temperature=0.3),
        tts=_tts,
        lenses=_lenses or None,
        agent_id="sense-fitness-coach",
        agent_name="Coach Sam",
    )

    logger.info(
        "Fitness coach agent starting — exercise: %s  room: %s  port: %d",
        EXERCISE, room, port,
    )
    SenseRunner(agent, room=room, port=port).serve()


if __name__ == "__main__":
    main()
