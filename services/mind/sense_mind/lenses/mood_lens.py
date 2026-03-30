"""
MoodLens — Customer Emotion Detection
Detects emotional states (frustrated, confused, satisfied, neutral) from video frames.
Useful for contact center agents to adapt their response style in real time.
"""

import logging
from typing import Optional

from .base_lens import BaseLens, LensEvent

logger = logging.getLogger(__name__)

# Emotion labels mapped from YOLO pose/facial heuristics
MOOD_LABELS = ["neutral", "satisfied", "confused", "frustrated", "escalating"]

# Confidence thresholds
MIN_CONFIDENCE = 0.45


class MoodLens(BaseLens):
    """
    Detect customer emotional state from video frames.

    Uses a lightweight YOLO model to estimate facial/body cues and classify
    mood into actionable states for contact center AI agents.

    Emits LensEvents with:
        data["mood"]        — detected emotion label
        data["confidence"]  — model confidence score
        data["escalation"]  — bool, True if escalation risk detected
        context_text        — human-readable summary for LLM injection

    Args:
        model_path:       Path to YOLO model weights (.pt file)
        throttle_seconds: Minimum seconds between emitted events (default: 3s)
        escalation_mood:  Mood label that triggers escalation flag (default: "frustrated")
    """

    name: str = "mood_lens"
    throttle_seconds: float = 3.0

    def __init__(
        self,
        model_path: str = "yolov8n-pose.pt",
        throttle_seconds: float = None,
        escalation_mood: str = "frustrated",
    ):
        self._model_path = model_path
        self._escalation_mood = escalation_mood
        self._model = None
        super().__init__(throttle_seconds=throttle_seconds)

    def _setup(self):
        """Load YOLO model. Marks unavailable if import or load fails."""
        try:
            from ultralytics import YOLO
            self._model = YOLO(self._model_path)
            self._available = True
            logger.info("MoodLens ready — model: %s", self._model_path)
        except ImportError:
            logger.warning("MoodLens: ultralytics not installed — pip install ultralytics")
            self._available = False
        except Exception as e:
            logger.warning("MoodLens: model load failed — %s", e)
            self._available = False

    def process_frame(self, frame) -> Optional[LensEvent]:
        """
        Analyze a video frame for emotional cues.

        Args:
            frame: PIL Image or numpy array (BGR or RGB)

        Returns:
            LensEvent with mood data, or None if not confident / throttled.
        """
        if not self._available or self._model is None:
            return None

        try:
            results = self._model(frame, verbose=False)
            mood, confidence = self._classify_mood(results)

            if confidence < MIN_CONFIDENCE:
                return None

            escalation = mood == self._escalation_mood
            event = LensEvent(
                lens_name=self.name,
                data={
                    "mood": mood,
                    "confidence": round(confidence, 3),
                    "escalation": escalation,
                },
                confidence=confidence,
                context_text=self._build_context(mood, confidence, escalation),
            )
            self._emit(event)
            return event

        except Exception as e:
            logger.debug("MoodLens.process_frame error: %s", e)
            return None

    def _classify_mood(self, results) -> tuple[str, float]:
        """
        Derive mood from YOLO keypoint heuristics.

        Pose-based signals used:
          - Shoulder elevation (frustration/tension)
          - Head tilt angle (confusion)
          - Body language symmetry (satisfaction)

        Returns (mood_label, confidence).
        """
        if not results or len(results) == 0:
            return "neutral", 0.0

        result = results[0]

        # Use detection confidence as base
        if result.boxes is not None and len(result.boxes) > 0:
            base_confidence = float(result.boxes.conf[0])
        else:
            return "neutral", 0.0

        if base_confidence < MIN_CONFIDENCE:
            return "neutral", base_confidence

        # Pose keypoint heuristics (requires pose model)
        if result.keypoints is not None and len(result.keypoints) > 0:
            mood = self._pose_to_mood(result.keypoints[0])
        else:
            mood = "neutral"

        return mood, base_confidence

    def _pose_to_mood(self, keypoints) -> str:
        """Map pose keypoints to a mood label using simple heuristics."""
        try:
            kp = keypoints.xy[0].cpu().numpy()  # shape: [17, 2]

            # Keypoint indices (COCO format):
            # 0=nose, 1=left_eye, 2=right_eye, 5=left_shoulder, 6=right_shoulder
            # 11=left_hip, 12=right_hip

            if len(kp) < 13:
                return "neutral"

            left_shoulder_y = kp[5][1]
            right_shoulder_y = kp[6][1]
            nose_y = kp[0][1]
            left_shoulder_x = kp[5][0]
            right_shoulder_x = kp[6][0]

            # Raised shoulders = tension/frustration
            shoulder_midpoint_y = (left_shoulder_y + right_shoulder_y) / 2
            if nose_y > 0 and shoulder_midpoint_y > 0:
                neck_ratio = (shoulder_midpoint_y - nose_y) / max(shoulder_midpoint_y, 1)
                if neck_ratio < 0.15:
                    return "frustrated"

            # Asymmetric shoulders = confusion / head tilt
            shoulder_diff = abs(left_shoulder_y - right_shoulder_y)
            shoulder_width = abs(left_shoulder_x - right_shoulder_x)
            if shoulder_width > 0 and shoulder_diff / shoulder_width > 0.2:
                return "confused"

            return "satisfied"

        except Exception:
            return "neutral"

    def _build_context(self, mood: str, confidence: float, escalation: bool) -> str:
        ctx = f"Customer appears {mood} (confidence: {confidence:.0%})."
        if escalation:
            ctx += " Escalation risk detected — consider empathetic response or supervisor handoff."
        elif mood == "confused":
            ctx += " Customer may need clarification or simpler explanation."
        elif mood == "satisfied":
            ctx += " Customer engagement is positive."
        return ctx
