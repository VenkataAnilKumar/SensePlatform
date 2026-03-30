/**
 * @sense/lens — Lens Event Types
 * Mirrors the Python LensEvent dataclass from Sense Mind.
 */

export type MoodLabel = "neutral" | "satisfied" | "confused" | "frustrated" | "escalating";
export type PoseState = "unknown" | "idle" | "active" | "correct_form" | "incorrect_form" | "at_risk";
export type SafetySeverity = "low" | "medium" | "high" | "critical";
export type FaceEventType = "face_detected" | "no_face" | "multiple_faces" | "prolonged_absence";

export interface LensEvent {
  lensName: string;
  timestamp: number;
  confidence: number;
  contextText: string;
  data: MoodData | PoseData | GuardData | FaceData | Record<string, unknown>;
}

export interface MoodData {
  mood: MoodLabel;
  confidence: number;
  escalation: boolean;
}

export interface PoseData {
  poseState: PoseState;
  activityLevel: number;
  formIssues: string[];
  exercise: string;
  keypoints: Array<{ x: number; y: number; conf: number }>;
}

export interface GuardData {
  safe: boolean;
  violations: string[];
  severity: SafetySeverity;
  action: "log" | "warn" | "mute" | "terminate" | null;
  policy: string;
}

export interface FaceData {
  eventType: FaceEventType;
  faceCount: number;
  occupancy: number;
  maxOccupancy: number;
  faces: Array<{ x1: number; y1: number; x2: number; y2: number; conf: number }>;
}

export type LensHandler<T = LensEvent> = (event: T) => void;
