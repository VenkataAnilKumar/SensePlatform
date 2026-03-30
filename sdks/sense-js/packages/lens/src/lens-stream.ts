/**
 * @sense/lens — LensStream
 * Subscribes to Vision Lens events from Sense Mind via Sense Wire.
 * Provides typed handlers for each lens type.
 */

import type { WireClient } from "@sense/chat";
import type {
  FaceData,
  GuardData,
  LensEvent,
  LensHandler,
  MoodData,
  PoseData,
} from "./types.js";

function camelizeKeys(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(obj)) {
    const camel = k.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
    result[camel] = v !== null && typeof v === "object" && !Array.isArray(v)
      ? camelizeKeys(v as Record<string, unknown>)
      : v;
  }
  return result;
}

export class LensStream {
  private _moodHandlers: LensHandler<LensEvent & { data: MoodData }>[] = [];
  private _poseHandlers: LensHandler<LensEvent & { data: PoseData }>[] = [];
  private _guardHandlers: LensHandler<LensEvent & { data: GuardData }>[] = [];
  private _faceHandlers: LensHandler<LensEvent & { data: FaceData }>[] = [];
  private _allHandlers: LensHandler[] = [];

  constructor(private readonly wire: WireClient) {
    this.wire.on("lens.event", (rawEvent) => this._handleLensEvent(rawEvent));
  }

  /**
   * React to MoodLens events — customer emotion changes.
   *
   * @example
   * lens.onMood(({ data, contextText }) => {
   *   if (data.escalation) showEscalationAlert();
   *   setMoodBadge(data.mood);
   * });
   */
  onMood(handler: LensHandler<LensEvent & { data: MoodData }>): this {
    this._moodHandlers.push(handler);
    return this;
  }

  /**
   * React to PoseLens events — body form and activity.
   *
   * @example
   * lens.onPose(({ data }) => {
   *   if (data.formIssues.includes("knee_cave_left")) showKneeWarning();
   *   setActivityMeter(data.activityLevel);
   * });
   */
  onPose(handler: LensHandler<LensEvent & { data: PoseData }>): this {
    this._poseHandlers.push(handler);
    return this;
  }

  /**
   * React to GuardLens events — content safety violations.
   *
   * @example
   * lens.onGuard(({ data }) => {
   *   if (data.action === "terminate") endSession();
   *   if (data.action === "warn") showContentWarning(data.violations);
   * });
   */
  onGuard(handler: LensHandler<LensEvent & { data: GuardData }>): this {
    this._guardHandlers.push(handler);
    return this;
  }

  /**
   * React to FaceLens events — presence and occupancy.
   *
   * @example
   * lens.onFace(({ data }) => {
   *   if (data.eventType === "no_face") showAwayIndicator();
   *   if (data.eventType === "multiple_faces") showMultiplePersonAlert();
   *   setOccupancyCount(data.faceCount);
   * });
   */
  onFace(handler: LensHandler<LensEvent & { data: FaceData }>): this {
    this._faceHandlers.push(handler);
    return this;
  }

  /**
   * Receive all lens events regardless of type.
   */
  onAny(handler: LensHandler): this {
    this._allHandlers.push(handler);
    return this;
  }

  // ── Private ───────────────────────────────────────────────────────────────

  private _handleLensEvent(rawEvent: Record<string, unknown>): void {
    const eventData = (rawEvent.data ?? rawEvent) as Record<string, unknown>;
    const camelized = camelizeKeys(eventData) as unknown as LensEvent;

    // Route to all-event handlers
    for (const h of this._allHandlers) h(camelized);

    // Route by lens name
    const lens = camelized.lensName ?? (rawEvent.lens_name as string);

    if (lens === "mood_lens") {
      for (const h of this._moodHandlers) {
        h(camelized as LensEvent & { data: MoodData });
      }
    } else if (lens === "pose_lens") {
      for (const h of this._poseHandlers) {
        h(camelized as LensEvent & { data: PoseData });
      }
    } else if (lens === "guard_lens") {
      for (const h of this._guardHandlers) {
        h(camelized as LensEvent & { data: GuardData });
      }
    } else if (lens === "face_lens") {
      for (const h of this._faceHandlers) {
        h(camelized as LensEvent & { data: FaceData });
      }
    }
  }
}
