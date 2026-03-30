/**
 * @sense/core — Sense Platform Core Client
 *
 * @example
 * import { SenseClient } from "@sense/core";
 *
 * const client = new SenseClient({
 *   gateUrl: "http://localhost:3000",
 *   apiKey: "sk_live_...",
 * });
 *
 * await client.connect("user-123", "Alice");
 * const { relayUrl, relayToken } = await client.joinRoom("support-room");
 * await client.startAgent("support-room", { lenses: ["MoodLens"] });
 */

export { SenseClient } from "./client.js";
export { SenseAuth } from "./auth.js";
export type {
  SenseConfig,
  SenseUser,
  TokenResponse,
  RoomJoinResponse,
  ApiError,
  SenseEventHandler,
} from "./types.js";
