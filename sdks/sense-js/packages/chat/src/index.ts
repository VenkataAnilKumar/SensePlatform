/**
 * @sense/chat — Real-time chat via Sense Wire
 *
 * @example
 * import { SenseClient } from "@sense/core";
 * import { WireClient, Channel } from "@sense/chat";
 *
 * const client = new SenseClient({ gateUrl: "http://localhost:3000", apiKey: "sk_live_..." });
 * await client.connect("user-123", "Alice");
 *
 * const wire = new WireClient(client);
 * await wire.connect();
 *
 * const channel = new Channel(client, wire, "room", "support-room-42");
 *
 * wire.on("message.new", (event) => renderMessage(event.message));
 * wire.on("typing.start", (event) => showTyping(event.user_id));
 * wire.on("lens.event", (event) => updateMoodBadge(event.data));
 *
 * channel.sendMessage("Hello!");
 */

export { WireClient } from "./wire-client.js";
export { Channel } from "./channel.js";
export type { WireMessage, WireReaction, WireChannel, WireEvent, WireEventType } from "./types.js";
