/**
 * @sense/chat — Channel
 * High-level channel operations: send messages, fetch history, reactions.
 */

import type { SenseClient } from "@sense/core";
import type { WireChannel, WireMessage } from "./types.js";
import type { WireClient } from "./wire-client.js";

export class Channel {
  constructor(
    private readonly client: SenseClient,
    private readonly wire: WireClient,
    readonly channelType: string,
    readonly channelId: string,
  ) {
    // Subscribe to WebSocket events for this channel
    this.wire.subscribe(channelType, channelId);
  }

  /**
   * Send a message to this channel.
   *
   * @example
   * await channel.sendMessage("Hello, how can I help you today?");
   */
  sendMessage(text: string, options?: { parentId?: string }): void {
    if (!text.trim()) return;
    (this.wire as unknown as { _send: (d: Record<string, unknown>) => void })._send({
      type: "message.new",
      channel_type: this.channelType,
      channel_id: this.channelId,
      text,
      parent_id: options?.parentId,
      user_name: this.client.auth.getUser()?.name,
    });
  }

  /**
   * Fetch message history (REST).
   *
   * @example
   * const { messages, hasMore } = await channel.getMessages({ limit: 50 });
   */
  async getMessages(options?: {
    limit?: number;
    before?: string;
  }): Promise<{ messages: WireMessage[]; hasMore: boolean; nextCursor: string | null }> {
    const user = this.client.auth.getUser();
    if (!user) throw new Error("Not authenticated");

    const params = new URLSearchParams();
    if (options?.limit) params.set("limit", String(options.limit));
    if (options?.before) params.set("before", options.before);

    const wireHttpUrl = this.client.config.wireUrl.replace(/^ws/, "http");
    const resp = await fetch(
      `${wireHttpUrl}/channels/${this.channelType}/${this.channelId}/messages?${params}`,
      { headers: { Authorization: this.client.auth.authHeader() } },
    );

    if (!resp.ok) throw new Error(`Failed to fetch messages: ${resp.statusText}`);

    const data = await resp.json();
    return {
      messages: data.messages,
      hasMore: data.has_more,
      nextCursor: data.next_cursor,
    };
  }

  /**
   * Add an emoji reaction to a message.
   */
  addReaction(messageId: string, emoji: string): void {
    (this.wire as unknown as { _send: (d: Record<string, unknown>) => void })._send({
      type: "reaction.add",
      channel_type: this.channelType,
      channel_id: this.channelId,
      message_id: messageId,
      emoji,
    });
  }

  /**
   * Remove an emoji reaction.
   */
  removeReaction(messageId: string, emoji: string): void {
    (this.wire as unknown as { _send: (d: Record<string, unknown>) => void })._send({
      type: "reaction.remove",
      channel_type: this.channelType,
      channel_id: this.channelId,
      message_id: messageId,
      emoji,
    });
  }

  /**
   * Send a typing start indicator.
   */
  startTyping(): void {
    (this.wire as unknown as { _send: (d: Record<string, unknown>) => void })._send({
      type: "typing.start",
      channel_type: this.channelType,
      channel_id: this.channelId,
    });
  }

  /**
   * Send a typing stop indicator.
   */
  stopTyping(): void {
    (this.wire as unknown as { _send: (d: Record<string, unknown>) => void })._send({
      type: "typing.stop",
      channel_type: this.channelType,
      channel_id: this.channelId,
    });
  }

  /**
   * Mark the channel as read up to now.
   */
  markRead(): void {
    (this.wire as unknown as { _send: (d: Record<string, unknown>) => void })._send({
      type: "channel.read",
      channel_type: this.channelType,
      channel_id: this.channelId,
    });
  }

  /** Leave this channel (unsubscribe from WebSocket events). */
  leave(): void {
    this.wire.unsubscribe(this.channelType, this.channelId);
  }
}
