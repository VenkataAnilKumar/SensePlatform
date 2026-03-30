/**
 * @sense/vision — Types
 */

export interface SenseRoomOptions {
  /** Room ID (user-facing, not namespaced). */
  roomId: string;
  /** Display name for this participant. */
  userName?: string;
  /** Publish camera + mic on join. Default: true */
  autoPublish?: boolean;
  /** Video container element to attach remote tracks to. */
  container?: HTMLElement;
}

export interface SenseParticipant {
  identity: string;
  name: string;
  isAgent: boolean;
  isSpeaking: boolean;
  isCameraEnabled: boolean;
  isMicEnabled: boolean;
}

export type RoomEvent =
  | "connected"
  | "disconnected"
  | "participant_joined"
  | "participant_left"
  | "track_subscribed"
  | "track_unsubscribed"
  | "speaking_changed"
  | "error";

export interface TrackInfo {
  trackSid: string;
  participantIdentity: string;
  kind: "audio" | "video";
  element?: HTMLMediaElement;
}
