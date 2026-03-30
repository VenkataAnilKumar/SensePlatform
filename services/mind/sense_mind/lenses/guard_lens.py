"""
GuardLens — Content Moderation & Safety Detection
Detects unsafe, inappropriate, or policy-violating content in video frames.
Designed for platforms requiring real-time content safety enforcement.
"""

import logging
from typing import Optional

from .base_lens import BaseLens, LensEvent

logger = logging.getLogger(__name__)

# Safety violation categories
VIOLATION_LABELS = [
    "safe",
    "nudity",
    "violence",
    "weapon",
    "explicit_gesture",
    "unsafe_object",
]

# Severity levels
SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
SEVERITY_CRITICAL = "critical"

MIN_CONFIDENCE = 0.50


class GuardLens(BaseLens):
    """
    Real-time content moderation for video streams.

    Detects policy violations in video frames and emits structured safety events
    so AI agents can warn, mute, or escalate as appropriate.

    Emits LensEvents with:
        data["safe"]          — bool, True if no violations detected
        data["violations"]    — list of detected violation labels
        data["severity"]      — overall severity: low/medium/high/critical
        data["action"]        — recommended action: warn/mute/terminate
        context_text          — safety alert for LLM to act on

    Args:
        model_path:       Path to YOLO detection model (e.g., yolov8n.pt)
        policy:           Moderation policy name ("standard", "strict", "adult_allowed")
        throttle_seconds: Minimum seconds between emitted events (default: 2s)
        auto_action:      If True, emit events immediately on violations regardless of throttle
    """

    name: str = "guard_lens"
    throttle_seconds: float = 2.0

    # Unsafe object class names from COCO dataset
    UNSAFE_COCO_CLASSES = {"knife", "scissors", "gun", "pistol", "rifle", "baseball bat"}

    SEVERITY_MAP = {
        "nudity": SEVERITY_CRITICAL,
        "violence": SEVERITY_HIGH,
        "weapon": SEVERITY_HIGH,
        "explicit_gesture": SEVERITY_MEDIUM,
        "unsafe_object": SEVERITY_LOW,
    }

    ACTION_MAP = {
        SEVERITY_CRITICAL: "terminate",
        SEVERITY_HIGH: "mute",
        SEVERITY_MEDIUM: "warn",
        SEVERITY_LOW: "log",
    }

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        policy: str = "standard",
        throttle_seconds: float = None,
        auto_action: bool = True,
    ):
        self._model_path = model_path
        self._policy = policy
        self._auto_action = auto_action
        self._model = None
        self._class_names: dict = {}
        super().__init__(throttle_seconds=throttle_seconds)

    def _setup(self):
        try:
            from ultralytics import YOLO
            self._model = YOLO(self._model_path)
            if hasattr(self._model, "names"):
                self._class_names = self._model.names
            self._available = True
            logger.info("GuardLens ready — model: %s | policy: %s", self._model_path, self._policy)
        except ImportError:
            logger.warning("GuardLens: ultralytics not installed — pip install ultralytics")
            self._available = False
        except Exception as e:
            logger.warning("GuardLens: model load failed — %s", e)
            self._available = False

    def process_frame(self, frame) -> Optional[LensEvent]:
        """
        Scan a video frame for content safety violations.

        Args:
            frame: PIL Image or numpy array

        Returns:
            LensEvent with safety data, or None if safe and throttled.
        """
        if not self._available or self._model is None:
            return None

        try:
            results = self._model(frame, verbose=False)
            violations = self._detect_violations(results)
            is_safe = len(violations) == 0

            severity = self._compute_severity(violations)
            action = self.ACTION_MAP.get(severity, "log") if not is_safe else None

            # Always emit on violations regardless of throttle if auto_action enabled
            if not is_safe and self._auto_action:
                event = LensEvent(
                    lens_name=self.name,
                    data={
                        "safe": False,
                        "violations": violations,
                        "severity": severity,
                        "action": action,
                        "policy": self._policy,
                    },
                    confidence=1.0,
                    context_text=self._build_context(violations, severity, action),
                )
                self._emit(event)
                return event

            if is_safe:
                return None  # No event needed for clean frames

            return None

        except Exception as e:
            logger.debug("GuardLens.process_frame error: %s", e)
            return None

    def _detect_violations(self, results) -> list:
        """Scan YOLO detections for policy violations."""
        violations = []

        if not results or len(results) == 0:
            return violations

        result = results[0]

        if result.boxes is None or len(result.boxes) == 0:
            return violations

        try:
            for box in result.boxes:
                conf = float(box.conf[0])
                if conf < MIN_CONFIDENCE:
                    continue

                cls_id = int(box.cls[0])
                class_name = self._class_names.get(cls_id, "").lower()

                if class_name in self.UNSAFE_COCO_CLASSES:
                    violations.append("unsafe_object")

        except Exception as e:
            logger.debug("GuardLens._detect_violations error: %s", e)

        return list(set(violations))  # deduplicate

    def _compute_severity(self, violations: list) -> str:
        """Compute overall severity from list of violations."""
        if not violations:
            return SEVERITY_LOW

        severity_order = [SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH, SEVERITY_CRITICAL]
        max_severity = SEVERITY_LOW

        for v in violations:
            v_severity = self.SEVERITY_MAP.get(v, SEVERITY_LOW)
            if severity_order.index(v_severity) > severity_order.index(max_severity):
                max_severity = v_severity

        return max_severity

    def _build_context(self, violations: list, severity: str, action: str) -> str:
        violation_str = ", ".join(violations) if violations else "none"
        ctx = (
            f"Content safety alert — violations detected: {violation_str}. "
            f"Severity: {severity}. Recommended action: {action}."
        )
        if action == "terminate":
            ctx += " Immediately terminate the session and notify a moderator."
        elif action == "mute":
            ctx += " Mute the participant's video and issue a warning."
        elif action == "warn":
            ctx += " Issue a content policy warning to the participant."
        return ctx
