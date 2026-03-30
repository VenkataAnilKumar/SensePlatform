/**
 * @sense/vision — WebRTC video via Sense Relay
 *
 * @example
 * import { SenseClient } from "@sense/core";
 * import { SenseRoom } from "@sense/vision";
 *
 * const client = new SenseClient({ gateUrl: "http://localhost:3000", apiKey: "sk_live_..." });
 * await client.connect("user-123", "Alice");
 *
 * const room = new SenseRoom(client);
 * room.on("track_subscribed", ({ element }) => videoGrid.append(element));
 * room.on("participant_joined", (p) => console.log(p.name, "joined"));
 *
 * await room.join({ roomId: "support-room-42", autoPublish: true });
 */

export { SenseRoom } from "./room.js";
export type { SenseRoomOptions, SenseParticipant, RoomEvent, TrackInfo } from "./types.js";
