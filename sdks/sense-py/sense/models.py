"""
Sense Platform — Python SDK Models
====================================
Pydantic models for all Sense Gate + Sense Wire API responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ── Gate models ───────────────────────────────────────────────────────────────

@dataclass
class Tenant:
    id: str
    name: str
    slug: str
    plan: str
    is_active: bool = True


@dataclass
class ApiKey:
    id: str
    tenant_id: str
    name: str
    key: str                      # Only present on creation
    is_test: bool = False
    created_at: str = ""


@dataclass
class Room:
    id: str
    tenant_id: str
    name: str
    active_participants: int = 0
    created_at: str = ""


@dataclass
class RelayToken:
    """LiveKit access token for a client joining a room."""
    relay_url: str
    relay_token: str
    room_name: str                # Namespaced: {tenant_slug}__{room_id}


@dataclass
class AgentStatus:
    room: str
    status: str                   # "running" | "stopped" | "not_found"
    llm: str = ""
    lenses: list[str] = field(default_factory=list)
    uptime_seconds: float = 0.0


@dataclass
class LensInfo:
    name: str
    throttle_seconds: float
    available: bool


@dataclass
class Webhook:
    id: str
    tenant_id: str
    url: str
    events: list[str] = field(default_factory=list)
    is_active: bool = True
    created_at: str = ""


@dataclass
class UsageSummary:
    tenant_id: str
    period_start: str
    period_end: str
    total_calls: int = 0
    total_minutes: float = 0.0
    total_participants: int = 0
    by_type: dict[str, int] = field(default_factory=dict)


# ── Wire models ───────────────────────────────────────────────────────────────

@dataclass
class Message:
    id: str
    channel_id: str
    tenant_id: str
    user_id: str
    text: str
    created_at: str
    is_deleted: bool = False
    reactions: list["Reaction"] = field(default_factory=list)


@dataclass
class Reaction:
    id: str
    message_id: str
    user_id: str
    emoji: str
    created_at: str = ""


@dataclass
class TypingEvent:
    channel_type: str
    channel_id: str
    user_id: str
    is_typing: bool


# ── Vision Lens event models ──────────────────────────────────────────────────

@dataclass
class LensEvent:
    """
    A vision intelligence event pushed from Sense Mind via Sense Wire.
    Received by LensStream subscribers.
    """
    lens_name: str                # "mood_lens" | "pose_lens" | "guard_lens" | "face_lens"
    confidence: float
    context_text: str             # Human-readable LLM context string
    timestamp: float
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class MoodEvent(LensEvent):
    """MoodLens detection result."""
    mood: str = ""                # "happy" | "neutral" | "frustrated" | "angry" | etc.
    valence: float = 0.0          # -1.0 (negative) to 1.0 (positive)

    @classmethod
    def from_lens_event(cls, event: LensEvent) -> "MoodEvent":
        return cls(
            lens_name=event.lens_name,
            confidence=event.confidence,
            context_text=event.context_text,
            timestamp=event.timestamp,
            data=event.data,
            mood=event.data.get("mood", ""),
            valence=float(event.data.get("valence", 0.0)),
        )


@dataclass
class PoseEvent(LensEvent):
    """PoseLens detection result."""
    keypoints: list[dict] = field(default_factory=list)
    posture: str = ""             # "good" | "slouching" | "leaning" | etc.

    @classmethod
    def from_lens_event(cls, event: LensEvent) -> "PoseEvent":
        return cls(
            lens_name=event.lens_name,
            confidence=event.confidence,
            context_text=event.context_text,
            timestamp=event.timestamp,
            data=event.data,
            keypoints=event.data.get("keypoints", []),
            posture=event.data.get("posture", ""),
        )


@dataclass
class GuardEvent(LensEvent):
    """GuardLens detection result."""
    violation: bool = False
    violation_type: str = ""      # "nudity" | "violence" | "weapon" | etc.
    action_taken: str = ""        # "flagged" | "blocked"

    @classmethod
    def from_lens_event(cls, event: LensEvent) -> "GuardEvent":
        return cls(
            lens_name=event.lens_name,
            confidence=event.confidence,
            context_text=event.context_text,
            timestamp=event.timestamp,
            data=event.data,
            violation=bool(event.data.get("violation", False)),
            violation_type=event.data.get("violation_type", ""),
            action_taken=event.data.get("action_taken", ""),
        )


@dataclass
class FaceEvent(LensEvent):
    """FaceLens detection result."""
    count: int = 0                # Number of faces detected
    identities: list[str] = field(default_factory=list)

    @classmethod
    def from_lens_event(cls, event: LensEvent) -> "FaceEvent":
        return cls(
            lens_name=event.lens_name,
            confidence=event.confidence,
            context_text=event.context_text,
            timestamp=event.timestamp,
            data=event.data,
            count=int(event.data.get("count", 0)),
            identities=event.data.get("identities", []),
        )
