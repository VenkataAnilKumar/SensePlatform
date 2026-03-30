/**
 * Sense Platform — Shared Types
 */

export interface SenseConfig {
  /** Sense Gate URL (default: http://localhost:3000) */
  gateUrl: string;
  /** Sense Wire URL (default: ws://localhost:3001) */
  wireUrl?: string;
  /** Sense Relay URL (default: ws://localhost:7880) — usually provided by Gate */
  relayUrl?: string;
  /** API key (server-side) or JWT (client-side) */
  apiKey?: string;
  /** Tenant slug */
  tenantSlug?: string;
}

export interface SenseUser {
  id: string;
  name?: string;
  role?: string;
  tenantId?: string;
}

export interface TokenResponse {
  accessToken: string;
  tokenType: string;
  expiresIn: number;
}

export interface RoomJoinResponse {
  relayUrl: string;
  relayToken: string;
  roomId: string;
  roomName: string;
}

export interface ApiError {
  status: number;
  detail: string;
  code?: string;
}

export type SenseEventHandler<T = unknown> = (event: T) => void | Promise<void>;
