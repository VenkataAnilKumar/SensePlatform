/**
 * @sense/vision — SenseRoom
 * Wraps the LiveKit Room to connect to a Sense Relay WebRTC room.
 */

import { Room, RoomEvent as LKRoomEvent, Track, createLocalTracks } from "livekit-client";
import type { SenseClient } from "@sense/core";
import type { RoomEvent, SenseParticipant, SenseRoomOptions, TrackInfo } from "./types.js";

type EventCallback<T = unknown> = (data: T) => void;

export class SenseRoom {
  private _room: Room;
  private _handlers: Map<RoomEvent, EventCallback[]> = new Map();
  private _participants: Map<string, SenseParticipant> = new Map();

  constructor(private readonly client: SenseClient) {
    this._room = new Room({
      adaptiveStream: true,
      dynacast: true,
    });
    this._bindRoomEvents();
  }

  /**
   * Join a Sense Relay room.
   * Automatically fetches a relay token from Sense Gate.
   *
   * @example
   * const room = new SenseRoom(client);
   * await room.join({ roomId: "support-room-42", autoPublish: true });
   */
  async join(options: SenseRoomOptions): Promise<void> {
    const { relayUrl, relayToken } = await this.client.joinRoom(options.roomId, {
      canPublish: true,
      canSubscribe: true,
    });

    await this._room.connect(relayUrl, relayToken);

    if (options.autoPublish !== false) {
      await this.publish();
    }

    this._emit("connected", { roomId: options.roomId });
  }

  /**
   * Publish local camera + microphone to the room.
   */
  async publish(video = true, audio = true): Promise<void> {
    const tracks = await createLocalTracks({ video, audio });
    for (const track of tracks) {
      await this._room.localParticipant.publishTrack(track);
    }
  }

  /**
   * Mute/unmute local microphone.
   */
  async setMicEnabled(enabled: boolean): Promise<void> {
    await this._room.localParticipant.setMicrophoneEnabled(enabled);
  }

  /**
   * Enable/disable local camera.
   */
  async setCameraEnabled(enabled: boolean): Promise<void> {
    await this._room.localParticipant.setCameraEnabled(enabled);
  }

  /**
   * Leave the room and clean up tracks.
   */
  async leave(): Promise<void> {
    await this._room.disconnect();
    this._emit("disconnected", {});
  }

  /**
   * Get all current participants (excluding local).
   */
  getParticipants(): SenseParticipant[] {
    return Array.from(this._participants.values());
  }

  /**
   * Register an event handler.
   *
   * @example
   * room.on("participant_joined", ({ identity }) => console.log(identity, "joined"));
   * room.on("track_subscribed", ({ element }) => videoContainer.append(element));
   */
  on<T = unknown>(event: RoomEvent, handler: EventCallback<T>): this {
    if (!this._handlers.has(event)) this._handlers.set(event, []);
    this._handlers.get(event)!.push(handler as EventCallback);
    return this;
  }

  off(event: RoomEvent, handler: EventCallback): this {
    const handlers = this._handlers.get(event) ?? [];
    this._handlers.set(event, handlers.filter((h) => h !== handler));
    return this;
  }

  /** Access the underlying LiveKit Room for advanced usage. */
  get liveKitRoom(): Room {
    return this._room;
  }

  // ── Private ───────────────────────────────────────────────────────────────

  private _emit(event: RoomEvent, data: unknown): void {
    const handlers = this._handlers.get(event) ?? [];
    for (const h of handlers) h(data);
  }

  private _bindRoomEvents(): void {
    this._room.on(LKRoomEvent.ParticipantConnected, (participant) => {
      const p: SenseParticipant = {
        identity: participant.identity,
        name: participant.name ?? participant.identity,
        isAgent: participant.identity.startsWith("sense-agent"),
        isSpeaking: false,
        isCameraEnabled: false,
        isMicEnabled: false,
      };
      this._participants.set(participant.identity, p);
      this._emit("participant_joined", p);
    });

    this._room.on(LKRoomEvent.ParticipantDisconnected, (participant) => {
      const p = this._participants.get(participant.identity);
      this._participants.delete(participant.identity);
      this._emit("participant_left", p ?? { identity: participant.identity });
    });

    this._room.on(LKRoomEvent.TrackSubscribed, (track, _pub, participant) => {
      const info: TrackInfo = {
        trackSid: track.sid ?? "",
        participantIdentity: participant.identity,
        kind: track.kind === Track.Kind.Audio ? "audio" : "video",
      };

      // Auto-attach video tracks to a media element
      if (track.kind === Track.Kind.Video || track.kind === Track.Kind.Audio) {
        const el = track.attach();
        info.element = el;
      }

      this._emit("track_subscribed", info);
    });

    this._room.on(LKRoomEvent.TrackUnsubscribed, (track, _pub, participant) => {
      track.detach();
      this._emit("track_unsubscribed", {
        trackSid: track.sid,
        participantIdentity: participant.identity,
      });
    });

    this._room.on(LKRoomEvent.ActiveSpeakersChanged, (speakers) => {
      for (const [identity, p] of this._participants) {
        p.isSpeaking = speakers.some((s) => s.identity === identity);
      }
      this._emit("speaking_changed", { speakers: speakers.map((s) => s.identity) });
    });

    this._room.on(LKRoomEvent.Disconnected, () => {
      this._emit("disconnected", {});
    });
  }
}
