/**
 * Sense Platform — Core Client
 * Base HTTP client for all Sense Gate API calls.
 */

import { SenseAuth } from "./auth.js";
import type { RoomJoinResponse, SenseConfig, SenseUser } from "./types.js";

export class SenseClient {
  readonly auth: SenseAuth;
  readonly config: Required<SenseConfig>;

  constructor(config: SenseConfig) {
    this.config = {
      gateUrl: config.gateUrl ?? "http://localhost:3000",
      wireUrl: config.wireUrl ?? "ws://localhost:3001",
      relayUrl: config.relayUrl ?? "ws://localhost:7880",
      apiKey: config.apiKey ?? "",
      tenantSlug: config.tenantSlug ?? "",
    };
    this.auth = new SenseAuth(this.config.gateUrl, this.config.apiKey);
  }

  // ── HTTP helpers ───────────────────────────────────────────────────────────

  private async _fetch<T>(
    path: string,
    options: RequestInit = {},
    useApiKey = false,
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string> ?? {}),
    };

    if (useApiKey && this.config.apiKey) {
      headers["X-API-Key"] = this.config.apiKey;
    } else if (this.auth.isAuthenticated()) {
      headers["Authorization"] = this.auth.authHeader();
    }

    const resp = await fetch(`${this.config.gateUrl}${path}`, {
      ...options,
      headers,
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(`[SenseGate] ${resp.status}: ${err.detail}`);
    }

    return resp.json() as Promise<T>;
  }

  // ── Auth ───────────────────────────────────────────────────────────────────

  /**
   * Authenticate as a user. Issues a JWT from Sense Gate.
   * Returns the token string.
   */
  async connect(userId: string, userName?: string, role = "user"): Promise<string> {
    return this.auth.login(userId, userName, role);
  }

  // ── Rooms ──────────────────────────────────────────────────────────────────

  /**
   * Join a Sense Relay room.
   * Returns a LiveKit token that your video client uses to connect.
   *
   * @example
   * const { relayUrl, relayToken } = await client.joinRoom("support-room-42");
   * // Pass relayToken to LiveKit JS SDK or @sense/vision
   */
  async joinRoom(
    roomId: string,
    options?: { canPublish?: boolean; canSubscribe?: boolean },
  ): Promise<RoomJoinResponse> {
    const user = this.auth.getUser();
    if (!user) throw new Error("Must call client.connect() before joinRoom()");

    return this._fetch<RoomJoinResponse>(`/rooms/${roomId}/join`, {
      method: "POST",
      body: JSON.stringify({
        user_id: user.id,
        user_name: user.name ?? user.id,
        can_publish: options?.canPublish ?? true,
        can_subscribe: options?.canSubscribe ?? true,
      }),
    });
  }

  /**
   * List active rooms for this tenant.
   */
  async listRooms(): Promise<Array<{ room_id: string; num_participants: number }>> {
    return this._fetch("/rooms");
  }

  // ── Agents ────────────────────────────────────────────────────────────────

  /**
   * Start a Sense Mind AI agent in a room.
   *
   * @example
   * await client.startAgent("support-room-42", {
   *   lenses: ["MoodLens"],
   *   llm: "claude-sonnet-4-6",
   * });
   */
  async startAgent(
    roomId: string,
    options?: { instructions?: string; lenses?: string[]; llm?: string },
  ): Promise<{ status: string; room: string }> {
    return this._fetch("/agents/start", {
      method: "POST",
      body: JSON.stringify({
        room_id: roomId,
        instructions: options?.instructions,
        lenses: options?.lenses ?? [],
        llm: options?.llm ?? "claude-sonnet-4-6",
      }),
    });
  }

  /**
   * Stop a running agent in a room.
   */
  async stopAgent(roomId: string): Promise<{ status: string }> {
    return this._fetch("/agents/stop", {
      method: "POST",
      body: JSON.stringify({ room_id: roomId }),
    });
  }

  // ── Health ────────────────────────────────────────────────────────────────

  async health(): Promise<{ status: string; service: string }> {
    return this._fetch("/health");
  }
}
