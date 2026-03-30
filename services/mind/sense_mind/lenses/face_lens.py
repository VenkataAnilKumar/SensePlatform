"""
FaceLens — Face Detection & Presence Monitoring
Detects faces, counts occupants, and tracks presence changes in video frames.
Designed for security SOC, access control, and telehealth identity verification.
"""

import logging
import time
from typing import Optional

from .base_lens import BaseLens, LensEvent

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.50
ABSENCE_TIMEOUT = 10.0   # seconds before "person left" event fires


class FaceLens(BaseLens):
    """
    Real-time face detection and occupancy tracking.

    Detects faces in video frames, tracks how many people are present,
    and fires events on presence changes (arrival, departure, multiple faces).

    Useful for:
      - Security camera SOC monitoring
      - Telehealth identity verification (one patient per session)
      - Contact center — detect if customer stepped away

    Emits LensEvents with:
        data["face_count"]      — number of faces detected
        data["event_type"]      — "presence_change" | "multiple_faces" | "no_face" | "face_detected"
        data["faces"]           — list of face bounding boxes [{x1,y1,x2,y2,conf}]
        data["occupancy"]       — current occupancy count
        context_text            — situational summary for LLM

    Args:
        model_path:        Path to YOLO face/detection model (e.g., yolov8n-face.pt or yolov8n.pt)
        max_occupancy:     Alert if more than this many faces detected (default: 1 for 1:1 sessions)
        throttle_seconds:  Minimum seconds between routine events (default: 5s)
        alert_on_absence:  Fire event if no face detected for `absence_timeout` seconds
        absence_timeout:   Seconds of no-face before firing absence event (default: 10s)
    """

    name: str = "face_lens"
    throttle_seconds: float = 5.0

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        max_occupancy: int = 1,
        throttle_seconds: float = None,
        alert_on_absence: bool = True,
        absence_timeout: float = ABSENCE_TIMEOUT,
    ):
        self._model_path = model_path
        self._max_occupancy = max_occupancy
        self._alert_on_absence = alert_on_absence
        self._absence_timeout = absence_timeout
        self._model = None
        self._class_names: dict = {}
        self._prev_face_count: int = 0
        self._last_face_seen: float = time.time()
        self._absence_alerted: bool = False
        super().__init__(throttle_seconds=throttle_seconds)

    def _setup(self):
        try:
            from ultralytics import YOLO
            self._model = YOLO(self._model_path)
            if hasattr(self._model, "names"):
                self._class_names = self._model.names
            self._available = True
            logger.info("FaceLens ready — model: %s | max_occupancy: %d", self._model_path, self._max_occupancy)
        except ImportError:
            logger.warning("FaceLens: ultralytics not installed — pip install ultralytics")
            self._available = False
        except Exception as e:
            logger.warning("FaceLens: model load failed — %s", e)
            self._available = False

    def process_frame(self, frame) -> Optional[LensEvent]:
        """
        Detect faces in a video frame and track presence changes.

        Args:
            frame: PIL Image or numpy array

        Returns:
            LensEvent on presence change or policy violation, None otherwise.
        """
        if not self._available or self._model is None:
            return None

        try:
            results = self._model(frame, verbose=False)
            faces = self._detect_faces(results)
            face_count = len(faces)

            now = time.time()
            if face_count > 0:
                self._last_face_seen = now
                self._absence_alerted = False

            event = self._evaluate_presence(faces, face_count, now)
            self._prev_face_count = face_count

            if event:
                self._emit(event)
                return event

            return None

        except Exception as e:
            logger.debug("FaceLens.process_frame error: %s", e)
            return None

    def _detect_faces(self, results) -> list:
        """Extract face/person detections from YOLO results."""
        faces = []

        if not results or len(results) == 0:
            return faces

        result = results[0]

        if result.boxes is None:
            return faces

        try:
            for box in result.boxes:
                conf = float(box.conf[0])
                if conf < MIN_CONFIDENCE:
                    continue

                cls_id = int(box.cls[0])
                class_name = self._class_names.get(cls_id, "").lower()

                # Accept "person" from COCO, or any face-specific model output
                if class_name in ("person", "face"):
                    xyxy = box.xyxy[0].cpu().numpy()
                    faces.append({
                        "x1": float(xyxy[0]),
                        "y1": float(xyxy[1]),
                        "x2": float(xyxy[2]),
                        "y2": float(xyxy[3]),
                        "conf": conf,
                    })
        except Exception as e:
            logger.debug("FaceLens._detect_faces error: %s", e)

        return faces

    def _evaluate_presence(self, faces: list, face_count: int, now: float) -> Optional[LensEvent]:
        """Determine if a LensEvent should be fired based on presence changes."""

        # Presence arrived
        if self._prev_face_count == 0 and face_count > 0:
            return self._make_event("face_detected", faces, face_count)

        # Presence departed
        if self._prev_face_count > 0 and face_count == 0:
            return self._make_event("no_face", faces, face_count)

        # Max occupancy exceeded
        if face_count > self._max_occupancy:
            return self._make_event("multiple_faces", faces, face_count)

        # Absence timeout
        if (
            self._alert_on_absence
            and face_count == 0
            and not self._absence_alerted
            and (now - self._last_face_seen) > self._absence_timeout
        ):
            self._absence_alerted = True
            return self._make_event("prolonged_absence", faces, face_count)

        return None

    def _make_event(self, event_type: str, faces: list, face_count: int) -> LensEvent:
        return LensEvent(
            lens_name=self.name,
            data={
                "event_type": event_type,
                "face_count": face_count,
                "occupancy": face_count,
                "faces": faces,
                "max_occupancy": self._max_occupancy,
            },
            confidence=max((f["conf"] for f in faces), default=1.0),
            context_text=self._build_context(event_type, face_count),
        )

    def _build_context(self, event_type: str, face_count: int) -> str:
        if event_type == "face_detected":
            return f"Person detected in frame (count: {face_count}). Session participant is present."
        if event_type == "no_face":
            return "No person detected in frame. Participant may have stepped away."
        if event_type == "multiple_faces":
            return (
                f"Multiple people detected ({face_count}). "
                f"Policy allows {self._max_occupancy}. Verify session participant identity."
            )
        if event_type == "prolonged_absence":
            return (
                f"No face detected for over {self._absence_timeout:.0f} seconds. "
                "Consider pausing the session or checking in with the participant."
            )
        return f"Face presence event: {event_type}. Faces: {face_count}."
