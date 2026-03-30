/**
 * @sense/lens — Vision Lens event subscription for the browser
 *
 * @example
 * import { SenseClient } from "@sense/core";
 * import { WireClient } from "@sense/chat";
 * import { LensStream } from "@sense/lens";
 *
 * const client = new SenseClient({ gateUrl: "http://localhost:3000", apiKey: "sk_live_..." });
 * await client.connect("user-123", "Alice");
 *
 * const wire = new WireClient(client);
 * await wire.connect();
 * wire.subscribe("room", "support-room-42");
 *
 * const lens = new LensStream(wire);
 *
 * lens.onMood(({ data, contextText }) => {
 *   setMoodBadge(data.mood);        // "frustrated" | "satisfied" | ...
 *   if (data.escalation) alert("Escalation risk!");
 * });
 *
 * lens.onPose(({ data }) => {
 *   if (data.formIssues.length > 0) showFormWarning(data.formIssues);
 * });
 *
 * lens.onGuard(({ data }) => {
 *   if (data.action === "terminate") endSession();
 * });
 *
 * lens.onFace(({ data }) => {
 *   setOccupancyBadge(data.faceCount);
 * });
 */

export { LensStream } from "./lens-stream.js";
export type {
  LensEvent,
  MoodData,
  PoseData,
  GuardData,
  FaceData,
  MoodLabel,
  PoseState,
  SafetySeverity,
  FaceEventType,
  LensHandler,
} from "./types.js";
