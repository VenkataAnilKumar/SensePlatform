"""
Sense Relay Transport
=====================
Implements the RelayTransport (EdgeTransport) interface using Sense Relay
(self-hosted LiveKit WebRTC server) instead of GetStream cloud.

This is the critical bridge that makes ALL Sense Mind plugins work
against the self-hosted Sense Relay server.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Optional

import aiortc
from livekit import api, rtc

from sense_mind.core.edge.edge_transport import EdgeTransport
from sense_mind.core.edge.types import Connection, Participant, User
from sense_mind.core.edge.events import (
    AudioReceivedEvent,
    CallEndedEvent,
    TrackAddedEvent,
    TrackRemovedEvent,
)
from sense_mind.core.edge.call import Call

if TYPE_CHECKING:
    from sense_mind.core.agents.agents import SenseMind

logger = logging.getLogger(__name__)


class RelayCall(Call):
    """Represents a room session on Sense Relay."""

    def __init__(self, room_name: str, room: rtc.Room):
        self.room_name = room_name
        self.room = room

    @property
    def id(self) -> str:
        return self.room_name


class RelayConnection(Connection):
    """Active connection to a Sense Relay room."""

    def __init__(self, room: rtc.Room, agent_identity: str):
        self._room = room
        self._agent_identity = agent_identity
        self._participant_joined = asyncio.Event()
        self._idle_since: float = 0.0
        self._closed = False

        # Track when participants join/leave
        self._room.on("participant_connected", self._on_participant_joined)
        self._room.on("participant_disconnected", self._on_participant_left)

        # If already has non-agent participants, mark as active
        if self._has_real_participants():
            self._participant_joined.set()

    def _has_real_participants(self) -> bool:
        return any(
            p.identity != self._agent_identity
            for p in self._room.remote_participants.values()
        )

    def _on_participant_joined(self, participant: rtc.RemoteParticipant):
        if participant.identity != self._agent_identity:
            logger.info("Participant joined: %s", participant.identity)
            self._participant_joined.set()
            self._idle_since = 0.0

    def _on_participant_left(self, participant: rtc.RemoteParticipant):
        if not self._has_real_participants():
            logger.info("All participants left — connection going idle")
            self._idle_since = time.time()

    async def wait_for_participant(self, timeout: Optional[float] = None) -> None:
        await asyncio.wait_for(self._participant_joined.wait(), timeout=timeout)

    def idle_since(self) -> float:
        return self._idle_since

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._room.disconnect()
            logger.info("Relay connection closed")


class RelayTransport(EdgeTransport[RelayCall]):
    """
    Transport implementation for Sense Relay (self-hosted LiveKit WebRTC).

    Usage:
        transport = RelayTransport(
            url="ws://localhost:7880",
            api_key="sense_gateway",
            api_secret="secret_change_in_production",
        )
    """

    def __init__(
        self,
        url: str = "ws://localhost:7880",
        api_key: str = "sense_gateway",
        api_secret: str = "secret_change_in_production",
    ):
        super().__init__()
        self._url = url
        self._api_key = api_key
        self._api_secret = api_secret
        self._livekit_api = api.LiveKitAPI(
            url=url.replace("ws://", "http://").replace("wss://", "https://"),
            api_key=api_key,
            api_secret=api_secret,
        )
        self._room: Optional[rtc.Room] = None
        self._agent_user: Optional[User] = None
        self._agent_token: Optional[str] = None
        self._source = rtc.AudioSource(sample_rate=48000, num_channels=1)
        self._audio_track: Optional[rtc.LocalAudioTrack] = None

    async def authenticate(self, user: User) -> None:
        """Generate an access token for the agent user."""
        self._agent_user = user
        logger.info("Relay transport authenticated for user: %s", user.id)

    async def create_call(self, call_id: str, **kwargs) -> RelayCall:
        """Create or retrieve a Sense Relay room."""
        try:
            await self._livekit_api.room.create_room(
                api.CreateRoomRequest(name=call_id)
            )
            logger.info("Created Relay room: %s", call_id)
        except Exception:
            logger.info("Room %s already exists — joining", call_id)

        room = rtc.Room()
        return RelayCall(room_name=call_id, room=room)

    def create_audio_track(self):
        """Create an audio track for the agent to publish."""
        self._audio_track = rtc.LocalAudioTrack.create_audio_track(
            "sense-agent-audio", self._source
        )
        # Return aiortc-compatible wrapper for Vision-Agents compatibility
        return _LiveKitAudioTrackAdapter(self._audio_track, self._source)

    async def join(self, agent: "SenseMind", call: RelayCall, **kwargs) -> RelayConnection:
        """Join a Sense Relay room and set up media/event handlers."""
        self._room = call.room

        # Generate access token for agent
        token = (
            api.AccessToken(self._api_key, self._api_secret)
            .with_identity(self._agent_user.id if self._agent_user else "sense-agent")
            .with_name(self._agent_user.name if self._agent_user else "Sense AI")
            .with_grants(api.VideoGrants(
                room_join=True,
                room=call.room_name,
                can_publish=True,
                can_subscribe=True,
            ))
            .to_jwt()
        )

        # Wire up incoming audio → AudioReceivedEvent
        @self._room.on("track_subscribed")
        def on_track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ):
            p = Participant(
                original=participant,
                user_id=participant.identity,
                id=participant.sid,
            )
            self.events.emit(TrackAddedEvent(participant=p, track_id=track.sid))

            if track.kind == rtc.TrackKind.KIND_AUDIO:
                audio_stream = rtc.AudioStream(track)
                asyncio.ensure_future(
                    self._forward_audio(audio_stream, p)
                )

        @self._room.on("track_unsubscribed")
        def on_track_unsubscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ):
            p = Participant(
                original=participant,
                user_id=participant.identity,
                id=participant.sid,
            )
            self.events.emit(TrackRemovedEvent(participant=p, track_id=track.sid))

        @self._room.on("disconnected")
        def on_disconnected(reason):
            self.events.emit(CallEndedEvent())

        # Connect to room
        await self._room.connect(self._url, token)
        logger.info("Sense Mind joined Relay room: %s", call.room_name)

        return RelayConnection(self._room, self._agent_user.id if self._agent_user else "sense-agent")

    async def _forward_audio(self, stream: rtc.AudioStream, participant: Participant):
        """Forward incoming audio frames as AudioReceivedEvents."""
        async for frame_event in stream:
            frame = frame_event.frame
            self.events.emit(AudioReceivedEvent(
                participant=participant,
                audio_data=frame.data,
                sample_rate=frame.sample_rate,
                num_channels=frame.num_channels,
            ))

    async def publish_tracks(
        self,
        audio_track=None,
        video_track=None,
    ):
        """Publish agent audio/video to the Relay room."""
        if self._room and audio_track and self._audio_track:
            await self._room.local_participant.publish_track(self._audio_track)
            logger.info("Agent audio track published to Relay")

    async def create_conversation(self, call: RelayCall, user: User, instructions: str):
        """Initialize conversation context (handled by LLM layer)."""
        logger.debug("Conversation initialized for room: %s", call.room_name)

    def add_track_subscriber(self, track_id: str):
        """Return a video track subscriber for vision processing."""
        return None  # Vision frames come via track_subscribed events

    async def send_custom_event(self, data: dict[str, Any]) -> None:
        """Send a data message to all room participants."""
        if self._room:
            import json
            await self._room.local_participant.publish_data(
                json.dumps(data).encode(),
                reliable=True,
            )

    def open_demo(self, *args, **kwargs):
        """No-op for headless server deployment."""
        pass

    async def close(self):
        """Disconnect from Relay room and clean up."""
        if self._room:
            await self._room.disconnect()
            self._room = None
        await self._livekit_api.aclose()
        logger.info("Relay transport closed")


class _LiveKitAudioTrackAdapter:
    """
    Thin adapter that wraps a LiveKit LocalAudioTrack to be compatible
    with the aiortc AudioStreamTrack interface expected by Vision-Agents.
    """
    def __init__(self, livekit_track: rtc.LocalAudioTrack, source: rtc.AudioSource):
        self._livekit_track = livekit_track
        self._source = source

    async def capture_frame(self, frame: rtc.AudioFrame):
        """Push a PCM audio frame to the LiveKit audio source."""
        await self._source.capture_frame(frame)
