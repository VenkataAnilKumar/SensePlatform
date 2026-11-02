"use client";

import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track } from "livekit-client";
import { Camera, Send, Square, Play } from "lucide-react";
import { Header } from "@/components/layout/header";
import { WIRE_URL, demoApi } from "@/lib/api";

const LENSES = [
  { id: "MoodLens", label: "Mood" },
  { id: "PoseLens", label: "Pose" },
  { id: "FaceLens", label: "Face" },
  { id: "GuardLens", label: "Guard" },
];

interface LensCard {
  key: number;
  lens: string;
  confidence: number;
  contextText: string;
  detail: string;
  at: string;
}

interface ChatLine {
  key: number;
  user: string;
  text: string;
}

const LENS_STYLE: Record<string, string> = {
  mood_lens: "bg-amber-100 text-amber-800",
  pose_lens: "bg-blue-100 text-blue-800",
  face_lens: "bg-green-100 text-green-800",
  guard_lens: "bg-red-100 text-red-800",
};

function detailOf(data: Record<string, unknown>): string {
  for (const k of ["mood", "pose_state", "event_type", "severity"]) {
    if (data[k]) return String(data[k]).replace(/_/g, " ");
  }
  return "";
}

export default function LiveDemoPage() {
  const [roomId, setRoomId] = useState("demo");
  const [lenses, setLenses] = useState<string[]>(["MoodLens", "FaceLens"]);
  const [status, setStatus] = useState<"idle" | "starting" | "live" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [agentIn, setAgentIn] = useState(false);
  const [cards, setCards] = useState<LensCard[]>([]);
  const [chat, setChat] = useState<ChatLine[]>([]);
  const [draft, setDraft] = useState("");

  const videoRef = useRef<HTMLVideoElement>(null);
  const roomRef = useRef<Room | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const counter = useRef(0);
  const liveRoomId = useRef("");
  const userId = useRef(`demo-${Math.random().toString(36).slice(2, 7)}`);

  async function start() {
    setError(null);
    setStatus("starting");
    setCards([]);
    setChat([]);
    liveRoomId.current = roomId;
    try {
      // 1. AI agent with the chosen lenses
      await demoApi.startAgent(roomId, lenses);

      // 2. Wire: lens events + chat
      const { access_token } = await demoApi.token(userId.current, userId.current);
      const httpWire = WIRE_URL.replace(/^ws/, "http");
      await fetch(`${httpWire}/channels`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${access_token}` },
        body: JSON.stringify({ channel_type: "room", channel_id: roomId }),
      }).catch(() => undefined); // already exists is fine
      const ws = new WebSocket(`${WIRE_URL}/ws/connect?token=${access_token}`);
      wsRef.current = ws;
      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "channel.subscribe", channel_type: "lens", channel_id: roomId }));
        ws.send(JSON.stringify({ type: "channel.subscribe", channel_type: "room", channel_id: roomId }));
      };
      ws.onmessage = (m) => {
        const ev = JSON.parse(m.data);
        if (ev.type === "lens.event" && ev.data) {
          const d = ev.data as Record<string, unknown>;
          setCards((prev) => [
            {
              key: counter.current++,
              lens: String(d.lens_name ?? "lens"),
              confidence: Number(d.confidence ?? 0),
              contextText: String(d.context_text ?? ""),
              detail: detailOf(d),
              at: new Date().toLocaleTimeString(),
            },
            ...prev,
          ].slice(0, 30));
        } else if (ev.type === "message.new" && ev.message) {
          setChat((prev) => [...prev, { key: counter.current++, user: ev.message.user_id, text: ev.message.text }]);
        }
      };

      // 3. Camera + mic into the Relay room
      const join = await demoApi.join(roomId, userId.current);
      const room = new Room();
      roomRef.current = room;
      room.on(RoomEvent.ParticipantConnected, () => setAgentIn(true));
      room.on(RoomEvent.ParticipantDisconnected, () => setAgentIn(room.remoteParticipants.size > 0));
      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio) document.body.appendChild(track.attach()); // agent voice
      });
      await room.connect(join.relay_url, join.relay_token);
      setAgentIn(room.remoteParticipants.size > 0);
      await room.localParticipant.setCameraEnabled(true);
      await room.localParticipant.setMicrophoneEnabled(true).catch(() => undefined);
      const cam = room.localParticipant.getTrackPublication(Track.Source.Camera)?.videoTrack;
      if (cam && videoRef.current) cam.attach(videoRef.current);
      setStatus("live");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStatus("error");
      await cleanup(false);
    }
  }

  async function cleanup(stopAgent: boolean) {
    wsRef.current?.close();
    wsRef.current = null;
    await roomRef.current?.disconnect();
    roomRef.current = null;
    if (stopAgent) await demoApi.stopAgent(liveRoomId.current).catch(() => undefined);
    setAgentIn(false);
  }

  async function stop() {
    await cleanup(true);
    setStatus("idle");
  }

  function sendChat(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim() || wsRef.current?.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({
      type: "message.new", channel_type: "room", channel_id: liveRoomId.current, text: draft,
    }));
    setDraft("");
  }

  useEffect(() => () => { void cleanup(true); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const busy = status === "starting" || status === "live";

  return (
    <div>
      <Header
        title="Live Demo"
        description="Join a room with your camera, start an AI agent, and watch vision lenses react in real time."
      />

      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4 flex flex-wrap items-end gap-5">
        <label className="text-sm">
          <span className="block text-gray-500 mb-1">Room</span>
          <input
            value={roomId}
            disabled={busy}
            onChange={(e) => setRoomId(e.target.value.replace(/[^a-zA-Z0-9_-]/g, ""))}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm w-40"
            data-testid="room-input"
          />
        </label>
        <fieldset className="text-sm" disabled={busy}>
          <legend className="text-gray-500 mb-1">Lenses</legend>
          <div className="flex gap-3">
            {LENSES.map((l) => (
              <label key={l.id} className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={lenses.includes(l.id)}
                  onChange={(e) =>
                    setLenses((prev) => (e.target.checked ? [...prev, l.id] : prev.filter((x) => x !== l.id)))
                  }
                />
                {l.label}
              </label>
            ))}
          </div>
        </fieldset>
        {busy ? (
          <button onClick={stop} className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700">
            <Square className="w-4 h-4" /> Stop demo
          </button>
        ) : (
          <button
            onClick={start}
            disabled={!roomId}
            data-testid="start"
            className="flex items-center gap-2 px-4 py-2 bg-sense-600 text-white text-sm rounded-lg hover:bg-sense-700 disabled:opacity-50"
          >
            <Play className="w-4 h-4" /> Start demo
          </button>
        )}
        <div className="text-sm ml-auto flex items-center gap-4" data-testid="status">
          <span className={status === "live" ? "text-green-600" : "text-gray-500"}>
            ● {status === "live" ? "Live" : status === "starting" ? "Starting…" : status === "error" ? "Error" : "Idle"}
          </span>
          {status === "live" && (
            <span className={agentIn ? "text-green-600" : "text-gray-400"}>
              {agentIn ? "AI agent in room" : "Waiting for agent…"}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-sm text-red-700 rounded-lg" data-testid="error">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 bg-white rounded-xl border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
            <Camera className="w-4 h-4" /> Your camera
          </h3>
          <video ref={videoRef} autoPlay muted playsInline className="w-full rounded-lg bg-gray-900 aspect-video" />
          <p className="text-xs text-gray-400 mt-2">
            Streams to Sense Relay. Browsers require HTTPS or localhost for camera access.
          </p>
        </div>

        <div className="lg:col-span-1 bg-white rounded-xl border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-900 mb-3">Live vision events</h3>
          <div className="space-y-2 max-h-96 overflow-y-auto" data-testid="lens-events">
            {cards.length === 0 && <p className="text-sm text-gray-400">No events yet — start the demo and face the camera.</p>}
            {cards.map((c) => (
              <div key={c.key} className="border border-gray-100 rounded-lg p-3 text-sm" data-testid="lens-card">
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${LENS_STYLE[c.lens] ?? "bg-gray-100 text-gray-700"}`}>
                    {c.lens.replace("_lens", "").toUpperCase()}{c.detail ? ` · ${c.detail}` : ""}
                  </span>
                  <span className="text-xs text-gray-400">{c.at} · {Math.round(c.confidence * 100)}%</span>
                </div>
                <p className="text-gray-600">{c.contextText}</p>
              </div>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-3">The text above is added to the AI agent&apos;s instructions as it arrives.</p>
        </div>

        <div className="lg:col-span-1 bg-white rounded-xl border border-gray-200 p-4 flex flex-col">
          <h3 className="text-sm font-medium text-gray-900 mb-3">Room chat</h3>
          <div className="flex-1 space-y-1.5 max-h-80 overflow-y-auto text-sm" data-testid="chat">
            {chat.length === 0 && <p className="text-gray-400">No messages yet.</p>}
            {chat.map((m) => (
              <div key={m.key}><span className="font-medium text-gray-700">{m.user}:</span> {m.text}</div>
            ))}
          </div>
          <form onSubmit={sendChat} className="flex gap-2 mt-3">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Message…"
              disabled={status !== "live"}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
              data-testid="chat-input"
            />
            <button disabled={status !== "live"} className="p-2 bg-sense-600 text-white rounded-lg disabled:opacity-50">
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
