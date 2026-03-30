"""
Sense Lenses — Vision Processing Pipeline
==========================================
Lenses analyze video frames in real-time and emit structured events
that the SenseMind agent uses for context-aware AI responses.

Available Lenses:
    MoodLens    — Detect customer emotion (frustrated, confused, satisfied)
    PoseLens    — Track body pose and movement (fitness, telehealth)
    GuardLens   — Content moderation and safety detection
    FaceLens    — Face detection and presence monitoring (security)
"""

from .mood_lens import MoodLens
from .pose_lens import PoseLens
from .guard_lens import GuardLens
from .face_lens import FaceLens

__all__ = ["MoodLens", "PoseLens", "GuardLens", "FaceLens"]
