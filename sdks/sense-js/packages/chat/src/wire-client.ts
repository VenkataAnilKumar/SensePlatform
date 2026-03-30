/**
 * @sense/chat — WireClient
 * WebSocket client for Sense Wire. Manages the connection lifecycle,
 * reconnection, and event routing.
 */

import type { SenseClient } from "@sense/core";
import type { WireEvent, WireEventType } from "./types.js";

type EventHandler = (event: WireEvent) => void | Promise<void>;

const RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_ATTEMPTS = 5;

export class WireClient {
  private _ws: WebSocket | null = null;
  private _connected = false;
  private _reconnectAttempts = 0;
  private _handlers: Map<WireEventType | "*", EventHandler[]> = new Map();
  private _pendingMessages: string[] = [];

  constructor(private readonly client: SenseClient) {}

  /**
   * Connect to Sense Wire WebSocket.
   * Automatically uses the JWT from SenseClient.auth.
   *
   * @example
   * const wire = new WireClient(client);
   * await wire.connect();
   */
  async connect(): Promise<void> {
    const token = this.client.auth.getToken();
    if (!token) throw new Error("@sense/chat: not authenticated. Call client.connect() first.");

    return new Promise((resolve, reject) => {
      const wireUrl = this.client.config.wireUrl.replace(/^http/, "ws");
      const url = `${wireUrl}/ws/connect?token=${encodeURIComponent(token)}`;

      this._ws = new WebSocket(url);

      this._ws.onopen = () => {
        this._connected = true;
        this._reconnectAttempts = 0;
        // Flush any messages queued before connection
        for (const msg of this._pendingMessages) this._ws!.send(msg);
        this._pendingMessages = [];
      };

      this._ws.onmessage = (ev) => {
        try {
          const event: WireEvent = JSON.parse(ev.data as string);
          if (event.type === "connection.ack") {
            resolve();
          }
          this._dispatch(event);
        } catch {
          // ignore malformed frames
        }
      };

      this._ws.onerror = () => reject(new Error("@sense/chat: WebSocket connection failed"));

      this._ws.onclose = () => {
        this._connected = false;
        this._dispatch({ type: "connection.error", created_at: Date.now(), reason: "closed" });
        this._scheduleReconnect();
      };
    });
  }

  /**
   * Disconnect from Sense Wire.
   */
  disconnect(): void {
    this._reconnectAttempts = MAX_RECONNECT_ATTEMPTS; // prevent auto-reconnect
    this._ws?.close();
    this._ws = null;
    this._connected = false;
  }

  /**
   * Subscribe to a channel to receive its messages.
   */
  subscribe(channelType: string, channelId: string): void {
    this._send({ type: "channel.subscribe", channel_type: channelType, channel_id: channelId });
  }

  /**
   * Unsubscribe from a channel.
   */
  unsubscribe(channelType: string, channelId: string): void {
    this._send({ type: "channel.unsubscribe", channel_type: channelType, channel_id: channelId });
  }

  /**
   * Register an event handler.
   * Use "*" to receive all events.
   *
   * @example
   * wire.on("message.new", (event) => console.log(event.message));
   * wire.on("typing.start", (event) => showTypingIndicator(event.user_id));
   * wire.on("lens.event", (event) => updateMoodBadge(event.data));
   */
  on(eventType: WireEventType | "*", handler: EventHandler): this {
    if (!this._handlers.has(eventType)) this._handlers.set(eventType, []);
    this._handlers.get(eventType)!.push(handler);
    return this;
  }

  off(eventType: WireEventType | "*", handler: EventHandler): this {
    const handlers = this._handlers.get(eventType) ?? [];
    this._handlers.set(eventType, handlers.filter((h) => h !== handler));
    return this;
  }

  isConnected(): boolean {
    return this._connected;
  }

  // ── Private ───────────────────────────────────────────────────────────────

  private _send(data: Record<string, unknown>): void {
    const msg = JSON.stringify(data);
    if (this._connected && this._ws?.readyState === WebSocket.OPEN) {
      this._ws.send(msg);
    } else {
      this._pendingMessages.push(msg);
    }
  }

  private _dispatch(event: WireEvent): void {
    const specific = this._handlers.get(event.type) ?? [];
    const wildcard = this._handlers.get("*") ?? [];
    for (const h of [...specific, ...wildcard]) {
      try {
        void h(event);
      } catch {
        // swallow handler errors
      }
    }
  }

  private _scheduleReconnect(): void {
    if (this._reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) return;
    this._reconnectAttempts++;
    const delay = RECONNECT_DELAY_MS * this._reconnectAttempts;
    setTimeout(() => void this.connect(), delay);
  }
}
