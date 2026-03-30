"use client";

import { useEffect, useState } from "react";
import { Video, Users, Clock, PlayCircle, StopCircle } from "lucide-react";
import { Header } from "@/components/layout/header";
import { roomsApi, agentsApi, type Room } from "@/lib/api";

export default function RoomsPage() {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionRoom, setActionRoom] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      setRooms(await roomsApi.list());
    } catch {
      setRooms([]);
    } finally {
      setLoading(false);
    }
  }

  async function handleStartAgent(roomId: string) {
    setActionRoom(roomId);
    try {
      await agentsApi.start(roomId, ["MoodLens"]);
      await load();
    } finally {
      setActionRoom(null);
    }
  }

  async function handleStopAgent(roomId: string) {
    setActionRoom(roomId);
    try {
      await agentsApi.stop(roomId);
      await load();
    } finally {
      setActionRoom(null);
    }
  }

  useEffect(() => { void load(); }, []);

  return (
    <div>
      <Header
        title="Rooms"
        description="Active WebRTC rooms on your Sense Relay server."
        onRefresh={load}
      />

      <div className="bg-white rounded-xl border border-gray-200">
        {loading ? (
          <div className="py-16 text-center text-sm text-gray-400">Loading rooms…</div>
        ) : rooms.length === 0 ? (
          <div className="py-16 text-center">
            <Video className="w-8 h-8 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500 font-medium">No rooms found</p>
            <p className="text-xs text-gray-400 mt-1">
              Rooms are created automatically when a client calls{" "}
              <code className="bg-gray-100 px-1 rounded">POST /rooms/:id/join</code>
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Room ID</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                  <div className="flex items-center gap-1"><Users className="w-3 h-3" /> Participants</div>
                </th>
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                  <div className="flex items-center gap-1"><Clock className="w-3 h-3" /> Created</div>
                </th>
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Agent</th>
              </tr>
            </thead>
            <tbody>
              {rooms.map((room) => (
                <tr key={room.room_id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${room.num_participants > 0 ? "bg-green-400" : "bg-gray-300"}`} />
                      <span className="font-medium text-gray-900">{room.room_id}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-gray-700">{room.num_participants}</td>
                  <td className="px-5 py-3 text-gray-500">
                    {new Date(room.creation_time * 1000).toLocaleString()}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleStartAgent(room.room_id)}
                        disabled={actionRoom === room.room_id}
                        className="flex items-center gap-1 px-2.5 py-1 bg-sense-600 hover:bg-sense-700
                                   text-white text-xs rounded-md transition-colors disabled:opacity-50"
                      >
                        <PlayCircle className="w-3 h-3" /> Start
                      </button>
                      <button
                        onClick={() => handleStopAgent(room.room_id)}
                        disabled={actionRoom === room.room_id}
                        className="flex items-center gap-1 px-2.5 py-1 bg-gray-100 hover:bg-gray-200
                                   text-gray-700 text-xs rounded-md transition-colors disabled:opacity-50"
                      >
                        <StopCircle className="w-3 h-3" /> Stop
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
