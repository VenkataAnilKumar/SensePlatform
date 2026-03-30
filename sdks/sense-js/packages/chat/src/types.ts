/**
 * @sense/chat — Types
 */

export interface WireMessage {
  id: string;
  channelId: string;
  userId: string;
  userName?: string;
  text: string;
  isAgent: boolean;
  parentId?: string;
  replyCount: number;
  reactions: WireReaction[];
  createdAt: string;
  updatedAt?: string;
}

export interface WireReaction {
  emoji: string;
  userId: string;
}

export interface WireChannel {
  id: string;
  tenantId: string;
  channelType: string;
  channelId: string;
  name?: string;
  memberCount: number;
  messageCount: number;
  isFrozen: boolean;
}

export type WireEventType =
  | "message.new"
  | "message.updated"
  | "message.deleted"
  | "reaction.new"
  | "reaction.deleted"
  | "typing.start"
  | "typing.stop"
  | "member.added"
  | "member.removed"
  | "channel.updated"
  | "lens.event"
  | "agent.message"
  | "custom"
  | "connection.ack"
  | "connection.error";

export interface WireEvent {
  type: WireEventType;
  created_at: number;
  [key: string]: unknown;
}
