"""
PoseLens — Body Pose & Movement Tracker
Tracks full-body pose keypoints and classifies movement quality.
Useful for fitness coaching, physical therapy, and telehealth sessions.
"""

import logging
from typing import Optional

from .base_lens import BaseLens, LensEvent

logger = logging.getLogger(__name__)

# Movement quality labels
POSE_STATES = ["unknown", "idle", "active", "incorrect_form", "correct_form", "at_risk"]

MIN_CONFIDENCE = 0.40


class PoseLens(BaseLens):
    """
    Track body pose and classify movement quality from video frames.

    Designed for fitness coaching and telehealth use cases where the AI agent
    needs real-time feedback on the user's physical form and activity level.

    Emits LensEvents with:
        data["pose_state"]      — movement quality label
        data["keypoints"]       — list of (x, y, confidence) for each keypoint
        data["activity_level"]  — float 0-1 indicating movement intensity
        data["form_issues"]     — list of detected form problems
        context_text            — coaching cue for LLM injection

    Args:
        model_path:       Path to YOLO pose model weights (e.g., yolov8n-pose.pt)
        exercise:         Current exercise type for form analysis (e.g., "squat", "pushup")
        throttle_seconds: Minimum seconds between emitted events (default: 2s)
    """

    name: str = "pose_lens"
    throttle_seconds: float = 2.0

    def __init__(
        self,
        model_path: str = "yolov8n-pose.pt",
        exercise: str = "general",
        throttle_seconds: float = None,
    ):
        self._model_path = model_path
        self._exercise = exercise
        self._model = None
        self._prev_keypoints = None
        super().__init__(throttle_seconds=throttle_seconds)

    def _setup(self):
        try:
            from ultralytics import YOLO
            self._model = YOLO(self._model_path)
            self._available = True
            logger.info("PoseLens ready — model: %s | exercise: %s", self._model_path, self._exercise)
        except ImportError:
            logger.warning("PoseLens: ultralytics not installed — pip install ultralytics")
            self._available = False
        except Exception as e:
            logger.warning("PoseLens: model load failed — %s", e)
            self._available = False

    def set_exercise(self, exercise: str):
        """Update the current exercise context for form analysis."""
        self._exercise = exercise
        logger.info("PoseLens exercise set to: %s", exercise)

    def process_frame(self, frame) -> Optional[LensEvent]:
        """
        Analyze a video frame for body pose and movement quality.

        Args:
            frame: PIL Image or numpy array

        Returns:
            LensEvent with pose data, or None if no person detected / throttled.
        """
        if not self._available or self._model is None:
            return None

        try:
            results = self._model(frame, verbose=False)
            pose_data = self._extract_pose(results)

            if pose_data is None:
                return None

            keypoints, confidence = pose_data
            activity_level = self._compute_activity(keypoints)
            form_issues, pose_state = self._analyze_form(keypoints)

            self._prev_keypoints = keypoints

            event = LensEvent(
                lens_name=self.name,
                data={
                    "pose_state": pose_state,
                    "keypoints": keypoints,
                    "activity_level": round(activity_level, 3),
                    "form_issues": form_issues,
                    "exercise": self._exercise,
                },
                confidence=confidence,
                context_text=self._build_context(pose_state, form_issues, activity_level),
            )
            self._emit(event)
            return event

        except Exception as e:
            logger.debug("PoseLens.process_frame error: %s", e)
            return None

    def _extract_pose(self, results) -> Optional[tuple]:
        """Extract keypoints and confidence from YOLO results."""
        if not results or len(results) == 0:
            return None

        result = results[0]

        if result.keypoints is None or len(result.keypoints) == 0:
            return None

        if result.boxes is None or len(result.boxes) == 0:
            return None

        confidence = float(result.boxes.conf[0])
        if confidence < MIN_CONFIDENCE:
            return None

        try:
            kp_data = result.keypoints[0]
            kp_xy = kp_data.xy[0].cpu().numpy()   # [17, 2]
            kp_conf = kp_data.conf[0].cpu().numpy()  # [17]

            keypoints = [
                {"x": float(kp_xy[i][0]), "y": float(kp_xy[i][1]), "conf": float(kp_conf[i])}
                for i in range(len(kp_xy))
            ]
            return keypoints, confidence
        except Exception:
            return None

    def _compute_activity(self, keypoints: list) -> float:
        """Estimate activity level by comparing to previous frame keypoints."""
        if self._prev_keypoints is None or len(keypoints) != len(self._prev_keypoints):
            return 0.0

        total_movement = 0.0
        valid_count = 0

        for curr, prev in zip(keypoints, self._prev_keypoints):
            if curr["conf"] > 0.3 and prev["conf"] > 0.3:
                dx = curr["x"] - prev["x"]
                dy = curr["y"] - prev["y"]
                total_movement += (dx ** 2 + dy ** 2) ** 0.5
                valid_count += 1

        if valid_count == 0:
            return 0.0

        avg_movement = total_movement / valid_count
        # Normalize to 0-1 (movement of ~50px = 1.0)
        return min(avg_movement / 50.0, 1.0)

    def _analyze_form(self, keypoints: list) -> tuple[list, str]:
        """
        Analyze pose for form issues based on exercise type.

        Returns (form_issues, pose_state).
        """
        if len(keypoints) < 17:
            return [], "unknown"

        form_issues = []

        try:
            # Key indices (COCO): 5=L_shoulder, 6=R_shoulder, 7=L_elbow, 8=R_elbow
            # 9=L_wrist, 10=R_wrist, 11=L_hip, 12=R_hip, 13=L_knee, 14=R_knee
            # 15=L_ankle, 16=R_ankle

            def kp(i):
                return keypoints[i]

            def visible(i):
                return kp(i)["conf"] > 0.3

            if self._exercise in ("squat", "general"):
                # Check knee alignment
                if visible(13) and visible(15) and visible(11):
                    knee_x = kp(13)["x"]
                    ankle_x = kp(15)["x"]
                    hip_x = kp(11)["x"]
                    if abs(knee_x - ankle_x) > abs(hip_x - ankle_x) * 0.3:
                        form_issues.append("knee_cave_left")

                if visible(14) and visible(16) and visible(12):
                    knee_x = kp(14)["x"]
                    ankle_x = kp(16)["x"]
                    hip_x = kp(12)["x"]
                    if abs(knee_x - ankle_x) > abs(hip_x - ankle_x) * 0.3:
                        form_issues.append("knee_cave_right")

            if self._exercise in ("pushup", "plank", "general"):
                # Check back alignment (hip drop)
                if visible(5) and visible(11) and visible(15):
                    shoulder_y = kp(5)["y"]
                    hip_y = kp(11)["y"]
                    ankle_y = kp(15)["y"]
                    if hip_y > 0 and ankle_y > 0:
                        expected_hip = shoulder_y + (ankle_y - shoulder_y) * 0.5
                        if abs(hip_y - expected_hip) / max(abs(ankle_y - shoulder_y), 1) > 0.2:
                            form_issues.append("hip_drop")

        except Exception:
            pass

        if form_issues:
            pose_state = "incorrect_form"
        else:
            pose_state = "correct_form"

        return form_issues, pose_state

    def _build_context(self, pose_state: str, form_issues: list, activity_level: float) -> str:
        level_str = "high" if activity_level > 0.6 else "moderate" if activity_level > 0.2 else "low"
        ctx = f"User pose: {pose_state.replace('_', ' ')}. Activity level: {level_str}."

        if form_issues:
            issue_str = ", ".join(i.replace("_", " ") for i in form_issues)
            ctx += f" Form issues detected: {issue_str}. Provide corrective cue."
        elif pose_state == "correct_form":
            ctx += " Form looks good — positive reinforcement appropriate."

        return ctx
