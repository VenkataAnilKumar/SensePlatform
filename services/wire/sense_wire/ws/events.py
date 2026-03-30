"""
Sense Wire — WebSocket Event Types
All events sent over the WebSocket connection.
"""

# ── Client → Server ──────────────────────────────────────────────────────────
class ClientEvent:
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    SUBSCRIBE = "channel.subscribe"
    UNSUBSCRIBE = "channel.unsubscribe"
    MESSAGE_NEW = "message.new"
    MESSAGE_DELETE = "message.delete"
    MESSAGE_UPDATE = "message.update"
    REACTION_ADD = "reaction.add"
    REACTION_REMOVE = "reaction.remove"
    TYPING_START = "typing.start"
    TYPING_STOP = "typing.stop"
    READ_MARK = "channel.read"
    CUSTOM = "custom"


# ── Server → Client ──────────────────────────────────────────────────────────
class ServerEvent:
    CONNECTED = "connection.ack"
    ERROR = "connection.error"
    MESSAGE_NEW = "message.new"
    MESSAGE_UPDATED = "message.updated"
    MESSAGE_DELETED = "message.deleted"
    REACTION_NEW = "reaction.new"
    REACTION_DELETED = "reaction.deleted"
    TYPING_START = "typing.start"
    TYPING_STOP = "typing.stop"
    MEMBER_ADDED = "member.added"
    MEMBER_REMOVED = "member.removed"
    CHANNEL_UPDATED = "channel.updated"
    LENS_EVENT = "lens.event"       # Vision Lens events (mood, pose, etc.)
    AGENT_MESSAGE = "agent.message" # Sense Mind agent messages
    CUSTOM = "custom"


def make_event(event_type: str, **data) -> dict:
    """Build a standard Wire event payload."""
    import time
    return {"type": event_type, "created_at": time.time(), **data}
